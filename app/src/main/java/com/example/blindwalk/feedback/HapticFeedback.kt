package com.example.blindwalk.feedback

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator

class HapticFeedback(context: Context) {
    private val vibrator = context.getSystemService(Vibrator::class.java)

    // 테스트용 짧은 진동을 한 번 실행한다. API 24~25도 지원한다.
    @Suppress("DEPRECATION")
    fun vibrate() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator.vibrate(VibrationEffect.createOneShot(150, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            vibrator.vibrate(150)
        }
    }

    // 화면 종료 시 진행 중인 진동을 중단한다.
    fun close() { vibrator.cancel() }
}
