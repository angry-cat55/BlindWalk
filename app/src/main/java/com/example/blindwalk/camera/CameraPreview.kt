package com.example.blindwalk.camera

import android.view.ViewOutlineProvider
import androidx.camera.core.CameraSelector
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner

// 후면 카메라 미리보기만 연결한다. 프레임 분석이나 저장은 하지 않는다.
@Composable
fun CameraPreview(modifier: Modifier = Modifier, onError: (String) -> Unit) {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val view = remember(context) {
        PreviewView(context).apply {
            // Compose 안에서 미리보기가 지정된 영역에 맞게 그려지도록 한다.
            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
            outlineProvider = ViewOutlineProvider.BOUNDS
            clipToOutline = true
        }
    }
    AndroidView(factory = { view }, modifier = modifier)

    DisposableEffect(owner, view) {
        val future = ProcessCameraProvider.getInstance(context)
        val preview = Preview.Builder().build()
        var provider: ProcessCameraProvider? = null
        var disposed = false
        future.addListener({
            if (!disposed) {
                try {
                    provider = future.get()
                    preview.setSurfaceProvider(view.surfaceProvider)
                    provider?.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, preview)
                } catch (exception: Exception) {
                    onError("카메라를 시작할 수 없습니다: ${exception.localizedMessage}")
                }
            }
        }, ContextCompat.getMainExecutor(context))
        // 화면을 벗어나면 이 미리보기의 연결만 해제한다.
        onDispose {
            disposed = true
            provider?.unbind(preview)
        }
    }
}
