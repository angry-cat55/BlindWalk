package com.example.blindwalk.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class OverlayTransformTest {
    @Test fun wideScreenCentersFourByThreeWithoutStretching() {
        val fit = OverlayTransform.fit(1920f, 1080f)
        assertEquals(240f, fit.x(0f), .01f)
        assertEquals(1680f, fit.x(640f), .01f)
        assertEquals(0f, fit.y(0f), .01f)
        assertEquals(1080f, fit.y(480f), .01f)
    }

    @Test fun narrowScreenHasVerticalMarginsAndClampsInvalidCoordinates() {
        val fit = OverlayTransform.fit(640f, 600f)
        assertEquals(120f, fit.y(0f), .01f)
        assertEquals(480f, fit.y(480f), .01f)
        assertEquals(80f, fit.x(-10f), .01f)
        assertEquals(560f, fit.x(900f), .01f)
    }
}
