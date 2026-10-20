package com.example.blindwalk.camera

// 밀린 프레임을 몰아 보내지 않고, 직전 선택부터 200ms가 지난 최신 프레임만 고른다.
internal class FrameGate {
    private var lastSelected: Long? = null
    fun select(nowNanos: Long): Boolean {
        if (lastSelected?.let { nowNanos - it < 200_000_000L } == true) return false
        lastSelected = nowNanos
        return true
    }
}
