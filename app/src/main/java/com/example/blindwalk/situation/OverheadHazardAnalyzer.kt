package com.example.blindwalk.situation

import com.example.blindwalk.model.DetectionFrame
import com.example.blindwalk.model.RiskEvent

class OverheadHazardAnalyzer : SituationAnalyzer {
    override fun analyze(frame: DetectionFrame): List<RiskEvent> {
        // TODO: 나뭇가지, 돌출 간판 등 머리 높이 장애물을 판단하는 기능을 구현할 예정.
        return emptyList()
    }
}
