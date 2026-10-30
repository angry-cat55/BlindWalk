package com.example.blindwalk.feedback

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import com.example.blindwalk.inference.Recognition

class HapticFeedback(context: Context) {
    private val vibrator = context.getSystemService(Vibrator::class.java)
    private val externalHaptic = UsbHapticManager(context.applicationContext)

    init {
        externalHaptic.connectIfNeeded()
    }

    @Suppress("DEPRECATION")
    fun vibrate() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator.vibrate(VibrationEffect.createOneShot(150, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            vibrator.vibrate(150)
        }
        externalHaptic.triggerPreparedPulse()
    }

    fun vibrateDirectional(selected: FeedbackResult, detections: List<Recognition>) {
        externalHaptic.vibrateForSelectedFeedback(selected, detections)
    }

    fun close() {
        vibrator.cancel()
        externalHaptic.close()
    }
}