package com.example.blindwalk.bridge

import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.example.blindwalk.feedback.FeedbackPriority
import com.example.blindwalk.feedback.FeedbackResult
import com.example.blindwalk.inference.Recognition
import org.json.JSONArray
import org.json.JSONObject

// Python은 Manifest의 PyApplication이 초기화한다. 이곳은 함수 호출만 연결한다.
class PythonBridge {
    // 새 촬영 세션에서 Python의 이전 안내 기록을 초기화한다.
    fun resetSession() {
        Python.getInstance().getModule("frame_interface").callAttr("reset_session")
    }

    // Kotlin 추론 결과만 전달한다. Python에서 모델을 중복 실행하지 않는다.
    fun analyzeFrame(frameId: Long, objects: List<Recognition>, width: Int, height: Int): List<FeedbackResult> {
        val detections = JSONArray()
        objects.forEach { obj ->
            detections.put(JSONObject().apply {
                put("id", obj.id)
                put("class_name", obj.className)
                put("confidence", obj.confidence.toDouble())
                put("distance_m", obj.distanceM?.toDouble() ?: JSONObject.NULL)
                put("bbox", JSONArray(obj.bbox))
                put("contour", obj.contour?.let { points ->
                    JSONArray().apply { points.forEach { put(JSONArray(it)) } }
                } ?: JSONObject.NULL)
            })
        }

        val returned = Python.getInstance().getModule("frame_interface").callAttr(
            "analyze_json", frameId, detections.toString(), width, height,
        ).toString()
        val results = JSONArray(returned)
        return List(results.length()) { index ->
            val item = results.getJSONObject(index)
            // 알 수 없는 등급을 임의로 바꾸지 않고 연결 오류로 처리한다.
            FeedbackResult(
                item.getString("situation"), item.getInt("object_id"),
                item.getString("message"), FeedbackPriority.valueOf(item.getString("priority")),
            )
        }
    }

    // Python의 고정 Mock 문자열을 UI에 전달한다.
    fun infer(): String = Python.getInstance().getModule("mock_inference")
        .callAttr("infer").toString()

    // 선택한 테스트 상황을 공통 처리 파일에 전달하고 결과 목록을 반환한다.
    fun analyze(situation: String): List<PyObject> = Python.getInstance()
        .getModule("frame_interface").callAttr("run_test", situation).asList()
}
