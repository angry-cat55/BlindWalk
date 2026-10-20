# AI 팀 공유: 카메라 입력부터 상황 판단까지

## 1. 지금 구현된 범위

본 앱은 가로 모드의 메인/촬영 화면과 카메라 원본 프레임 선택까지만 구현했다.
메인에는 카메라가 없고, 시작을 누르면 후면 Preview와 프레임 선택이 켜진다. 중지·뒤로·백그라운드 이동 시 종료한다.
AI 모델 설치·추론·전처리·Python 영상 전달·자동 상황 판단·자동 음성/진동 안내는 구현하지 않았다.
`jh-test`의 ARCore 실험은 본 앱과 별개이며 여기에는 연결하지 않는다.

## 2. 현재 실제 파일 호출 흐름

아래 Kotlin 경로의 기준은 `app/src/main/java/com/example/blindwalk/`이다.

```text
MainActivity.kt
  └─ ui/CameraScreen.kt
       ├─ 메인: BlindWalk 워드마크 + 시작 버튼 (카메라 꺼짐)
       └─ 시작 → CAMERA 권한 확인 → 촬영 화면
            └─ camera/CameraPreview.kt
                 ├─ 후면 카메라 → Preview → PreviewView → 화면 표시
                 │                          (30FPS 목표)
                 └─ 같은 카메라 → ImageAnalysis → 단일 분석 스레드
                      └─ camera/FrameGate.kt
                           ├─ 직전 선택 후 200ms 미만 → 선택하지 않음
                           └─ 200ms 이상 → 최신 프레임 한 장 선택
                                └─ camera/AiFrameInput.kt
                                     onFrameSelected(frameId, image)
                                     현재 본문 TODO: 실제 AI 호출 없음
                                └─ 콜백 반환 → image.close()
```

- **촬영/분석 연결 파일:** `camera/CameraPreview.kt`. CameraX `ProcessCameraProvider`에 후면 카메라의 Preview와 ImageAnalysis를 함께 생명주기 바인딩한다.
- **화면 표시:** Preview가 `PreviewView.surfaceProvider`로 연결된다. 화면 표시를 위해 Python을 거치지 않는다.
- **프레임 선택:** `FrameGate.kt`가 단조 경과 시각으로 간격을 제한한다. 선택 횟수는 최대 약5장/초이고, 실제 추론 속도를 의미하지 않는다. 카메라 공급이 늦거나 향후 소비자가 느리면 더 낮아진다.
- **적체 방지:** `STRATEGY_KEEP_ONLY_LATEST`로 최신 프레임만 유지하고 별도의 처리 큐는 만들지 않는다. 밀린 프레임 수량을 나중에 보충하지 않는다.
- **반환:** 선택하지 않은 프레임·선택한 프레임·예외 발생 프레임 모두 `finally`에서 닫는다.

## 3. AI 담당자가 연결할 파일과 함수

정확한 파일:

`app/src/main/java/com/example/blindwalk/camera/AiFrameInput.kt`

```kotlin
fun onFrameSelected(frameId: Long, image: ImageProxy)
```

`CameraPreview.kt`가 이 함수를 분석 전용 스레드에서 **동기 호출**한다. 현재 반환값은 `Unit`이며 본문은 TODO다.
이미지를 파일로 저장해서 주거나 서버로 보내는 구조가 아니다. Kotlin 메모리 안의 원본 프레임 핸들을 잠깐 전달한다.
지금 Python 상황 모듈에는 이 영상이 전달되지 않는다.

## 4. 지금 받는 데이터 형태

| 값 | Kotlin/Android 형식 | 의미 |
| --- | --- | --- |
| frameId | Long | 선택된 프레임 번호. 선택할 때만 증가하며 카메라 재시작 시1부터. 전역 고유 ID 아님 |
| image | androidx.camera.core.ImageProxy | CameraX 원본 영상과 메타데이터에 접근하는 핸들 |
| image.width, image.height | Int | 원본 영상 버퍼의 가로·세로. 모델 입력 해상도로 고정하지 않음 |
| image.cropRect | android.graphics.Rect | Preview와 공유하는 유효 촬영 영역. 원본 버퍼 기준 좌표 |
| image.imageInfo.rotationDegrees | Int | 원본을 올바른 방향으로 해석할 회전값(도) |
| image.imageInfo.timestamp | Long | 카메라 촬영 timestamp, 나노초. Unix epoch 시각으로 해석하지 않음 |
| image.format | Int | 현재 CameraX 기본 YUV_420_888(format=35). 모델 입력 색상 형식이 아님 |
| image.planes | Array<ImageProxy.PlaneProxy> | Y/U/V Plane의 ByteBuffer와 rowStride, pixelStride |

실기기에서 관찰한 한 예는 `buffer=640×480`, `cropRect=(0,0)-(640,480)`, `rotationDegrees=0`, `format=35`였다.
이는 **관찰 예시이며 고정된 모델 입력 계약이 아니다**. 해상도·stride·회전은 받은 프레임의 메타데이터로 확인해야 한다.
Plane 버퍼를 가로×세로로 단순 연결하거나 행 간격·픽셀 간격을 무시하면 올바른 영상이 되지 않을 수 있다.

### 4:3과 방향 규칙

Preview와 ImageAnalysis는 공통 `ViewPort(4:3)`를 사용한다.
`cropRect`에 해당하는 영역을 사용하고 `rotationDegrees`를 반영한 **유효 영상이 가로4:3**이다.
원본 버퍼 전체가 언제나 가로4:3이라고 가정하지 않는다. 현재 연결점은 잘라낸 별도 Bitmap을 주지 않으며, 원본과 영역/회전 정보만 준다.
화면 좌표·원본 버퍼 좌표·향후 모델 입력 좌표는 서로 다르다. 모델 선정 후 crop/회전/resize/letterbox와 bbox 역변환 규칙을 함께 정해야 한다.

## 5. 프레임 수명과 처리 규칙

1. 카메라 측이 `ImageProxy`를 소유한다. AI 담당자는 동기 콜백 안에서만 원본을 읽는다.
2. 콜백이 끝나면 `CameraPreview.kt`가 `image.close()`한다. 소비자가 별도로 닫지 않는다.
3. `image`, `planes`, Plane의 `ByteBuffer` 참조를 저장하거나 다른 스레드/Python으로 넘겨 나중에 읽지 않는다.
4. 향후 비동기 추론이 필요하면 콜백 안에서 필요한 데이터의 **소유 복사본**을 만들고, 처리 중에는 입력을 버리는 등 최신 프레임 정책을 별도 연결해야 한다. 이번에는 복사·전처리·비동기 추론을 구현하지 않았다.
5. Preview는 분석 전용 스레드의 모델 실행과 분리하되, 향후 무거운 추론을 추가하면 CPU/GPU 경합으로 Preview도 느려질 수 있으므로 다시 측정한다.

## 6. 모델 선정 후 연결할 목표 흐름 — 아직 미구현

```text
AiFrameInput.onFrameSelected(frameId, image)
  → 원본 영역·방향 해석
  → 모델 입력 전처리 [크기/색상/정규화 미정]
  → 공통 추론 계층 [실행 언어·엔진·파일명 미정]
  → 하나 이상의 모델 예측 [동일 프레임 번호와 촬영 시각으로 대응]
  → app/src/main/python/frame_interface.py
       build_frame(frame_id, model_results)
  → 공통 Python dict {frame_id, objects, situations}
  → frame_interface.analyze(frame_data)
  → situations에 지정된 상황 모듈의 analyze(frame_data)
  → 판단 결과 목록
  → Kotlin 음성/진동 안내 [결과 계약·연결 미구현]
```

`frame_interface.py`는 **카메라 원본을 받는 파일이 아니라 추론 후 예측 결과를 정리할 파일**이다.
현재 `build_frame`은 model_results를 변환하지 않고 빈 objects/situations를 만든다.
`analyze`의 지정 모듈 호출 골격은 있지만 네 모듈은 아직 TODO와 `return []`뿐이다.
동일 모델을 각 상황 모듈에서 중복 실행하지 않고 공통 추론 계층에서 실행할 계획이다.

| Python 파일 (app/src/main/python/) | 향후 담당 |
| --- | --- |
| frame_interface.py | 같은 프레임의 예측을 공통 objects로 정리, 분석할 situations 선택·호출 |
| tactile_anomaly.py | 점자블록 파손·가림·단절 등 이상 판단 |
| tactile_context.py | 점형블록 주변 계단·횡단보도·엘리베이터 등 분석 |
| walking_hazard.py | 턱·계단·장애물·노면 위험 판단 |
| overhead_hazard.py | 나뭇가지·돌출 간판 등 머리 높이 장애물 판단 |

예정된 공통 결과의 현재 최소 형태:

```python
frame_data = {
    "frame_id": 1,
    "objects": [],
    "situations": [],
}
```

objects의 항목·bbox 좌표계·깊이 단위·판단 결과 항목은 아직 확정하지 않았다.
`situations`는 확정된 위험이 아니라 **어떤 분석 모듈을 호출할지** 뜻한다.
기존 `bridge/PythonBridge.kt`의 infer/analyze는 보존된 Mock/버튼 테스트용이며 현재 카메라 입력이나 실제 AI 실행과 연결되어 있지 않다.

## 7. AI 팀과 다음에 확정할 사항

- 사용할 모델·가중치·실행 엔진·실행 언어(Kotlin 또는 Python).
- 모델 입력 크기·색상 순서·정규화와 crop/회전/resize/letterbox 규칙.
- 비동기 처리에 필요한 복사본의 형식·소유권·최신 프레임 정책.
- 같은 촬영 프레임의 여러 모델 결과를 묶는 방법과 세션 재시작 식별 방법.
- 공통 objects/bbox/깊이/판단 결과 계약. 확정되면 docs/contracts.md도 함께 수정한다.

현재 원본 입력과 미래 AI 결과를 혼동하지 않는 것이 우선이다. 데이터 계약 변경은 팀과 협의한다.
