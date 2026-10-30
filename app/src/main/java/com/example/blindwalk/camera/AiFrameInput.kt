package com.example.blindwalk.camera

import androidx.camera.core.ImageProxy
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import android.os.SystemClock
import android.util.Log
import com.example.blindwalk.bridge.PythonBridge
import com.example.blindwalk.feedback.FeedbackResult
import com.example.blindwalk.inference.MobileInferenceEngine
import com.example.blindwalk.inference.Recognition
import com.example.blindwalk.inference.ObjectTracker
import java.util.concurrent.atomic.AtomicBoolean

// 좌표는 넓은 영상의 중앙 4:3을 자른 뒤 640×480 기준이다. 원본 이미지는 UI에 넘기지 않는다.
data class AiFrameResult(
    val frameId: Long,
    val selectedAtMillis: Long,
    val detections: List<Recognition>,
    val feedback: List<FeedbackResult>,
    val frameBitmap: Bitmap? = null,
)

/** 카메라 원본 → Kotlin 추론 → 객체 추적 → Python 판단을 분석 스레드에서 동기 실행한다. */
class AiFrameInput(private val context: Context) {
    private var engine: MobileInferenceEngine? = null
    private val bridge = PythonBridge()
    private val cancelled = AtomicBoolean(false)
    private val tracker = ObjectTracker()
    private var pythonReady = false

    fun onFrameSelected(frameId: Long, image: ImageProxy): AiFrameResult? {
        if (cancelled.get()) return null
        val selectedAt = SystemClock.elapsedRealtime()

        // 모델 자원은 생성·호출·해제 모두 같은 분석 스레드에서 처리한다.
        if (engine == null) {
            engine = MobileInferenceEngine(context.applicationContext)
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
            val observations = engine!!.infer(frame)
            if (cancelled.get()) return null
            // 추론 완료 시각이 아닌 원본 선택 시각으로 유실 시간을 잰다. 빈 탐지도 갱신한다.
            val detections = tracker.update(observations, selectedAt)
            val stats = tracker.diagnostics
            Log.d("ObjectTracking", "frame=$frameId intervalMs=${stats.intervalMillis} " +
                "observed=${detections.size} new=${stats.created} reconnected=${stats.reconnected} " +
                "expired=${stats.expired} evicted=${stats.evicted} retained=${stats.retained} " +
                "selectionAgeMs=${SystemClock.elapsedRealtime() - selectedAt}")
            // Python 상태는 앱 전역이다. 재시작 시 이전 호출 종료 후 초기화하고,
            // 잠금을 기다리던 이전 세션은 새 세션 상태를 다시 변경하지 못하게 한다.
            val feedback = synchronized(pythonSessionLock) {
                if (cancelled.get()) return null
                if (!pythonReady) {
                    bridge.resetSession()
                    pythonReady = true
                }
                bridge.analyzeFrame(frameId, detections, frame.width, frame.height)
            }
            if (cancelled.get()) return null
            // UI와 Python 모두 현재 관측 목록만 사용한다. 유실 트랙은 포함하지 않는다.
            val displayBitmap = frame.copy(Bitmap.Config.ARGB_8888, false)
            return AiFrameResult(frameId, selectedAt, detections, feedback, displayBitmap)
        } finally {
            frame.recycle()
        }
    }

    fun onBitmapFrame(frameId: Long, source: Bitmap): AiFrameResult? {
        if (cancelled.get()) return null
        val selectedAt = SystemClock.elapsedRealtime()
        if (engine == null) {
            engine = MobileInferenceEngine(context.applicationContext)
        }
        val area = AnalysisRegion.centered(source.width, source.height)
        val cropped = Bitmap.createBitmap(source, area.left, area.top, area.width, area.height)
        val frame = Bitmap.createScaledBitmap(cropped, 640, 480, true)
        if (cropped !== source && cropped !== frame) cropped.recycle()

        try {
            val observations = engine!!.infer(frame)
            if (cancelled.get()) return null
            val detections = tracker.update(observations, selectedAt)
            val feedback = synchronized(pythonSessionLock) {
                if (cancelled.get()) return null
                if (!pythonReady) {
                    bridge.resetSession()
                    pythonReady = true
                }
                bridge.analyzeFrame(frameId, detections, frame.width, frame.height)
            }
            if (cancelled.get()) return null
            val displayBitmap = frame.copy(Bitmap.Config.ARGB_8888, false)
            return AiFrameResult(frameId, selectedAt, detections, feedback, displayBitmap)
        } finally {
            frame.recycle()
        }
    }

    // UI 중지 시 즉시 결과를 무효화한다. JNI 자원은 실행 중 추론이 끝난 뒤 닫는다.
    fun cancel() { cancelled.set(true) }

    fun close() {
        cancelled.set(true)
        try { engine?.close() }
        finally {
            engine = null
            tracker.reset()
            pythonReady = false
        }
    }

    private companion object {
        val pythonSessionLock = Any()
    }
}
