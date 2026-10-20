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

// 가로 메인·카메라 화면을 공통 테마 안에서 실행한다.
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(statusBarStyle = SystemBarStyle.light(0, 0), navigationBarStyle = SystemBarStyle.light(0, 0))
        setContent { BlindWalkTheme(darkTheme = false, dynamicColor = false) { Surface(color = Color.White) { CameraScreen() } } }
    }
}
