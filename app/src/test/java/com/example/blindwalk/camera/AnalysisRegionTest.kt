package com.example.blindwalk.camera

import org.junit.Assert.assertEquals
import org.junit.Test

class AnalysisRegionTest {
    @Test fun wideInputDropsOnlyLeftAndRight() {
        assertEquals(AnalysisRegion(240, 0, 1440, 1080), AnalysisRegion.centered(1920, 1080))
    }

    @Test fun fourByThreeInputIsUnchanged() {
        assertEquals(AnalysisRegion(0, 0, 640, 480), AnalysisRegion.centered(640, 480))
    }

    @Test fun narrowerFallbackStaysCentered() {
        assertEquals(AnalysisRegion(0, 60, 640, 480), AnalysisRegion.centered(640, 600))
    }
}
