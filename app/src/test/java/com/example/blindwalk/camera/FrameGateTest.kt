package com.example.blindwalk.camera

import org.junit.Assert.*
import org.junit.Test

class FrameGateTest {
    @Test fun selectsAtMostEvery200ms() {
        val gate = FrameGate()
        assertTrue(gate.select(0))
        assertFalse(gate.select(199_999_999))
        assertTrue(gate.select(200_000_000))
        assertFalse(gate.select(200_000_001))
    }

    @Test fun delayedFrameDoesNotCreateCatchUpBurst() {
        val gate = FrameGate()
        assertTrue(gate.select(0))
        assertTrue(gate.select(1_500_000_000))
        assertFalse(gate.select(1_500_000_001))
        assertTrue(gate.select(1_700_000_000))
    }
}
