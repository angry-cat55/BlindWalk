package com.example.blindwalk.inference

class MockInferenceEngine {
    // 실제 모델을 실행하지 않고 호출 확인용 고정 문자열만 반환한다.
    fun infer(): String = "선형 점자블록 감지 (Mock)"
}
