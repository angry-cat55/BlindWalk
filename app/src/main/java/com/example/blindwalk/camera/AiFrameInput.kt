package com.example.blindwalk.camera

import androidx.camera.core.ImageProxy

/** AI 담당자의 연결 지점. 현재는 모델 실행·변환·Python 전달을 하지 않는다. */
object AiFrameInput {
    // 분석 전용 스레드에서 동기 호출된다. 반환 후 image/planes를 보관하거나 읽으면 안 된다.
    // cropRect와 imageInfo.rotationDegrees 적용 후 유효 영상이 가로 4:3이다.
    fun onFrameSelected(frameId: Long, image: ImageProxy) {
        // TODO: 모델 선정 후 원본 영상·메타데이터를 이용해 공통 추론 계층에 연결한다.
        // 입력 크기·정규화·색상 변환·버퍼 복사 방식은 AI 담당자와 협의한다.
    }
}
