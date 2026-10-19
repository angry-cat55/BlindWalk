package com.example.blindwalk.bridge

import com.chaquo.python.PyObject
import com.chaquo.python.Python

// Python은 Manifest의 PyApplication이 초기화한다. 이곳은 함수 호출만 연결한다.
class PythonBridge {
    // Python의 고정 Mock 문자열을 UI에 전달한다.
    fun infer(): String = Python.getInstance().getModule("mock_inference")
        .callAttr("infer").toString()

    // 선택한 테스트 상황을 공통 처리 파일에 전달하고 결과 목록을 반환한다.
    fun analyze(situation: String): List<PyObject> = Python.getInstance()
        .getModule("frame_interface").callAttr("run_test", situation).asList()
}
