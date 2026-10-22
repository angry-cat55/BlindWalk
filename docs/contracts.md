# Python 상황 판단의 임시 계약

파일별 전체 흐름과 AI 담당자 연결 지점은 [AI 팀 공유 문서](ai-team-handoff.md)에 정리한다. 이 문서는 공통 데이터 계약의 기준이다.

## 카메라→향후 AI 연결점 (AI 예측 전)
본 앱의 `camera/CameraPreview.kt`가 `AiFrameInput.onFrameSelected(frameId: Long, image: ImageProxy)`를 분석 전용 스레드에서 동기 호출한다. 파일은 `app/src/main/java/com/example/blindwalk/camera/AiFrameInput.kt`다. 현재 함수 본문은 TODO이며 데이터를 Python으로 전송하지 않는다.

| 전달 데이터 | 형식·의미 |
| --- | --- |
| frameId | Long, 선택된 프레임에만1씩 증가. 카메라 재시작 시1부터 시작 |
| image | CameraX ImageProxy, 복사·모델 전처리하지 않은 원본 프레임 |
| image.width/height | 원본 버퍼 크기. 모델 입력 크기가 아님 |
| image.cropRect | 공통 ViewPort의 유효 촬영 영역 |
| image.imageInfo.rotationDegrees | 원본을 올바른 방향으로 해석할 회전값(도) |
| image.imageInfo.timestamp | 카메라 촬영 timestamp(ns). epoch시각으로 해석하지 않음 |
| image.format / image.planes | 원본 포맷·Plane 버퍼·rowStride/pixelStride. 현재 CameraX 기본 YUV_420_888, 모델 색상 계약은 아님 |

가로4:3은 cropRect 적용 후 rotationDegrees로 방향을 맞춘 유효 영상 기준이다. 버퍼 전체가 가로4:3이라고 가정하지 않는다. 크기 조절·RGB 변환·정규화·텐서화·Python 변환은 이번 범위에 없고 AI 담당자와 추후 결정한다.

프레임 선택은 단조 시각 기준 최소200ms 간격(최대 약5장/초)이다. 지연 시 누락분을 몰아보내지 않는다. Preview30FPS는 별도 목표이며 AI 추론5FPS를 뜻하지 않는다.
콜백이 반환되면 카메라가 반드시 image.close()한다. image·planes·ByteBuffer를 저장하거나 다른 스레드에서 나중에 읽지 않는다. 향후 비동기 추론이 필요하면 콜백 안에서 필요한 데이터의 소유 복사본을 만들고 단일 처리/최신 프레임 정책을 별도 설계한다. 지금은 복사나 큐를 추가하지 않는다.

아래 Python frame_data는 **추론 후 예측 결과** 계약이며 위 카메라 원본 계약과 다르다.

AI 인지 파트의 공통 인터페이스 규약이다. 인스턴스 세그멘테이션과 MiDaS 단안 깊이 추정을 결합하여 각 객체의 위치(`bbox`), 외곽선(`contour`), 추정 거리(`distance_m`)를 제공한다.

## 공통 입력
모든 상황 모듈은 `analyze(frame_data)`를 사용하고 Python 목록을 반환한다.

```python
from detection import Detection

frame_data = {
    "frame_id": 1,
    "objects": [
        Detection(
            id=1,
            class_name="tactile_line",
            confidence=0.92,
            distance_m=1.2,
            bbox=[100, 150, 250, 400],
            contour=[[100, 150], [250, 150], [250, 400], [100, 400]],
        ),
        # ...
    ],
    "situations": ["TACTILE_ANOMALY", "WALKING_HAZARD"],
}
```

- `frame_id`: 같은 촬영 프레임의 예측을 묶는 식별자. (1, 2, 3...)
- `objects`: 검출된 `Detection` 객체들의 리스트 (`List[Detection]`).
  - `id`: 프레임 내 객체 고유 번호 (1, 2, ...)
  - `class_name`: 모델의 메타데이터(`model.names`)로부터 동적으로 인식된 클래스명. (기본 활성 16종: `tactile_line`, `tactile_dot`, `stairs`, `curb`, `caution_zone`, `bollard`, `barricade`, `pole`, `tree_trunk`, `bicycle`, `movable_signage`, `vehicle`, `person`, `traffic_light`, `facility`, `overhang`)
  - `confidence`: 검출 신뢰도 (0.0 ~ 1.0)
  - `distance_m`: 깊이 추정 AI(`depth.onnx`) 기반 미터(m) 단위 추정 거리
  - `bbox`: 원본 4:3 픽셀 좌표계 기준 경계상자 `[x1, y1, x2, y2]` (전 객체 공통)
  - `contour`: 외곽선 다각형 꼭짓점 좌표 목록 `[[x, y], [x, y], ...]` (세그멘테이션 마스크 보유 객체)
- `situations`: 실행할 분석 종류 목록. 확정된 위험을 의미하지 않으며 여러 상황을 동시에 지정할 수 있다. (미정인 경우 빈 리스트)
- 상황 이름: `TACTILE_ANOMALY`, `TACTILE_CONTEXT`, `WALKING_HAZARD`, `OVERHEAD_HAZARD`.

## 함수와 담당 범위
- `frame_interface.build_frame(frame_id, objects=None, situations=None)`: AI 결과(`List[Detection]`)를 받아 표준 `frame_data` 딕셔너리로 패키징한다.
- `frame_interface.analyze(frame_data)`: situations에 지정된 모듈을 각각 호출하고 반환 목록을 합친다. 각 모듈은 `frame_data["objects"]`의 `Detection` 객체들을 검사하여 위험을 판단한다.
- `frame_interface.run_test(situation)`: 버튼 연결 확인 전용. 빈 프레임에 상황 하나를 직접 지정한 뒤 analyze를 호출한다. AI 기반 상황 판단이 아니다.
- 네 상황 모듈의 `analyze(frame_data)`: 현재 TODO와 `return []`만 있다. 향후 세부 위험 판단을 담당한다.
- 판단 결과: 현재 빈 목록. 항목의 필드는 미정이다. 빈 결과는 안전하다는 의미가 아니다.

## 호출 흐름
보존된 테스트 함수: `PythonBridge → run_test → 공통 입력 구성 → 해당 Python 모듈 → 빈 목록`. 현재 UI에서는 호출하지 않는다.
보존된 Mock 테스트 함수: `PythonBridge → mock_inference.infer → 고정 Mock 문자열`.
목표: `카메라 → 하나 이상의 AI 예측 → build_frame → analyze → 해당 상황 모듈 → 결과 → Kotlin 음성·진동`.

현재 UI 흐름은 `메인 → 시작 → CameraX Preview + 원본 선택 → AiFrameInput TODO → 중지/뒤로 → 메인`이다. 카메라와 Python 사이의 프레임 전달, 실제 모델 추론, 모델 결과 변환, 상황 자동 선택, 자동 피드백은 구현하지 않는다.
Mock 문자열을 실제 AI 결과로 취급하지 않는다. 계약 변경 시 이 문서와 AGENTS.md를 함께 수정한다.

## 실제 서비스로 바꿀 때의 진입점
현재 `PythonBridge.infer()`와 `PythonBridge.analyze(situation) → run_test()`는 테스트 전용 진입점이다.
실제 추론 연결을 검증한 뒤 Mock 파일과 `run_test()`를 제거하고, Bridge는 실제 입력과 결과 전달을 담당하도록 수정한다.
공통 처리의 `build_frame → analyze → 각 모듈의 analyze(frame_data)` 경로는 유지·구현한다.
사용자의 시작 동작에서 이 경로를 호출할 실시간 처리 연결은 아직 없다. 버튼 전용 테스트는 제거·갱신하되 공통 모듈 호출 계약 검증은 유지한다.
