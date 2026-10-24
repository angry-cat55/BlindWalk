package com.example.blindwalk.inference

import org.junit.Assert.*
import org.junit.Test

class YoloDecoderTest {
    private val labels = listOf("person", "tactile_line")
    private fun boxes(secondClass: Int = 0): FloatArray {
        // 후보 2개의 출력이다. 좌표는 cx,cy,w,h의 정규화 값이다.
        val values = FloatArray(7 * 2)
        for (i in 0..1) {
            values[i] = 0.5f
            values[2 + i] = 0.5f
            values[4 + i] = 0.2f
            values[6 + i] = 0.2f
            values[(4 + if (i == 0) 0 else secondClass) * 2 + i] = if (i == 0) 0.9f else 0.8f
        }
        return values
    }

    @Test fun normalizedCoordinatesUndoLetterboxAndSameClassNms() {
        val decoder = YoloDecoder(labels, candidateCount = 2, maskSize = 2, maskChannels = 1)
        val objects = decoder.decode(boxes(), FloatArray(4), 640, 480)
        assertEquals(1, objects.size)
        assertEquals(listOf(256, 176, 384, 304), objects[0].bbox)
        assertEquals("person", objects[0].className)
        assertNull(objects[0].distanceM)
    }

    @Test fun differentClassesSurviveNmsAndScoresAreNotSigmoidedAgain() {
        val decoder = YoloDecoder(labels, candidateCount = 2, maskSize = 2, maskChannels = 1)
        assertEquals(2, decoder.decode(boxes(1), FloatArray(4), 640, 480).size)
        val low = boxes().apply { this[8] = 0.1f; this[9] = 0.1f }
        assertTrue(decoder.decode(low, FloatArray(4), 640, 480).isEmpty())
    }

    @Test fun tactileMaskProducesPolygonInOriginalImageCoordinates() {
        val decoder = YoloDecoder(listOf("tactile_line"), candidateCount = 1, maskSize = 4, maskChannels = 1)
        val values = floatArrayOf(0.5f, 0.5f, 1f, 0.75f, 0.9f, 1f)
        val obj = decoder.decode(values, FloatArray(16) { 1f }, 640, 480).single()
        assertTrue(obj.contour!!.size >= 3)
        assertTrue(obj.contour!!.all { it[0] in 0..639 && it[1] in 0..479 })
    }
}
