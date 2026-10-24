package com.example.blindwalk

import android.graphics.Bitmap
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import com.example.blindwalk.bridge.PythonBridge
import com.example.blindwalk.feedback.FeedbackCoordinator
import com.example.blindwalk.feedback.FeedbackPriority
import com.example.blindwalk.feedback.SpeechFeedback
import com.example.blindwalk.feedback.HapticFeedback
import com.example.blindwalk.inference.MobileInferenceEngine
import com.example.blindwalk.inference.Recognition
import java.nio.FloatBuffer
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class AiIntegrationTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext

    @Test fun bundledModelsActuallyRunOnAndroid() {
        val bitmap = Bitmap.createBitmap(640, 480, Bitmap.Config.ARGB_8888)
        try {
            MobileInferenceEngine(context).use { engine ->
                // 검정 영상도 실제 YOLO 연산을 실행한다. 검출 개수는 강제하지 않는다.
                assertTrue(engine.infer(bitmap).all { it.confidence.isFinite() })
            }
        } finally { bitmap.recycle() }

        // YOLO가 빈 결과여도 깊이 모델의 양자화 연산까지 별도로 검증한다.
        val environment = OrtEnvironment.getEnvironment()
        OrtSession.SessionOptions().use { options ->
            options.setIntraOpNumThreads(2)
            environment.createSession(context.assets.open("ai/depth.onnx").use { it.readBytes() }, options).use { session ->
                OnnxTensor.createTensor(environment, FloatBuffer.wrap(FloatArray(3 * 256 * 256)),
                    longArrayOf(1, 3, 256, 256)).use { input ->
                    session.run(mapOf("input" to input)).use { output ->
                        val tensor = output[0] as OnnxTensor
                        assertEquals(3, tensor.info.shape.size)
                        val values = FloatArray(tensor.floatBuffer.remaining())
                        tensor.floatBuffer.get(values)
                        assertTrue(values.isNotEmpty())
                        assertTrue(values.all { it.isFinite() })
                    }
                }
            }
        }
    }

    @Test fun pythonResultsReachTheFeedbackCoordinator() {
        val bridge = PythonBridge()
        bridge.resetSession()
        val results = bridge.analyzeFrame(1, listOf(
            Recognition(1, "overhang", 0.9f, listOf(0, 0, 100, 100), null),
            Recognition(2, "vehicle", 0.9f, listOf(280, 250, 360, 440), null),
        ), 640, 480)
        assertEquals(2, results.size)

        instrumentation.runOnMainSync {
            var spoken = ""
            var vibrations = 0
            val coordinator = FeedbackCoordinator(
                speak = { spoken = it; true }, isSpeaking = { false },
                vibrate = { vibrations++ }, stopSpeech = {},
            )
            val selected = coordinator.submit(results)
            assertEquals(FeedbackPriority.URGENT, selected?.priority)
            assertEquals("전방에 차량", spoken)
            assertEquals(1, vibrations)
            coordinator.reset()
        }
    }

    @Test fun koreanSpeechAndHapticRequestsAreAccepted() {
        lateinit var speech: SpeechFeedback
        lateinit var haptic: HapticFeedback
        instrumentation.runOnMainSync {
            speech = SpeechFeedback(context)
            haptic = HapticFeedback(context)
        }

        try {
            // TTS 초기화를 기다리되 실제 요청이 수락되면 한 번만 읽는다.
            var accepted = false
            val deadline = android.os.SystemClock.elapsedRealtime() + 15_000
            while (!accepted && android.os.SystemClock.elapsedRealtime() < deadline) {
                instrumentation.runOnMainSync { accepted = speech.speak() }
                if (!accepted) android.os.SystemClock.sleep(100)
            }
            assertTrue("한국어 TTS 초기화 또는 발화 요청 실패", accepted)
            instrumentation.runOnMainSync { haptic.vibrate() }

            // 실제 청취·진동 체감은 사람이 확인해야 한다. 여기서는 API 요청을 검증한다.
            val finishDeadline = android.os.SystemClock.elapsedRealtime() + 10_000
            while (speech.isSpeaking() && android.os.SystemClock.elapsedRealtime() < finishDeadline) {
                android.os.SystemClock.sleep(100)
            }
            assertFalse("TTS 완료 콜백이 오지 않음", speech.isSpeaking())
        } finally {
            instrumentation.runOnMainSync { speech.close(); haptic.close() }
        }
    }
}
