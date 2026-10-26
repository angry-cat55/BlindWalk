package com.example.blindwalk.inference

import org.junit.Assert.*
import org.junit.Test

class ObjectTrackerTest {
    private fun obj(x: Int = 100, name: String = "person", candidate: Int = 1, size: Int = 100) =
        Recognition(candidate, name, .9f, listOf(x, 100, x + size, 100 + size), null)

    @Test fun candidateNumberAndOrderDoNotDetermineTrackId() {
        val tracker = ObjectTracker()
        val first = tracker.update(listOf(obj(100, candidate = 50), obj(400, candidate = 60)), 0)
        val next = tracker.update(listOf(obj(410, candidate = 50), obj(110, candidate = 60)), 200)
        assertEquals(first[1].id, next[0].id)
        assertEquals(first[0].id, next[1].id)
        assertNotEquals(next[0].id, next[1].id)
    }

    @Test fun missedFramesReturnNoObjectsAndReconnectAtOneSecondBoundary() {
        val tracker = ObjectTracker()
        val first = tracker.update(listOf(obj()), 100).single()
        assertTrue(tracker.update(emptyList(), 400).isEmpty())
        assertTrue(tracker.update(emptyList(), 900).isEmpty())
        val current = obj(110, candidate = 98).copy(confidence = .6f, distanceM = 2.3f,
            contour = listOf(listOf(110, 100), listOf(210, 100), listOf(210, 200)))
        val linked = tracker.update(listOf(current), 1_100).single()
        assertEquals(first.id, linked.id)
        assertEquals(current.copy(id = first.id), linked)
        assertEquals(1, tracker.diagnostics.reconnected)
    }

    @Test fun missingObservationsDoNotExtendLastSeenAndExpiredIdIsNeverReused() {
        val tracker = ObjectTracker()
        val first = tracker.update(listOf(obj(candidate = 90)), 0).single().id
        tracker.update(emptyList(), 999)
        assertTrue(tracker.update(emptyList(), 1_001).isEmpty())
        assertEquals(1, tracker.diagnostics.expired)
        assertEquals(0, tracker.diagnostics.retained)
        val second = tracker.update(listOf(obj(candidate = 90)), 1_002).single().id
        assertTrue(second > first)
        val third = tracker.update(listOf(obj()), 2_003).single().id
        assertTrue(third > second)
    }

    @Test fun unrelatedClassLocationAndSizeGetNewIdsEvenWithinOneSecond() {
        for (changed in listOf(obj(450), obj(name = "vehicle"), obj(size = 300))) {
            val tracker = ObjectTracker()
            val first = tracker.update(listOf(obj()), 0).single().id
            tracker.update(emptyList(), 100)
            assertNotEquals(first, tracker.update(listOf(changed), 200).single().id)
        }
    }

    @Test fun oneTrackCannotBeAssignedToTwoDetections() {
        val tracker = ObjectTracker()
        val first = tracker.update(listOf(obj()), 0).single().id
        val next = tracker.update(listOf(obj(102), obj(175)), 200)
        assertEquals(2, next.map { it.id }.toSet().size)
        assertEquals(first, next[0].id)
        assertNotEquals(first, next[1].id)
    }

    @Test fun equallyPlausibleObjectsAreNotForciblyLinked() {
        val tracker = ObjectTracker()
        val oldIds = tracker.update(listOf(obj(100), obj(140)), 0).map { it.id }
        val next = tracker.update(listOf(obj(120)), 200).single()
        assertFalse(next.id in oldIds)
    }

    @Test fun ambiguousCrossingCanSettleOnANewTrackWithoutPermanentIdChurn() {
        val tracker = ObjectTracker()
        val first = tracker.update(listOf(obj(60), obj(340)), 0).map { it.id }
        assertEquals(first, tracker.update(listOf(obj(100), obj(300)), 200).map { it.id })
        // 두 예측 중심이 겹친다. 이 순간은 억지로 연결하지 않고 새 ID를 사용한다.
        val replacement = tracker.update(listOf(obj(200)), 700).single().id
        assertFalse(replacement in first)
        for (time in 900L..3_100L step 200) {
            assertEquals(replacement, tracker.update(listOf(obj(200)), time).single().id)
        }
    }

    @Test fun motionUsesElapsedTimeAndOnlyPredictsInternallyAcrossGap() {
        val tracker = ObjectTracker()
        val id = tracker.update(listOf(obj(100)), 0).single().id
        assertEquals(id, tracker.update(listOf(obj(130)), 200).single().id)
        assertTrue(tracker.update(emptyList(), 500).isEmpty())
        // 150px/s 이동. 직전 bbox와는 겹침이 적지만 500ms 예측과 맞는다.
        val actual = obj(205, candidate = 999)
        val current = tracker.update(listOf(actual), 700).single()
        assertEquals(id, current.id)
        assertEquals(actual.bbox, current.bbox)
        assertEquals(200L, tracker.diagnostics.intervalMillis)
    }

    @Test fun oppositeMovingObjectsKeepIdsWhenObservationOrderChanges() {
        val tracker = ObjectTracker()
        val first = tracker.update(listOf(obj(100), obj(320)), 0)
        assertEquals(2, first.map { it.id }.toSet().size)
        val second = tracker.update(listOf(obj(140), obj(280)), 200)
        assertEquals(first.map { it.id }, second.map { it.id })
        val crossed = tracker.update(listOf(obj(200), obj(220)), 600)
        assertEquals(first[1].id, crossed[0].id)
        assertEquals(first[0].id, crossed[1].id)
    }

    @Test fun missingObjectReconnectsAlongsideAnotherActiveObjectOfSameClass() {
        val tracker = ObjectTracker()
        val first = tracker.update(listOf(obj(100), obj(400)), 0)
        assertEquals(first[0].id, tracker.update(listOf(obj(110)), 200).single().id)
        val both = tracker.update(listOf(obj(400), obj(120)), 400)
        assertEquals(first[1].id, both[0].id)
        assertEquals(first[0].id, both[1].id)
        assertEquals(1, tracker.diagnostics.reconnected)
    }

    @Test fun resetDropsTracksMotionAndClockForNewSession() {
        val tracker = ObjectTracker()
        tracker.update(listOf(obj()), 10_000)
        tracker.update(listOf(obj(130)), 10_200)
        tracker.reset()
        val result = tracker.update(listOf(obj(160)), 0)
        assertEquals(1, tracker.diagnostics.created)
        assertEquals(0, tracker.diagnostics.reconnected)
        assertNull(tracker.diagnostics.intervalMillis)
        assertEquals(1, result.single().id)
    }

    @Test fun retainedHistoryIsBoundedUnderRapidUnmatchedDetections() {
        val tracker = ObjectTracker()
        val ids = mutableSetOf<Int>()
        repeat(300) { index ->
            val result = tracker.update(listOf(obj(name = "class$index")), index.toLong())
            assertTrue(ids.add(result.single().id))
            assertTrue(tracker.diagnostics.retained <= 256)
        }
        assertEquals(256, tracker.diagnostics.retained)
        assertEquals(1, tracker.diagnostics.evicted)
    }

    @Test fun capacityKeepsAllUnexpiredTracksAtMaximumCameraRateAndDecoderCount() {
        val tracker = ObjectTracker()
        // 200ms 간격·결과30개. 1000ms 경계의 최초 관측까지 총180개가 유효하다.
        for (frame in 0..5) {
            tracker.update(List(30) { obj(name = "frame${frame}object$it") }, frame * 200L)
        }
        assertEquals(180, tracker.diagnostics.retained)
        assertEquals(0, tracker.diagnostics.evicted)
        tracker.update(emptyList(), 1_001)
        assertEquals(30, tracker.diagnostics.expired)
        assertEquals(150, tracker.diagnostics.retained)
    }

    @Test(expected = IllegalArgumentException::class)
    fun backwardsTimeIsRejectedInsteadOfRevivingExpiredHistory() {
        val tracker = ObjectTracker()
        tracker.update(listOf(obj()), 100)
        tracker.update(emptyList(), 99)
    }
}
