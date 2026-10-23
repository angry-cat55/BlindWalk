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
            class_name="tactile_dot",
            confidence=0.92,
            distance_m=1.2,
            bbox=[100, 150, 250, 400],
            contour=[[100, 150], [250, 150], [250, 400], [100, 400]],
        ),
        # ...
    ],
    "situations": ["TACTILE_CONTEXT"],
}
```

- `frame_id`: 같은 촬영 프레임의 예측을 묶는 식별자. (1, 2, 3...)
- `objects`: 검출된 `Detection` 객체들의 리스트 (`List[Detection]`).
  - `id`: 프레임 간 ByteTrack 다중 객체 추적(MOT)에 의해 유지되는 고유 추적 ID (`track_id`, 1, 2, ...). 유효한 추적값이 있는 경우 연속 프레임의 ID를 사용하며, 추적값이 없으면 프레임 내 순번으로 대체된다. 재시작·추적 단절 후 동일성을 보장하지 않는다.
  - `class_name`: 모델의 메타데이터(`model.names`)로부터 동적으로 인식된 클래스명. (기본 활성 18종 Master: `tactile_line`, `tactile_dot`, `stairs`, `curb`, `crosswalk`, `bollard`, `pole`, `tree_trunk`, `bicycle`, `movable_signage`, `vehicle`, `person`, `traffic_light`, `facility`, `overhang`, `elevator`, `elevator_sign`, `toilet_sign`)
  - `confidence`: 검출 신뢰도 (0.0 ~ 1.0)
  - `distance_m`: `Optional[float]`. 깊이 추정 AI(`depth.onnx`) 기반 미터(m) 단위 추정 거리. 모델 없음·깊이 추론 실패·유효하지 않은 깊이값은 `None`이며 직렬화 시 `null`이다. 기본 거리로 대체하지 않는다. 거리 계산·직렬화에서는 정밀도를 유지하고, 표시 문구에서만 반올림한다. 점형 판단은 거리 미상·음수·비유한 값을 병합 전에 제외한다.
  - `bbox`: 원본 4:3 픽셀 좌표계 기준 경계상자 `[x1, y1, x2, y2]` (전 객체 공통)
  - `contour`: 외곽선 다각형 꼭짓점 좌표 목록 `[[x, y], [x, y], ...]` (세그멘테이션 마스크 보유 객체)
- `situations`: 실행할 분석 종류 목록. 확정된 위험을 의미하지 않으며 여러 상황을 동시에 지정할 수 있다. (생략하면 아래 규칙으로 자동 선택, 직접 지정한 빈 목록은 자동 선택하지 않음)
- 상황 이름: `TACTILE_ANOMALY`, `TACTILE_CONTEXT`, `WALKING_HAZARD`, `OVERHEAD_HAZARD`.

## 함수와 담당 범위
- `frame_interface.build_frame(frame_id, objects=None, situations=None)`: AI 결과(`List[Detection]`)를 받아 표준 `frame_data` 딕셔너리로 패키징한다.
- `frame_interface.analyze(frame_data)`: situations에 지정된 모듈을 각각 호출하고 반환 목록을 합친다. 각 모듈은 `frame_data["objects"]`의 `Detection` 객체들을 검사하여 위험을 판단한다.
- `frame_interface.run_test(situation)`: 버튼 연결 확인 전용. 빈 프레임에 상황 하나를 직접 지정한 뒤 analyze를 호출한다. AI 기반 상황 판단이 아니다.
- `tactile_context.analyze(frame_data)`: 가운데 1/3의 5m 이내 점형 구역 중 가장 가까운 것을 분석한다. 선형 접촉·세로 위치는 선택 조건이 아니다. walking_hazard는 아래 3번 정책을 구현했고, 1·4번은 TODO 상태다.
- 판단 결과: 2·3번 판단은 아래 공통 반환 계약으로 결과를 생성한다. 1·4번은 빈 목록을 반환한다. 빈 결과는 안전하다는 의미가 아니다.

## 호출 흐름
보존된 테스트 함수: `PythonBridge → run_test → 공통 입력 구성 → 해당 Python 모듈 → 빈 목록`. 현재 UI에서는 호출하지 않는다.
보존된 Mock 테스트 함수: `PythonBridge → mock_inference.infer → 고정 Mock 문자열`.
목표: `카메라 → 하나 이상의 AI 예측 → build_frame → analyze → 해당 상황 모듈 → 결과 → Kotlin 음성·진동`.

현재 UI 흐름은 `메인 → 시작 → CameraX Preview + 원본 선택 → AiFrameInput TODO → 중지/뒤로 → 메인`이다. 카메라와 Python 사이의 프레임 전달, 실제 모델 추론, 앱의 실시간 AI 연결과 자동 피드백은 구현하지 않는다. Python build_frame의 클래스 기반 상황 선택은 구현되어 있으나 위험 판단은 아니다.
Mock 문자열을 실제 AI 결과로 취급하지 않는다. 계약 변경 시 이 문서와 AGENTS.md를 함께 수정한다.

## 실제 서비스로 바꿀 때의 진입점
현재 `PythonBridge.infer()`와 `PythonBridge.analyze(situation) → run_test()`는 테스트 전용 진입점이다.
실제 추론 연결을 검증한 뒤 Mock 파일과 `run_test()`를 제거하고, Bridge는 실제 입력과 결과 전달을 담당하도록 수정한다.
공통 처리의 `build_frame → analyze → 각 모듈의 analyze(frame_data)` 경로는 유지·구현한다.
사용자의 시작 동작에서 이 경로를 호출할 실시간 처리 연결은 아직 없다. 버튼 전용 테스트는 제거·갱신하되 공통 모듈 호출 계약 검증은 유지한다.

## 클래스 기반 상황 선택
`build_frame()`은 situations를 생략하거나 None으로 주면 아래 순서로 분석 대상을 선택한다.

| 분석 종류 | 탐지 클래스 조건 |
| --- | --- |
| TACTILE_CONTEXT (2번) | tactile_dot |
| WALKING_HAZARD (3번) | stairs, curb, bollard, pole, tree_trunk, bicycle, movable_signage, vehicle, person, facility 중 하나 이상 |
| OVERHEAD_HAZARD (4번) | overhang |

여러 상황을 동시에 선택할 수 있고 각 상황은 한 번만 포함한다.
빈 객체 목록이나 조건에 없는 클래스만 있으면 situations는 빈 목록이다.
TACTILE_ANOMALY는 자동 선택하지 않는다. 기존 수동 테스트 호출은 유지한다.
객체의 신뢰도·거리·위치로 위험을 확정하지 않으며, 전체 objects를 각 모듈에 전달한다.
objects가 지정되면 model_results보다 우선한다. model_results만 제공해도 같은 분류를 수행한다.
build_frame은 데이터를 반환할 뿐 모듈을 실행하지 않는다. 호출자는 analyze(frame_data)를 호출해야 한다.
analyze는 선택된 모듈의 반환 목록을 합치며 음성·진동을 직접 실행하지 않는다.

## 공통 반환 계약 (2·3번에 구현, 앱 전달은 미구현)
각 상황 모듈은 아래 항목을 가진 딕셔너리의 목록을 반환한다. 안내 근거가 없으면 []다.

| 키 | 형식·의미 |
| --- | --- |
| situation | str: TACTILE_CONTEXT / WALKING_HAZARD / OVERHEAD_HAZARD |
| object_id | int: 입력 Detection.id 중 안내의 주 대상 |
| message | str: 화면·TTS용 비어 있지 않은 한국어 안내 |
| priority | str: INFO / CAUTION / URGENT |

INFO는 환경 정보, CAUTION은 주의 필요, URGENT는 즉시 대응 필요를 뜻한다.
모듈별 등급을 고정하지 않는다. 각 모듈의 실제 조건과 임계값은 별도 검증한다.
analyze는 목록을 합칠 뿐 등급 정렬·중복 제거·동률 처리를 하지 않는다.
2·3번 판단의 결과 생성·형식 테스트는 구현했다. Kotlin 전달·공통 안내 처리는 아직 구현하지 않았다.
객체 ID는 추적 실패 시 프레임 내 순번으로 대체될 수 있고, distance_m은 깊이 실패 시 None이다. 지속 ID·유효 미터 거리로 무조건 신뢰하지 않으며, 거리 미상은 5m 이내 판정이나 가장 가까운 대상 선정의 근거로 사용하지 않는다.
2번 담당자의 입력·구현 범위·반환 예시·남은 연결 작업은 [상황 판단 핸드오프](situation-handoff.md)를 참고한다.

## 3번 일반 보행 판단: 현재 구현
- 입력 크기: build_frame(..., image_width=너비, image_height=높이). 기존 인자 뒤 키워드 전용 선택 인자다. 둘 다 제공할 때 frame_data에 추가한다.
- 크기는 bbox·contour 좌표계에 대응하는 입력 영상 크기이며 모델 텐서·Preview 위젯 크기가 아니다. PC process_frame은 실제 img_bgr.shape를 전달한다.
- 크기가 없거나 비유한 값·0 이하이면 3번은 []를 반환한다. 기존 호출과 2번 담당 모듈은 변경하지 않았다.
- 객체 bbox 하단 15%를 영상 범위로 자른 뒤 분석한다. 잘못된 bbox는 제외한다.
- tactile_line/tactile_dot의 유효 contour들을 점자블록 영역으로 사용한다. contour가 없으면 해당 블록은 건너뛰며 bbox로 영역을 추측하지 않는다.
- 중앙 진행 영역은 영상 비율 (0.4,0.5), (0.6,0.5), (0.8,1.0), (0.2,1.0)의 사다리꼴이다. 실제 보행 경로 추정 결과가 아니다.
- 객체 하단의 10×10 격자 중심을 검사해 영역과의 겹침을 근사한다. 100개 중 10개를 초과해 겹쳐야 선택한다. 여러 블록의 중복 영역은 중복 집계하지 않는다.
- 점자블록 겹침을 우선하고, 아니면 중앙 영역을 확인한다. 두 조건 모두 맞아도 객체별 결과 하나만 반환한다.
- 우선순위: vehicle→URGENT / person·facility→INFO / stairs·curb·bollard·pole·tree_trunk·bicycle·movable_signage→CAUTION.
- 클래스별 초기 안내 정책이며 거리·접근 속도·충돌 임박을 측정한 등급이 아니다. confidence 추가 필터 없이 AI 출력 객체를 사용한다.
- 문구: '점자블록 위 볼라드', '전방에 자전거'처럼 위치와 짧은 객체명만 사용한다. 그룹 클래스의 세부 종류를 추측하지 않는다.
- 상태 저장·프레임 간 중복 제한·등급 정렬·TTS·진동은 구현하지 않았다. 객체 입력 순서대로 반환한다.
- 계단·연석도 동일한 하단 기준을 사용한 초기 구현이다. 실제 영상에서 별도 검증해야 한다. 15%·10%·사다리꼴·표본 격자는 검증 전 실험 기준이다.
- OpenCV·NumPy를 추가하지 않고 Python 표준 라이브러리만 사용한다. 실제 영상 정확도와 모바일 실행 속도는 미검증이다.
