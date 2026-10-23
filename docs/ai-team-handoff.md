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
  → 4:3 원본 영역·방향 해석
  → models/active/ 모델 기반 AI 파이프라인 (YOLO11n-seg + MiDaS Depth)
  → 프레임 내 객체별 Detection 인스턴스 생성 (bbox, contour, distance_m, class_name)
  → app/src/main/python/frame_interface.py
       build_frame(frame_id, objects=[Detection, ...], situations=...)
  → 공통 Python dict {frame_id, objects, situations}
  → frame_interface.analyze(frame_data)
  → situations에 지정된 상황 모듈의 analyze(frame_data)
  → 판단 결과 목록
  → Kotlin 음성/진동 안내
```

`frame_interface.py`는 **카메라 원본을 받는 파일이 아니라 추론 후 예측 결과(`Detection` 목록)를 정리할 파일**이다.
`build_frame`은 `objects` (`List[Detection]`)를 받아 공통 `frame_data`를 구성한다.
동일 모델을 각 상황 모듈에서 중복 실행하지 않고 공통 추론 계층에서 실행하여 `frame_data`로 공급한다.

| Python 파일 (app/src/main/python/) | 향후 담당 |
| --- | --- |
| detection.py | 표준 `Detection` 데이터클래스 (`id`, `class_name`, `confidence`, `distance_m`, `bbox`, `contour`) |
| frame_interface.py | 같은 프레임의 예측(`objects`)을 정리, 분석할 situations 선택·호출 |
| tactile_anomaly.py | 점자블록 파손·가림·단절 등 이상 판단 |
| tactile_context.py | 점형블록 주변 계단·횡단보도·엘리베이터 등 분석 |
| walking_hazard.py | 턱·계단·장애물·노면 위험 판단 |
| overhead_hazard.py | 나뭇가지·돌출 간판 등 머리 높이 장애물 판단 |

공통 결과의 표준 형태:

```python
from detection import Detection

frame_data = {
    "frame_id": 1,
    "objects": [
        Detection(
            id=1,
            class_name="stairs",
            confidence=0.91,
            distance_m=1.8,
            bbox=[215, 306, 458, 471],
            contour=[[215, 306], ...],
        )
    ],
    "situations": ["WALKING_HAZARD"],
}
```

- `objects`: 모든 검출 객체는 `bbox`와 `contour`를 담으며, `depth.onnx`를 통해 추정한 `distance_m`을 가진다.
- `situations`: 확정된 위험이 아니라 **어떤 분석 모듈을 호출할지** 뜻한다.
- 모델 가중치는 `models/active/`에 등록되어 있으며, 클래스는 모델의 `model.names`에서 동적으로 로드된다.

## 7. AI 팀과 다음에 확정할 사항

- 안드로이드 실기기(Kotlin/Chaquopy) 상에서의 실시간 프레임 버퍼 전달 및 TFLite/ONNX 실행 엔진 최종 융합
- 2·3·4 상황 모듈(`tactile_context`, `walking_hazard`, `overhead_hazard`)의 세부 판단 구현. 1번은 이번 범위에서 제외
- 상황 판단 결과 생성과 Kotlin TTS/진동 연결 구현. 공통 반환 항목은 contracts.md와 situation-handoff.md를 따른다

## 클래스 기반 분석 대상 선택 추가
Python build_frame은 situations 생략 시 2·3·4 분석 대상을 자동 선택한다. 규칙은 docs/contracts.md를 따른다. 전체 objects를 유지하며 위험 판단과 음성·진동은 수행하지 않는다. 카메라와 AI의 실시간 연결은 여전히 TODO다.

2번 담당자의 상세 개발 안내와 공통 결과·우선순위 계약: [상황 판단 핸드오프](situation-handoff.md).
