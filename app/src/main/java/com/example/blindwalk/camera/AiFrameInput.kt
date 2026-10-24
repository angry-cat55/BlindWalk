package com.example.blindwalk.camera

import androidx.camera.core.ImageProxy
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import com.example.blindwalk.bridge.PythonBridge
import com.example.blindwalk.feedback.FeedbackResult
import com.example.blindwalk.inference.MobileInferenceEngine
import com.example.blindwalk.inference.Recognition
import java.util.concurrent.atomic.AtomicBoolean

// 좌표는 넓은 영상의 중앙 4:3을 자른 뒤 640×480 기준이다. 원본 이미지는 UI에 넘기지 않는다.
data class AiFrameResult(
    val frameId: Long,
    val selectedAtMillis: Long,
    val detections: List<Recognition>,
    val feedback: List<FeedbackResult>,
)

/** 카메라 원본 → Kotlin 추론 → Python 상황 판단을 분석 스레드에서 동기 실행한다. */
class AiFrameInput(private val context: Context) {
    private var engine: MobileInferenceEngine? = null
    private val bridge = PythonBridge()
    private val cancelled = AtomicBoolean(false)

    fun onFrameSelected(frameId: Long, image: ImageProxy): AiFrameResult? {
        if (cancelled.get()) return null
        val selectedAt = android.os.SystemClock.elapsedRealtime()

        // 최초 프레임에서 같은 분석 스레드에 모델과 Python 세션을 준비한다.
        if (engine == null) {
            engine = MobileInferenceEngine(context.applicationContext)
            bridge.resetSession()
        }

        // CameraX가 YUV planes의 stride를 처리한다. 원본 소유권은 카메라에 남는다.
        val raw = image.toBitmap()
        val crop = image.cropRect
        val matrix = Matrix().apply { postRotate(image.imageInfo.rotationDegrees.toFloat()) }
        val oriented = Bitmap.createBitmap(raw, crop.left, crop.top, crop.width(), crop.height(), matrix, true)
        if (oriented !== raw) raw.recycle()

        // 화면은 16:9로 유지한다. 추론만 중앙 4:3으로 잘라 기존 모듈 계약을 유지한다.
        val area = AnalysisRegion.centered(oriented.width, oriented.height)
        val cropped = Bitmap.createBitmap(oriented, area.left, area.top, area.width, area.height)
        if (cropped !== oriented) oriented.recycle()
        val frame = Bitmap.createScaledBitmap(cropped, 640, 480, true)
        if (frame !== cropped) cropped.recycle()

        try {
            val detections = engine!!.infer(frame)
            if (cancelled.get()) return null
            return AiFrameResult(frameId, selectedAt, detections,
                bridge.analyzeFrame(frameId, detections, frame.width, frame.height))
        } finally {
            frame.recycle()
        }
    }

    // UI 중지 시 즉시 결과를 무효화한다. JNI 자원은 실행 중 추론이 끝난 뒤 닫는다.
    fun cancel() { cancelled.set(true) }

    fun close() {
        engine?.close()
        engine = null
    }
}
