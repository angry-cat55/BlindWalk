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
        enableEdgeToEdge(statusBarStyle = SystemBarStyle.dark(0), navigationBarStyle = SystemBarStyle.dark(0))
        setContent { BlindWalkTheme(darkTheme = true, dynamicColor = false) { Surface(color = Color.Black) { CameraScreen() } } }
    }
}
