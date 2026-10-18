package com.example.blindwalk

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.Surface
import com.example.blindwalk.ui.CameraScreen
import com.example.blindwalk.ui.theme.BlindWalkTheme

// 앱 진입점: 공통 테마 안에서 테스트 화면을 실행한다.
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { BlindWalkTheme { Surface { CameraScreen() } } }
    }
}
