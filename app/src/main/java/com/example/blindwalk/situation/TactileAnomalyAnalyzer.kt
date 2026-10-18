package com.example.blindwalk.situation

import com.example.blindwalk.model.DetectionFrame
import com.example.blindwalk.model.RiskEvent

class TactileAnomalyAnalyzer : SituationAnalyzer {
    override fun analyze(frame: DetectionFrame): List<RiskEvent> {
        // TODO: 점자블록의 파손, 가림, 단절 등 이상 상태을 판단하는 기능을 구현할 예정.
        return emptyList()
    }
}
