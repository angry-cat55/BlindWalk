package com.example.blindwalk

import android.graphics.Bitmap
import android.graphics.Color
import android.os.SystemClock
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.example.blindwalk.inference.MobileInferenceEngine
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class GpuBenchmarkTest {
    @Test fun compareCpuAndGpuWithTheSameInput() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val image = Bitmap.createBitmap(640, 480, Bitmap.Config.ARGB_8888).apply {
            eraseColor(Color.rgb(114, 114, 114))
        }
        try {
            for (useGpu in listOf(false, true)) {
                // 같은 스레드에서 생성·워밍업·실행·해제를 수행한다.
                MobileInferenceEngine(context, preferGpu = useGpu).use { engine ->
                    repeat(2) { engine.infer(image) }
                    val times = List(5) {
                        val start = SystemClock.elapsedRealtimeNanos()
                        val objects = engine.infer(image)
                        assertTrue(objects.all { it.confidence.isFinite() })
                        (SystemClock.elapsedRealtimeNanos() - start) / 1_000_000.0
                    }.sorted()
                    val report = "requestedGpu=$useGpu actual=${engine.yoloBackend} medianMs=${times[2]} minMs=${times.first()} maxMs=${times.last()}"
                    Log.i("GpuBenchmark", report)
                    println(report)
                    assertEquals(if (useGpu) "GPU" else "CPU", engine.yoloBackend)
                }
            }
        } finally { image.recycle() }
    }
}
