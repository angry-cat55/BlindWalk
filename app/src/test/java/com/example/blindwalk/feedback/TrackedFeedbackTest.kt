package com.example.blindwalk.feedback

import com.example.blindwalk.inference.ObjectTracker
import com.example.blindwalk.inference.Recognition
import org.junit.Assert.*
import org.junit.Test

class TrackedFeedbackTest {
    @Test fun reconnectedIdKeepsFiveSecondLimitAfterPhraseLimitEnds() {
        val tracker = ObjectTracker()
        var now = 0L
        val spoken = mutableListOf<String>()
        val coordinator = FeedbackCoordinator({ spoken += it; true }, { false }, {}, {}, { now })
        val observation = Recognition(80, "overhang", .9f, listOf(10, 20, 100, 200), null)
        fun submit(observations: List<Recognition>): FeedbackResult? {
            val current = tracker.update(observations, now)
            return coordinator.submit(current.map {
                FeedbackResult("OVERHEAD_HAZARD", it.id, "돌출물 주의", FeedbackPriority.CAUTION)
            })
        }
        val first = submit(listOf(observation))!!
        now = 400
        assertNull(submit(emptyList()))
        now = 800
        assertNull(submit(listOf(observation.copy(id = 900))))
        // 5초 동안 관측 간격은 1초 이내로 유지한다.
        for (time in listOf(1_600L, 2_400L, 3_000L, 4_000L, 4_999L)) {
            now = time
            assertNull(submit(listOf(observation)))
        }
        assertEquals(1, spoken.size)
        now = 5_000
        assertEquals(first.objectId, submit(listOf(observation))?.objectId)
        assertEquals(2, spoken.size)
    }

    @Test fun newTrackStillSharesPhraseCooldownAndResetStartsNewFeedbackSession() {
        val tracker = ObjectTracker()
        var now = 0L
        var spoken = 0
        val coordinator = FeedbackCoordinator({ spoken++; true }, { false }, {}, {}, { now })
        val observation = Recognition(1, "overhang", .9f, listOf(10, 20, 100, 200), null)
        fun feedback(id: Int) = FeedbackResult("OVERHEAD_HAZARD", id, "돌출물 주의", FeedbackPriority.CAUTION)
        val firstId = tracker.update(listOf(observation), now).single().id
        assertNotNull(coordinator.submit(listOf(feedback(firstId))))
        now = 1_001
        val nextId = tracker.update(listOf(observation), now).single().id
        assertNotEquals(firstId, nextId)
        now = 2_999
        assertNull(coordinator.submit(listOf(feedback(nextId))))
        now = 3_000
        assertNotNull(coordinator.submit(listOf(feedback(nextId))))
        coordinator.reset()
        tracker.reset()
        now = 0
        val sessionId = tracker.update(listOf(observation), now).single().id
        assertNotNull(coordinator.submit(listOf(feedback(sessionId))))
        assertEquals(3, spoken)
    }
}
