package com.example.blindwalk.situation

import com.example.blindwalk.model.DetectionFrame
import com.example.blindwalk.model.RiskEvent

class WalkingHazardAnalyzer : SituationAnalyzer {
    override fun analyze(frame: DetectionFrame): List<RiskEvent> {
        // TODO: 턱, 계단, 장애물, 노면 등 일반 보행 위험을 판단하는 기능을 구현할 예정.
        return emptyList()
    }
}
