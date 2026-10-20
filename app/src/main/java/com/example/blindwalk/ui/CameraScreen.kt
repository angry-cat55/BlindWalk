package com.example.blindwalk.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.example.blindwalk.camera.CameraPreview

/** 가로 메인→시작→카메라→중지 흐름. 실제 AI 판단·보행 안내는 연결하지 않는다. */
@Composable
fun CameraScreen() {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    var running by remember { mutableStateOf(false) }
    var streaming by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("") }
    var permissionDenied by remember { mutableStateOf(false) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        running = granted
        permissionDenied = !granted
        message = if (granted) "" else "카메라 권한이 필요합니다."
    }
    DisposableEffect(owner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) { running = false; streaming = false }
        }
        owner.lifecycle.addObserver(observer)
        onDispose { owner.lifecycle.removeObserver(observer) }
    }
    BackHandler(enabled = running) { running = false; streaming = false }
    val padding = Modifier.fillMaxSize().safeDrawingPadding().padding(20.dp)
    if (!running) {
        Column(padding.verticalScroll(rememberScrollState()), horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(20.dp, Alignment.CenterVertically)) {
            Text("BlindWalk", color = MaterialTheme.colorScheme.primary, fontSize = 48.sp,
                fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
            if (message.isNotEmpty()) Text(message, fontSize = 20.sp,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
            Button(onClick = {
                streaming = false; message = ""
                if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) running = true
                else permission.launch(Manifest.permission.CAMERA)
            }, shape = RoundedCornerShape(16.dp), modifier = Modifier.widthIn(min = 280.dp, max = 440.dp).heightIn(min = 88.dp)
                .semantics { contentDescription = "카메라 시작" }) { Text("시작", fontSize = 32.sp) }
            if (permissionDenied) TextButton(onClick = {
                context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}")))
            }) { Text("카메라 권한 설정", fontSize = 20.sp) }
        }
    } else {
        BoxWithConstraints(padding) {
            val previewWidth = minOf(maxHeight * 4f / 3f, maxWidth * .63f)
            Row(Modifier.fillMaxSize(), verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                CameraPreview(Modifier.width(previewWidth).aspectRatio(4f / 3f).clearAndSetSemantics {},
                    onReady = { streaming = true }, onError = { running = false; streaming = false; message = it })
                Column(Modifier.weight(1f).fillMaxHeight().verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(24.dp, Alignment.CenterVertically)) {
                    Text("BlindWalk", fontSize = 28.sp, fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary, modifier = Modifier.semantics { heading() })
                    Text(if (streaming) "카메라 실행 중" else "카메라 준비 중", fontSize = 26.sp,
                        fontWeight = FontWeight.Bold, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                    Button(onClick = { running = false; streaming = false },
                        shape = RoundedCornerShape(16.dp),
                        modifier = Modifier.fillMaxWidth().heightIn(min = 88.dp)
                            .semantics { contentDescription = "카메라 중지, 메인 화면으로 이동" }) {
                        Text("중지", fontSize = 32.sp)
                    }
                }
            }
        }
    }
}
