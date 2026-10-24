package com.example.blindwalk.camera

// 회전이 끝난 영상에서 중앙 4:3 영역만 선택한다. 비율을 늘이거나 누르지 않는다.
data class AnalysisRegion(val left: Int, val top: Int, val width: Int, val height: Int) {
    companion object {
        fun centered(width: Int, height: Int): AnalysisRegion {
            require(width > 0 && height > 0)
            val cropWidth = minOf(width, height * 4 / 3).coerceAtLeast(1)
            val cropHeight = minOf(height, width * 3 / 4).coerceAtLeast(1)
            return AnalysisRegion((width - cropWidth) / 2, (height - cropHeight) / 2, cropWidth, cropHeight)
        }
    }
}
