package com.example.blindwalk

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.SystemBarStyle
import androidx.compose.material3.Surface
import androidx.compose.ui.graphics.Color
import com.example.blindwalk.ui.CameraScreen
import com.example.blindwalk.ui.theme.BlindWalkTheme

// 앱을 열면 가로 카메라 화면을 표시한다.
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
            requestPermissions(arrayOf(android.Manifest.permission.BLUETOOTH_CONNECT, android.Manifest.permission.BLUETOOTH_SCAN), 101)
        }
        enableEdgeToEdge(statusBarStyle = SystemBarStyle.dark(0), navigationBarStyle = SystemBarStyle.dark(0))
        setContent { BlindWalkTheme(darkTheme = true, dynamicColor = false) { Surface(color = Color.Black) { CameraScreen() } } }
    }
}
