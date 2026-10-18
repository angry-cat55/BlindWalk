package com.example.blindwalk.situation

import com.example.blindwalk.model.DetectionFrame
import com.example.blindwalk.model.RiskEvent

class TactileContextAnalyzer : SituationAnalyzer {
    override fun analyze(frame: DetectionFrame): List<RiskEvent> {
        // TODO: 점형블록 주변의 계단, 횡단보도, 엘리베이터 등 환경을 판단하는 기능을 구현할 예정.
        return emptyList()
    }
}
