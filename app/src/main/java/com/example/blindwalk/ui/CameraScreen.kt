package com.example.blindwalk.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.SystemClock
import android.provider.Settings
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import android.media.MediaMetadataRetriever
import android.util.Log
import com.example.blindwalk.camera.AiFrameInput
import com.example.blindwalk.camera.AiFrameResult
import com.example.blindwalk.camera.CameraPreview
import com.example.blindwalk.feedback.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private val Ink = Color(0xFF142421)
private val Mint = Color(0xFF9CF2C7)

/** 자동 카메라 화면. 일시정지해도 같은 위치의 버튼으로 다시 시작한다. */
@Composable
fun CameraScreen() {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    var foreground by remember { mutableStateOf(owner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) }
    var running by remember { mutableStateOf(false) }
    var prepared by remember { mutableStateOf(false) }
    var cameraReady by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var denied by remember { mutableStateOf(false) }
    var showDetections by remember { mutableStateOf(true) }
    var frame by remember { mutableStateOf<AiFrameResult?>(null) }
    var selectedId by remember { mutableStateOf<Int?>(null) }
    var announcement by remember { mutableStateOf<FeedbackResult?>(null) }
    var announcementAt by remember { mutableLongStateOf(0L) }

    // 화면의 음성 엔진은 유지하고, 일시정지 시 공통 안내의 세션 기록만 초기화한다.
    val speech = remember { SpeechFeedback(context) }
    val haptic = remember { HapticFeedback(context) }
    val coordinator = remember {
        FeedbackCoordinator(speech::speak, speech::isSpeaking, haptic::vibrate, speech::stop)
    }

    val scope = rememberCoroutineScope()
    var videoRunning by remember { mutableStateOf(false) }
    var videoJob by remember { mutableStateOf<Job?>(null) }
    val videoAiInput = remember(context) { AiFrameInput(context.applicationContext) }

    val videoLauncher = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        if (uri != null) {
            videoJob?.cancel()
            videoRunning = true
            prepared = true
            videoJob = scope.launch(Dispatchers.Default) {
                val retriever = MediaMetadataRetriever()
                try {
                    retriever.setDataSource(context, uri)
                    val durationStr = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)
                    val durationMs = durationStr?.toLongOrNull() ?: 0L
                    var frameId = 10000L
                    val playStartTime = SystemClock.elapsedRealtime()
                    while (isActive) {
                        val elapsedMs = SystemClock.elapsedRealtime() - playStartTime
                        if (elapsedMs >= durationMs) break

                        val timeUs = elapsedMs * 1000L
                        val rawBitmap = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
                            retriever.getScaledFrameAtTime(timeUs, MediaMetadataRetriever.OPTION_CLOSEST, 640, 480)
                        } else {
                            retriever.getFrameAtTime(timeUs, MediaMetadataRetriever.OPTION_CLOSEST_SYNC)
                        }
                        if (rawBitmap != null) {
                            val result = videoAiInput.onBitmapFrame(++frameId, rawBitmap)
                            rawBitmap.recycle()
                            if (result != null) {
                                withContext(Dispatchers.Main) {
                                    val old = frame
                                    frame = result
                                    if (old !== frame) old?.frameBitmap?.recycle()
                                    selectedId = null
                                    coordinator.submit(result.feedback)?.let { fb ->
                                        val hDir = haptic.vibrateDirectional(fb, result.detections)
                                        announcement = fb.copy(message = hDir + fb.message)
                                        announcementAt = SystemClock.elapsedRealtime()
                                        if (frame != null) selectedId = fb.objectId
                                    }
                                }
                            }
                        } else {
                            delay(10L)
                        }
                    }
                } catch (e: Exception) {
                    Log.e("VideoVerify", "영상 검증 중 오류: ${e.message}")
                } finally {
                    try { retriever.release() } catch (_: Exception) {}
                    withContext(Dispatchers.Main) {
                        videoRunning = false
                    }
                }
            }
        }
    }
    fun pause() {
        videoJob?.cancel()
        videoRunning = false
        running = false
        prepared = false
        cameraReady = false
        frame?.frameBitmap?.recycle()
        frame = null
        selectedId = null
        announcement = null
        coordinator.reset()
        haptic.close()
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        denied = !granted
        running = granted
        error = if (granted) null else "카메라 권한이 필요합니다"
    }
    fun start() {
        error = null
        prepared = false
        cameraReady = false
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            denied = false
            running = true
        } else permission.launch(Manifest.permission.CAMERA)
    }

    LaunchedEffect(Unit) { start() }
    DisposableEffect(owner) {
        val observer = LifecycleEventObserver { _, event ->
            // 복귀 시 자동 촬영하지 않는다. 같은 위치의 다시 시작 버튼을 이용한다.
            if (event == Lifecycle.Event.ON_START) foreground = true
            if (event == Lifecycle.Event.ON_STOP) { foreground = false; pause(); speech.stop() }
        }
        owner.lifecycle.addObserver(observer)
        onDispose {
            videoJob?.cancel()
            videoAiInput.close()
            owner.lifecycle.removeObserver(observer)
            coordinator.reset()
            speech.close()
            haptic.close()
        }
    }
    BackHandler(enabled = running) { pause() }

    val status = when {
        error != null -> "실행할 수 없음"
        videoRunning -> "영상 검증 중"
        !running -> "일시정지"
        !cameraReady || !prepared -> "준비 중"
        else -> "실행 중"
    }
    // TalkBack 사용 시에도 상태를 직접 읽을 수 있다. 안내 카드 자동 읽기와 중복하지 않는다.
    LaunchedEffect(status, error, foreground) {
        if (!foreground) return@LaunchedEffect
        val phrase = error ?: when (status) {
            "준비 중" -> "카메라와 인식을 준비합니다"
            "실행 중" -> "인식을 시작합니다"
            else -> "일시정지했습니다"
        }
        for (attempt in 0 until 40) {
            // 상태 음성 때문에 이미 선택된 위험 안내를 끊지 않는다.
            if (status == "실행 중" && announcement != null) break
            if (speech.speak(phrase)) break
            delay(100)
        }
    }
    // 추론이 멈추거나 늦어져도 오래된 박스와 안내 문구는 독립적으로 지운다.
    LaunchedEffect(frame?.frameId, frame?.selectedAtMillis) {
        val current = frame ?: return@LaunchedEffect
        delay((current.selectedAtMillis + 1_200 - SystemClock.elapsedRealtime()).coerceAtLeast(0))
        current.frameBitmap?.recycle()
        frame = null
        selectedId = null
    }
    LaunchedEffect(announcementAt) {
        if (announcementAt > 0) {
            delay(3_000)
            announcement = null
        }
    }

    BoxWithConstraints(Modifier.fillMaxSize().background(Color(0xFF0D1718))) {
        // FIT_CENTER 영상의 왼쪽 여백만큼 이름을 옮긴다. 카메라 크기와 좌표는 유지한다.
        val previewSidePadding = ((maxWidth - maxHeight * 16f / 9f) / 2f).coerceAtLeast(0.dp)
        if (running && !videoRunning) {
            CameraPreview(Modifier.size(1.dp).alpha(0f).clearAndSetSemantics {},
                onReady = { cameraReady = true },
                onError = { reason -> pause(); error = reason },
                onResults = { result ->
                    prepared = true
                    // 매 결과의 실제 관측 목록으로 교체한다. 유실 트랙으로 박스를 연장하지 않는다.
                    val old = frame
                    frame = result.takeIf { SystemClock.elapsedRealtime() - it.selectedAtMillis < 1_200 }
                    if (old !== frame) old?.frameBitmap?.recycle()
                    selectedId = null
                    coordinator.submit(result.feedback)?.let {
                        val hDir = haptic.vibrateDirectional(it, result.detections)
                        announcement = it.copy(message = hDir + it.message)
                        announcementAt = SystemClock.elapsedRealtime()
                        if (frame != null) selectedId = it.objectId
                    }
                })
        }
        if (showDetections && (running || videoRunning)) {
            DetectionOverlay(frame?.detections.orEmpty(), selectedId, Modifier.fillMaxSize(), frame?.frameBitmap)
        }
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(
            Color.Black.copy(alpha = .65f), Color.Transparent, Color.Transparent, Color.Black.copy(alpha = .75f)))))

        Column(Modifier.fillMaxSize().safeDrawingPadding().padding(horizontal = 24.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.SpaceBetween) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween) {
                Text("BlindWalk", color = Color.White, fontWeight = FontWeight.SemiBold, fontSize = 22.sp,
                    modifier = Modifier.padding(start = previewSidePadding).semantics { heading() })
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    TextButton(onClick = { showDetections = !showDetections },
                        colors = ButtonDefaults.textButtonColors(contentColor = Color.White),
                        modifier = Modifier.heightIn(min = 48.dp).semantics {
                            contentDescription = "검출 표시"
                            stateDescription = if (showDetections) "켜짐" else "꺼짐"
                        }) { Text(if (showDetections) "검출 표시 켜짐" else "검출 표시 꺼짐", fontSize = 16.sp) }
                    Surface(shape = RoundedCornerShape(28.dp), color = Ink.copy(alpha = .95f)) {
                        Text(status, color = Mint, fontWeight = FontWeight.Bold, fontSize = 18.sp,
                            modifier = Modifier.padding(horizontal = 18.dp, vertical = 10.dp))
                    }
                }
            }
            if (!running || !prepared) {
                Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()),
                    horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                    if (running) CircularProgressIndicator(color = Mint, modifier = Modifier.size(36.dp))
                    Text(error ?: if (running) "카메라와 인식을 준비하고 있습니다" else "일시정지",
                        color = Color.White, fontWeight = FontWeight.Bold, fontSize = 26.sp,
                        modifier = Modifier.padding(12.dp))
                    if (denied) TextButton(onClick = {
                        context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}")))
                    }) { Text("카메라 권한 설정 열기", color = Mint, fontSize = 20.sp) }
                }
            } else Spacer(Modifier.weight(1f))

            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(start = previewSidePadding, bottom = 4.dp),
                horizontalArrangement = Arrangement.Start
            ) {
                Surface(
                    shape = RoundedCornerShape(16.dp),
                    color = if (videoRunning) Color(0xFFC62828) else Ink.copy(alpha = .88f)
                ) {
                    TextButton(
                        onClick = {
                            if (videoRunning) {
                                videoJob?.cancel()
                                videoRunning = false
                            } else {
                                videoLauncher.launch("video/*")
                            }
                        },
                        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 4.dp)
                    ) {
                        Text(
                            text = if (videoRunning) "⏹ 영상 중지" else "🎬 영상 검증",
                            color = if (videoRunning) Color.White else Mint,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }

            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom,
                horizontalArrangement = Arrangement.spacedBy(18.dp)) {
                val current = announcement
                if (current != null && running) {
                    Surface(Modifier.weight(1f), shape = RoundedCornerShape(16.dp), color = Ink.copy(alpha = .94f)) {
                        Column(Modifier.padding(horizontal = 22.dp, vertical = 16.dp)) {
                            Text(when (current.priority) {
                                FeedbackPriority.INFO -> "주변 안내"
                                FeedbackPriority.CAUTION -> "보행 주의"
                                FeedbackPriority.URGENT -> "위험 주의"
                            }, color = if (current.priority == FeedbackPriority.INFO) Mint else Color(0xFFFFD27B), fontSize = 15.sp)
                            Text(current.message, color = Color.White, fontSize = 30.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                } else Spacer(Modifier.weight(1f))
                Button(onClick = { if (running) pause() else start() }, shape = RoundedCornerShape(16.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFF6FAF7), contentColor = Ink),
                    modifier = Modifier.widthIn(min = 180.dp).heightIn(min = 88.dp).semantics {
                        contentDescription = if (running) "인식 일시정지" else "인식 다시 시작"
                    }) { Text(if (running) "Ⅱ 일시정지" else "▶ 다시 시작", fontSize = 24.sp, fontWeight = FontWeight.Bold) }
            }
        }
    }
}
