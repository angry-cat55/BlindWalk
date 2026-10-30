plugins {
    alias(libs.plugins.chaquopy)
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "com.example.blindwalk"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.example.blindwalk"
        minSdk = 24
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            optimization {
                enable = false
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    buildFeatures {
        compose = true
    }
}

// Python 실행 환경만 포함한다. AI 모델·외부 Python 패키지는 추가하지 않는다.
chaquopy {
    defaultConfig { version = "3.14" }
}

dependencies {
    implementation("com.github.mik3y:usb-serial-for-android:3.8.0")
    implementation(libs.litert)
    implementation(libs.litert.gpu)
    implementation(libs.litert.gpu.api)
    implementation(libs.onnxruntime)
    implementation(libs.androidx.camera.camera2)
    implementation(libs.androidx.camera.lifecycle)
    implementation(libs.androidx.camera.view)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    testImplementation(libs.junit)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.junit)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
    debugImplementation(libs.androidx.compose.ui.tooling)
}

// 원본 가중치는 models/active 한 곳에 둔다. 빌드할 때만 앱 assets로 복사한다.
val prepareAiAssets by tasks.registering(Sync::class) {
    from(rootProject.file("models/active")) {
        include("yolo11n_seg_18cls.tflite", "depth.onnx")
        into("ai")
    }
    into(layout.buildDirectory.dir("generated/aiAssets"))
}
android.sourceSets["main"].assets.directories.add(layout.buildDirectory.dir("generated/aiAssets").get().asFile.absolutePath)
tasks.named("preBuild").configure { dependsOn(prepareAiAssets) }
