package com.example.blindwalk.inference

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.os.SystemClock
import android.util.Log
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import org.json.JSONObject
import org.tensorflow.lite.DataType
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.gpu.CompatibilityList
import org.tensorflow.lite.gpu.GpuDelegate
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.math.*

// 모델 실행은 단일 분석 스레드에서만 한다. Python에는 예측 결과만 전달한다.
class MobileInferenceEngine(context: Context, preferGpu: Boolean = true) : AutoCloseable {
    private val environment = OrtEnvironment.getEnvironment()
    private val modelBuffer = direct(context.assets.open("ai/yolo11n_seg_18cls.tflite").use { it.readBytes() })
    private var gpuDelegate: GpuDelegate? = null
    var yoloBackend: String = "CPU"
        private set
    private var yolo = createYolo(preferGpu)
    private val depth: OrtSession
    private val labelMetadata = JSONObject(context.assets.open("ai/labels.json").bufferedReader().use { it.readText() })
    private val labels = labelMetadata.getJSONArray("labels")
        .let { names -> List(names.length()) { names.getString(it) } }
    private val decoder = YoloDecoder(labels)
    private val yoloInput = ByteBuffer.allocateDirect(3 * 640 * 640 * 4).order(ByteOrder.nativeOrder())
    private val boxes = ByteBuffer.allocateDirect(54 * 8400 * 4).order(ByteOrder.nativeOrder())
    private val masks = ByteBuffer.allocateDirect(32 * 160 * 160 * 4).order(ByteOrder.nativeOrder())
    private val canvasBitmap = Bitmap.createBitmap(640, 640, Bitmap.Config.ARGB_8888)
    private val paint = Paint(Paint.FILTER_BITMAP_FLAG)

    init {
        try {
            // README 설명 대신 실제 모델의 NCHW shape와 자료형을 검증한다.
            check(yolo.getInputTensor(0).shape().contentEquals(intArrayOf(1, 3, 640, 640)))
            check(yolo.getInputTensor(0).dataType() == DataType.FLOAT32)
            check(yolo.getOutputTensor(0).shape().contentEquals(intArrayOf(1, 54, 8400)))
            check(yolo.getOutputTensor(1).shape().contentEquals(intArrayOf(1, 32, 160, 160)))
            check(labels.size == 18)
            val digest = MessageDigest.getInstance("SHA-256")
            digest.update(modelBuffer.asReadOnlyBuffer().apply { rewind() })
            val fingerprint = digest.digest().joinToString("") { "%02x".format(it) }
            check(fingerprint == labelMetadata.getString("sha256")) { "모델과 클래스 목록이 일치하지 않습니다" }
            OrtSession.SessionOptions().use { options ->
                options.setIntraOpNumThreads(2)
                depth = environment.createSession(context.assets.open("ai/depth.onnx").use { it.readBytes() }, options)
            }
        } catch (exception: Exception) {
            closeYolo()
            canvasBitmap.recycle()
            throw exception
        }
    }

    fun infer(frame: Bitmap): List<Recognition> {
        val started = SystemClock.elapsedRealtime()
        // 가로 4:3 영상은 회색 여백을 위아래에 넣어 640×640으로 만든다.
        // 탐지 좌표는 decoder에서 여백을 제거해 원본 좌표로 되돌린다.
        val gain = min(640f / frame.width, 640f / frame.height)
        val left = (640 - frame.width * gain) / 2
        val top = (640 - frame.height * gain) / 2
        val canvas = Canvas(canvasBitmap)
        canvas.drawColor(Color.rgb(114, 114, 114))
        canvas.drawBitmap(frame, null, RectF(left, top, left + frame.width * gain, top + frame.height * gain), paint)
        fillInput(canvasBitmap, yoloInput, normalize = false)
        boxes.rewind(); masks.rewind()
        runYolo()
        val yoloFinished = SystemClock.elapsedRealtime()

        val detections = decoder.decode(readFloats(boxes), readFloats(masks), frame.width, frame.height)
        val decoded = SystemClock.elapsedRealtime()
        if (detections.isEmpty()) {
            Log.d("AiInference", "backend=$yoloBackend objects=0 yoloMs=${yoloFinished - started} decodeMs=${decoded - yoloFinished}")
            return detections
        }

        // MiDaS는 letterbox가 아니라 PC 파이프라인과 같은 256×256 리사이즈다.
        val resized = Bitmap.createScaledBitmap(frame, 256, 256, true)
        val input = ByteBuffer.allocateDirect(3 * 256 * 256 * 4).order(ByteOrder.nativeOrder())
        try { fillInput(resized, input, normalize = true) }
        finally { if (resized !== frame) resized.recycle() }

        OnnxTensor.createTensor(environment, input.asFloatBuffer(), longArrayOf(1, 3, 256, 256)).use { tensor ->
            depth.run(mapOf("input" to tensor)).use { outputs ->
                val output = outputs[0] as OnnxTensor
                val shape = output.info.shape
                check(shape.size == 3 && shape[0] == 1L) { "지원하지 않는 깊이 출력 shape" }
                val dh = shape[1].toInt()
                val dw = shape[2].toInt()
                val values = FloatArray(dh * dw)
                output.floatBuffer.get(values)
                val depthFinished = SystemClock.elapsedRealtime()
                val recognized = detections.map { obj -> obj.copy(distanceM = distance(obj, values, dw, dh, frame.width, frame.height)) }
                Log.d("AiInference", "backend=$yoloBackend objects=${recognized.size} yoloMs=${yoloFinished - started} decodeMs=${decoded - yoloFinished} depthMs=${depthFinished - decoded} postMs=${SystemClock.elapsedRealtime() - depthFinished}")
                return recognized
            }
        }
    }

    private fun fillInput(bitmap: Bitmap, target: ByteBuffer, normalize: Boolean) {
        val count = bitmap.width * bitmap.height
        val pixels = IntArray(count)
        bitmap.getPixels(pixels, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)
        val means = floatArrayOf(0.485f, 0.456f, 0.406f)
        val deviations = floatArrayOf(0.229f, 0.224f, 0.225f)
        target.rewind()
        // RGB 채널을 차례로 쓴 NCHW다. YUV 버퍼나 NHWC를 그대로 넘기지 않는다.
        for (channel in 0..2) for (pixel in pixels) {
            val value = ((pixel shr (16 - channel * 8)) and 255) / 255f
            target.putFloat(if (normalize) (value - means[channel]) / deviations[channel] else value)
        }
        target.rewind()
    }

    private fun distance(obj: Recognition, values: FloatArray, dw: Int, dh: Int, width: Int, height: Int): Float? {
        val box = obj.bbox
        val samples = mutableListOf<Float>()
        val contour = obj.contour
        val marginX = if (contour == null) (box[2] - box[0]) / 4 else 0
        val marginY = if (contour == null) (box[3] - box[1]) / 4 else 0

        // 깊이 맵 셀 중심에서 객체 마스크 또는 bbox 중앙 50% 영역을 샘플링한다.
        // PC의 원본 크기 보간 후 중앙값과는 표본 해상도 차이가 있다.
        for (y in 0 until dh) for (x in 0 until dw) {
            val px = (x + 0.5f) * width / dw
            val py = (y + 0.5f) * height / dh
            if (px < box[0] + marginX || px > box[2] - marginX ||
                py < box[1] + marginY || py > box[3] - marginY) continue
            if (contour != null && !contains(contour, px, py)) continue
            val value = values[y * dw + x]
            if (value.isFinite() && value > 0) samples += value
        }
        if (samples.isEmpty()) return null
        samples.sort()
        val middle = samples.size / 2
        val median = if (samples.size % 2 == 0) (samples[middle - 1] + samples[middle]) / 2 else samples[middle]
        // AI 담당자의 PC 코드와 같은 K=1000 환산이다. 실제 미터 보정 정확도는 미검증이다.
        val estimate = 1000f / (median + 0.0001f)
        return estimate.takeIf { it.isFinite() && it > 0 }?.coerceIn(0.3f, 15f)
    }

    private fun contains(points: List<List<Int>>, x: Float, y: Float): Boolean {
        var inside = false
        var previous = points.last()
        for (point in points) {
            if ((point[1] > y) != (previous[1] > y) &&
                x < point[0] + (y - point[1]) * (previous[0] - point[0]) / (previous[1] - point[1])) inside = !inside
            previous = point
        }
        return inside
    }

    override fun close() {
        closeYolo()
        depth.close()
        canvasBitmap.recycle()
        // OrtEnvironment는 앱 전역 공유이므로 세션 종료 때 닫지 않는다.
    }

    private fun createYolo(useGpu: Boolean): Interpreter {
        // GPU 생성·추론·해제는 호출자의 동일 분석 스레드에서만 수행한다.
        var candidate: GpuDelegate? = null
        if (useGpu) {
            try {
                CompatibilityList().use { compatibility ->
                    if (compatibility.isDelegateSupportedOnThisDevice) {
                        candidate = GpuDelegate(compatibility.bestOptionsForThisDevice)
                        val interpreter = Interpreter(modelBuffer, Interpreter.Options().addDelegate(candidate!!))
                        gpuDelegate = candidate
                        yoloBackend = "GPU"
                        // 일부 연산만 위임될 수 있다. 전체 GPU 여부는 런타임 로그로 구분한다.
                        Log.i("AiInference", "YOLO GPU delegate initialized")
                        return interpreter
                    }
                    Log.w("AiInference", "GPU unsupported on this device; using CPU")
                }
            } catch (failure: Throwable) {
                if (failure !is Exception && failure !is LinkageError) throw failure
                candidate?.close()
                Log.w("AiInference", "GPU initialization failed; using CPU", failure)
            }
        }

        yoloBackend = "CPU"
        modelBuffer.rewind()
        return Interpreter(modelBuffer, Interpreter.Options().apply { setNumThreads(2) })
    }

    private fun runYolo() {
        try {
            yolo.runForMultipleInputsOutputs(arrayOf(yoloInput), mapOf(0 to boxes, 1 to masks))
        } catch (failure: Exception) {
            if (gpuDelegate == null) throw failure

            // 로드는 성공했으나 실행이 실패한 경우에도 모델을 새 CPU 엔진으로 재생성한다.
            Log.w("AiInference", "GPU invocation failed; retrying on CPU", failure)
            closeYolo()
            yolo = createYolo(false)
            yoloInput.rewind(); boxes.rewind(); masks.rewind()
            yolo.runForMultipleInputsOutputs(arrayOf(yoloInput), mapOf(0 to boxes, 1 to masks))
        }
    }

    private fun closeYolo() {
        try { yolo.close() }
        finally {
            gpuDelegate?.close()
            gpuDelegate = null
        }
    }

    companion object {
        private fun direct(bytes: ByteArray): ByteBuffer = ByteBuffer.allocateDirect(bytes.size)
            .order(ByteOrder.nativeOrder()).apply { put(bytes); rewind() }

        private fun readFloats(buffer: ByteBuffer): FloatArray {
            buffer.rewind()
            val values = FloatArray(buffer.capacity() / 4)
            buffer.asFloatBuffer().get(values)
            return values
        }
    }
}
