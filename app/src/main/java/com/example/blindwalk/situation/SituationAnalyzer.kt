package com.example.blindwalk.situation

import com.example.blindwalk.model.DetectionFrame
import com.example.blindwalk.model.RiskEvent

// 네 담당 모듈이 공유하는 임시 계약. 모델 추론은 실행하지 않는다.
interface SituationAnalyzer {
    fun analyze(frame: DetectionFrame): List<RiskEvent>
}
