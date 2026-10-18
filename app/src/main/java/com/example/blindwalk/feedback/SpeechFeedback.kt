package com.example.blindwalk.feedback

import android.content.Context
import android.speech.tts.TextToSpeech
import java.util.Locale

class SpeechFeedback(context: Context) {
    private var ready = false
    private var closed = false
    private var tts: TextToSpeech? = null

    init {
        // 비동기 초기화 및 한국어 지원 확인 후에만 발화한다.
        tts = TextToSpeech(context.applicationContext) { status ->
            if (!closed && status == TextToSpeech.SUCCESS) {
                ready = (tts?.setLanguage(Locale.KOREAN) ?: TextToSpeech.LANG_NOT_SUPPORTED) >= 0
            }
        }
    }

    // 준비되었으면 지정 문장을 읽고 호출 성공 여부를 UI에 알린다.
    fun speak(): Boolean = ready && tts?.speak(
        "보행 보조 서비스 음성 안내 테스트입니다.",
        TextToSpeech.QUEUE_FLUSH, null, "speech-test"
    ) == TextToSpeech.SUCCESS

    // 화면 종료 시 음성을 중단하고 엔진 자원을 해제한다.
    fun close() {
        closed = true
        ready = false
        tts?.stop()
        tts?.shutdown()
    }
}
