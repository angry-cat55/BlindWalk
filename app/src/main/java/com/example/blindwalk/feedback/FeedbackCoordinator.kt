package com.example.blindwalk.feedback

// Python의 priority 문자열과 같은 이름을 사용한다. 순서는 낮은 등급부터다.
enum class FeedbackPriority { INFO, CAUTION, URGENT }

// Python 결과의 네 필드를 Kotlin에서 사용할 형태다. 변환은 Bridge의 향후 작업이다.
data class FeedbackResult(
    val situation: String,
    val objectId: Int,
    val message: String,
    val priority: FeedbackPriority,
)

// 최신 결과에서 이번에 안내할 하나를 고른다. 모든 호출은 메인 스레드에서 한다.
// 최근 안내만 메모리에 저장하며 파일·DB·Keystore에는 저장하지 않는다.
// 완료 후 자동 재생하는 큐는 없다. 다음 submit의 최신 결과로 다시 선택한다.
class FeedbackCoordinator(
    private val speak: (String) -> Boolean,
    private val isSpeaking: () -> Boolean,
    private val vibrate: () -> Unit,
    private val stopSpeech: () -> Unit,
    private val nowMillis: () -> Long = { System.nanoTime() / 1_000_000 },
) {
    private data class Key(val objectId: Int, val message: String, val priority: FeedbackPriority)

    // 정확히 같은 대상은 5초, ID가 바뀌어도 같은 문구·등급은 3초 제한한다.
    // 같은 종류의 서로 다른 객체도 잠시 묶일 수 있는 정책이다.
    private val history = linkedMapOf<Key, Long>()
    private val phraseHistory = linkedMapOf<Pair<String, FeedbackPriority>, Long>()
    private var activePriority: FeedbackPriority? = null

    fun submit(results: List<FeedbackResult>): FeedbackResult? {
        val now = nowMillis()
        prune(history, now)
        prune(phraseHistory, now)

        // 같은 객체를 여러 모듈이 안내하면 가장 높은 등급 하나만 남긴다.
        // 동률이면 입력 순서를 유지한다. 객체 ID는 해당 프레임 안에서만 비교한다.
        val candidates = results.filter { it.message.isNotBlank() }
            .groupBy { it.objectId }
            .values.map { group -> group.maxBy { it.priority.ordinal } }
            .filter { result ->
                val exact = history[key(result)]
                val phrase = phraseHistory[result.message to result.priority]
                (exact == null || now - exact >= 5_000) &&
                    (phrase == null || now - phrase >= 3_000)
            }

        // 높은 등급 우선, 같은 등급이면 덜 최근에 안내한 대상을 먼저 고른다.
        // 한 번도 안내하지 않은 대상끼리는 입력 순서대로 선택한다.
        val selected = candidates.sortedWith(
            compareByDescending<FeedbackResult> { it.priority.ordinal }
                .thenBy { history[key(it)] ?: Long.MIN_VALUE },
        ).firstOrNull() ?: return null

        // 말하는 중에는 쌓지 않는다. 새 URGENT만 낮은 등급 안내를 중단한다.
        if (isSpeaking()) {
            if (selected.priority != FeedbackPriority.URGENT || activePriority == FeedbackPriority.URGENT) {
                return null
            }
        } else {
            activePriority = null
        }

        // 초기화 실패 등으로 발화 요청을 받지 못하면 기록·진동도 하지 않는다.
        // speak는 SpeechFeedback처럼 기존 발화를 교체하는 함수를 전달한다.
        if (!speak(selected.message)) return null

        activePriority = selected.priority
        remember(history, key(selected), now)
        remember(phraseHistory, selected.message to selected.priority, now)

        if (selected.priority != FeedbackPriority.INFO) vibrate()

        // 호출자는 이 결과로 화면을 갱신할 수 있다. null은 새 안내가 없다는 뜻이다.
        return selected
    }

    // 중지·새 세션 시작 시 호출한다. TTS 엔진 해제와 진동 취소는 소유 화면의 역할이다.
    fun reset() {
        stopSpeech()
        history.clear()
        phraseHistory.clear()
        activePriority = null
    }

    private fun key(result: FeedbackResult) = Key(result.objectId, result.message, result.priority)

    // 두 기록 모두 최대 64개·최근 30초로 제한해 장시간 실행해도 쌓이지 않게 한다.
    private fun <K> prune(records: MutableMap<K, Long>, now: Long) {
        records.entries.removeAll { now - it.value >= 30_000 }
    }

    private fun <K> remember(records: MutableMap<K, Long>, key: K, now: Long) {
        records.remove(key)
        records[key] = now
        if (records.size > 64) records.remove(records.keys.first())
    }
}
