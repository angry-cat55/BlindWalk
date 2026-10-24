package com.example.blindwalk.ui

import kotlin.math.min

// 16:9 Preview의 중앙 4:3 crop을 화면으로 복원한다. 바깥 여백도 포함한다.
data class OverlayTransform(val scale: Float, val left: Float, val top: Float) {
    fun x(value: Float) = left + value.coerceIn(0f, 640f) * scale
    fun y(value: Float) = top + value.coerceIn(0f, 480f) * scale

    companion object {
        fun fit(width: Float, height: Float): OverlayTransform {
            val previewHeight = min(height, width * 9f / 16f)
            val scale = previewHeight / 480f
            return OverlayTransform(scale, (width - 640f * scale) / 2, (height - 480f * scale) / 2)
        }
    }
}
