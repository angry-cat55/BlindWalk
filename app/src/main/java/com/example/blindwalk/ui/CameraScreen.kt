package com.example.blindwalk.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.example.blindwalk.camera.CameraPreview
import com.example.blindwalk.feedback.HapticFeedback
import com.example.blindwalk.feedback.SpeechFeedback
import com.example.blindwalk.bridge.PythonBridge

// 카메라와 일곱 테스트 버튼을 표시하고 담당 모듈의 함수만 호출한다.
@Composable
fun CameraScreen() {
    val context = LocalContext.current
    var granted by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
            PackageManager.PERMISSION_GRANTED)
    }
    val permission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted = it }
    LaunchedEffect(Unit) {
        if (!granted) permission.launch(Manifest.permission.CAMERA)
    }

    val python = remember { PythonBridge() }
    val analyzers = remember {
        listOf(
            "점자블록 이상 판단" to "TACTILE_ANOMALY",
            "점형블록 주변 분석" to "TACTILE_CONTEXT",
            "일반 보행 위험 판단" to "WALKING_HAZARD",
            "머리 높이 장애물 판단" to "OVERHEAD_HAZARD"
        )
    }
    val haptic = remember(context) { HapticFeedback(context) }
    val speech = remember(context) { SpeechFeedback(context) }
    var message by remember { mutableStateOf("초기 Skeleton · 실제 AI 미구현") }
    DisposableEffect(haptic, speech) {
        onDispose { haptic.close(); speech.close() }
    }

    Column(Modifier.fillMaxSize().safeDrawingPadding().padding(16.dp)) {
        if (granted) {
            CameraPreview(Modifier.fillMaxWidth().weight(1f), onError = { message = it })
        } else {
            Text("카메라 권한이 필요합니다.", Modifier.weight(1f))
        }
        Column(
            Modifier.fillMaxWidth().weight(1f).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Text(message)
            Button(onClick = { message = python.infer() }) { Text("AI 인식 테스트") }
            analyzers.forEach { (label, situation) ->
                Button(onClick = {
                    python.analyze(situation)
                    message = "아직 구현되지 않은 기능입니다"
                }) { Text(label) }
            }
            Button(onClick = { haptic.vibrate() }) { Text("진동 테스트") }
            Button(onClick = {
                if (!speech.speak()) message = "TTS 초기화 또는 한국어 음성 지원을 확인해 주세요."
            }) { Text("TTS 테스트") }
        }
    }
}
