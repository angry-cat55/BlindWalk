package com.example.blindwalk.feedback

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

class SpeechFeedback(context: Context) {
    @Volatile private var ready = false
    @Volatile private var closed = false
    private var tts: TextToSpeech? = null
    private val sequence = AtomicLong()
    private val activeUtterance = AtomicReference<String?>(null)

    init {
        // 비동기 초기화 및 한국어 지원 확인 후에만 발화한다.
        tts = TextToSpeech(context.applicationContext) { status ->
            if (!closed && status == TextToSpeech.SUCCESS) {
                ready = (tts?.setLanguage(Locale.KOREAN) ?: TextToSpeech.LANG_NOT_SUPPORTED) >= 0
            }
        }

        // 완료·오류·중단은 TTS 스레드에서 올 수 있다.
        // 발화 ID가 같을 때만 지워 이전 발화 콜백이 새 발화를 지우지 않게 한다.
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) = Unit
            override fun onDone(utteranceId: String?) { finish(utteranceId) }
            override fun onError(utteranceId: String?) { finish(utteranceId) }
            override fun onStop(utteranceId: String?, interrupted: Boolean) {
                finish(utteranceId)
            }
        })
    }

    // 준비되었으면 지정 문장을 읽고 호출 성공 여부를 UI에 알린다.
    fun speak(message: String = "보행 보조 서비스 음성 안내 테스트입니다."): Boolean {
        if (!ready || closed || message.isBlank()) return false

        val id = "feedback-${sequence.incrementAndGet()}"
        activeUtterance.set(id)
        val accepted = tts?.speak(message, TextToSpeech.QUEUE_FLUSH, null, id) == TextToSpeech.SUCCESS
        if (!accepted) activeUtterance.compareAndSet(id, null)
        return accepted
    }

    // 재생 시작 대기 상태도 포함해서 발화 중으로 취급한다.
    fun isSpeaking(): Boolean = activeUtterance.get() != null

    private fun finish(id: String?) {
        // 콜백의 문자열은 새 객체일 수 있으므로 참조가 아닌 내용을 비교한다.
        activeUtterance.updateAndGet { current -> if (current == id) null else current }
    }

    fun stop() {
        activeUtterance.set(null)
        tts?.stop()
    }

    // 화면 종료 시 음성을 중단하고 엔진 자원을 해제한다.
    fun close() {
        closed = true
        ready = false
        stop()
        tts?.shutdown()
    }
}
