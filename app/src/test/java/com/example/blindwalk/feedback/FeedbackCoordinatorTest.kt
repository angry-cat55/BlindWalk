package com.example.blindwalk.feedback

import org.junit.Assert.*
import org.junit.Test

class FeedbackCoordinatorTest {
    private var now = 0L
    private var speaking = false
    private var accepted = true
    private var vibrationCount = 0
    private val messages = mutableListOf<String>()

    private fun coordinator() = FeedbackCoordinator(
        speak = { text ->
            if (accepted) {
                messages += text
                speaking = true
            }
            accepted
        },
        isSpeaking = { speaking },
        vibrate = { vibrationCount++ },
        stopSpeech = { speaking = false },
        nowMillis = { now },
    )

    private fun result(id: Int, priority: FeedbackPriority, message: String = "안내 $id") =
        FeedbackResult("WALKING_HAZARD", id, message, priority)

    @Test fun highestPriorityWinsAndSameObjectIsCombined() {
        val coordinator = coordinator()
        val urgent = result(1, FeedbackPriority.URGENT)
        assertEquals(urgent, coordinator.submit(listOf(
            result(1, FeedbackPriority.INFO), result(2, FeedbackPriority.CAUTION), urgent,
        )))
        assertEquals(listOf("안내 1"), messages)
        assertEquals(1, vibrationCount)
    }

    @Test fun samePriorityGivesUnannouncedObjectATurn() {
        val coordinator = coordinator()
        val first = result(1, FeedbackPriority.INFO)
        val second = result(2, FeedbackPriority.INFO)
        assertEquals(first, coordinator.submit(listOf(first, second)))
        speaking = false
        now = 1_000
        assertEquals(second, coordinator.submit(listOf(first, second)))
        assertEquals(0, vibrationCount)
    }

    @Test fun repeatedMessageIsLimitedEvenWhenTrackingIdChanges() {
        val coordinator = coordinator()
        val original = result(1, FeedbackPriority.CAUTION, "전방에 자전거")
        coordinator.submit(listOf(original))
        speaking = false
        now = 1_000
        assertNull(coordinator.submit(listOf(original.copy(objectId = 99))))
        now = 5_000
        assertNotNull(coordinator.submit(listOf(original)))
    }

    @Test fun urgentInterruptsLowerPriorityButNotAnotherUrgent() {
        val coordinator = coordinator()
        coordinator.submit(listOf(result(1, FeedbackPriority.INFO)))
        assertNotNull(coordinator.submit(listOf(result(2, FeedbackPriority.URGENT))))
        assertNull(coordinator.submit(listOf(result(3, FeedbackPriority.URGENT))))
        assertEquals(2, messages.size)
    }

    @Test fun busyResultsAreNotQueuedAndFailedSpeechDoesNotStartCooldown() {
        val coordinator = coordinator()
        val caution = result(1, FeedbackPriority.CAUTION)
        accepted = false
        assertNull(coordinator.submit(listOf(caution)))
        assertEquals(0, vibrationCount)
        accepted = true
        assertNotNull(coordinator.submit(listOf(caution)))
        assertNull(coordinator.submit(listOf(result(2, FeedbackPriority.CAUTION))))
        speaking = false
        assertNull(coordinator.submit(emptyList()))
        assertEquals(1, messages.size)
    }

    @Test fun escalationIsNotBlockedByPreviousLowerPriorityMessage() {
        val coordinator = coordinator()
        val info = result(1, FeedbackPriority.INFO)
        coordinator.submit(listOf(info))
        assertNotNull(coordinator.submit(listOf(info.copy(priority = FeedbackPriority.URGENT))))
    }

    @Test fun resetStopsSpeechAndClearsMemory() {
        val coordinator = coordinator()
        val info = result(1, FeedbackPriority.INFO)
        coordinator.submit(listOf(info))
        coordinator.reset()
        assertFalse(speaking)
        assertNotNull(coordinator.submit(listOf(info)))
    }

    @Test fun historyDoesNotGrowWithoutLimit() {
        val coordinator = coordinator()
        repeat(65) { id ->
            speaking = false
            assertNotNull(coordinator.submit(listOf(result(id, FeedbackPriority.INFO))))
        }

        // 최대 64개이므로 가장 오래된 항목은 제거된다.
        speaking = false
        assertNotNull(coordinator.submit(listOf(result(0, FeedbackPriority.INFO))))
    }
}
