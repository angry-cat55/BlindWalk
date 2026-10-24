package com.example.blindwalk.camera

import android.util.Log
import android.util.Range
import android.util.Rational
import android.view.Surface
import android.view.View
import androidx.camera.core.*
import androidx.camera.core.resolutionselector.AspectRatioStrategy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Observer
import androidx.lifecycle.compose.LocalLifecycleOwner
import java.util.concurrent.Executors

/** Preview와 분석 스레드를 분리하고 선택한 프레임의 판단 결과를 UI에 전달한다. */
@Composable
fun CameraPreview(
    modifier: Modifier = Modifier,
    onReady: () -> Unit,
    onError: (String) -> Unit,
    onResults: (AiFrameResult) -> Unit,
) {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val ready by rememberUpdatedState(onReady)
    val error by rememberUpdatedState(onError)
    val results by rememberUpdatedState(onResults)
    val view = remember(context) {
        PreviewView(context).apply {
            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
            scaleType = PreviewView.ScaleType.FIT_CENTER
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
            keepScreenOn = true
        }
    }
    AndroidView(factory = { view }, modifier = modifier)

    DisposableEffect(owner, view) {
        val future = ProcessCameraProvider.getInstance(context)
        val executor = Executors.newSingleThreadExecutor()
        val ai = AiFrameInput(context.applicationContext)
        val rotation = view.display?.rotation ?: Surface.ROTATION_90
        val resolution = ResolutionSelector.Builder().setAspectRatioStrategy(
            AspectRatioStrategy(AspectRatio.RATIO_16_9, AspectRatioStrategy.FALLBACK_RULE_AUTO)
        ).build()
        val preview = Preview.Builder().setResolutionSelector(resolution)
            .setTargetRotation(rotation).setTargetFrameRate(Range(30, 30)).build()
        val analysis = ImageAnalysis.Builder().setResolutionSelector(resolution)
            .setTargetRotation(rotation).setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
        val gate = FrameGate()
        var frameId = 0L
        var windowStart = android.os.SystemClock.elapsedRealtimeNanos()
        var received = 0
        var selected = 0
        val disposed = java.util.concurrent.atomic.AtomicBoolean(false)
        var provider: ProcessCameraProvider? = null
        analysis.setAnalyzer(executor) { image ->
            try {
                if (!disposed.get()) {
                    val now = android.os.SystemClock.elapsedRealtimeNanos()
                    received++
                    if (gate.select(now)) {
                        selected++
                        val feedback = ai.onFrameSelected(++frameId, image)
                        ContextCompat.getMainExecutor(context).execute {
                            // 중지한 세션의 늦은 결과로 UI·음성을 다시 실행하지 않는다.
                            if (!disposed.get() && feedback != null) results(feedback)
                        }
                        Log.d("CameraInput", "selected=$frameId timestampNs=${image.imageInfo.timestamp} buffer=${image.width}x${image.height} crop=${image.cropRect} rotation=${image.imageInfo.rotationDegrees} format=${image.format}")
                    }
                    if (now - windowStart >= 2_000_000_000L) {
                        val seconds = (now - windowStart) / 1_000_000_000.0
                        Log.d("CameraInput", "analysisFps=${received / seconds} selectedFps=${selected / seconds}")
                        received = 0; selected = 0; windowStart = now
                    }
                }
            } catch (exception: Exception) {
                ContextCompat.getMainExecutor(context).execute { if (!disposed.get()) error("프레임 처리 오류: ${exception.localizedMessage}") }
            } finally { image.close() }
        }
        val observer = Observer<PreviewView.StreamState> {
            if (!disposed.get() && it == PreviewView.StreamState.STREAMING) ready()
        }
        view.previewStreamState.observe(owner, observer)
        future.addListener({
            if (!disposed.get()) {
                try {
                    provider = future.get()
                    preview.setSurfaceProvider(view.surfaceProvider)
                    // 화면과 분석은 같은 16:9 원본 범위를 공유한다. AI용 4:3 crop은 이후 수행한다.
                    val group = UseCaseGroup.Builder().setViewPort(ViewPort.Builder(Rational(16, 9), rotation)
                        .setScaleType(ViewPort.FILL_CENTER).build()).addUseCase(preview).addUseCase(analysis).build()
                    provider?.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, group)
                } catch (exception: Exception) {
                    error("카메라를 시작할 수 없습니다: ${exception.localizedMessage}")
                }
            }
        }, ContextCompat.getMainExecutor(context))
        // 프레임 소유권은 카메라 측에 있다. 소비자는 콜백 안에서만 읽는다.
        onDispose {
            disposed.set(true)
            ai.cancel()
            view.previewStreamState.removeObserver(observer)
            analysis.clearAnalyzer()
            provider?.unbind(preview, analysis)
            // 추론 중 JNI 자원을 닫지 않는다. 같은 executor 뒤에서 해제한다.
            executor.execute { ai.close() }
            executor.shutdown()
            view.keepScreenOn = false
        }
    }
}
