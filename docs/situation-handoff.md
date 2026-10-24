# 상황 판단 개발 핸드오프 — 2번 담당자 중심

## 먼저 알아둘 현재 상태

이 문서는 사람과 AI 코딩 에이전트가 같은 입력·출력 규칙으로 개발하기 위한 안내다.
작업 전 AGENTS.md, README.md, [공통 계약](contracts.md)을 먼저 읽는다.

- 구현됨: Detection 목록 묶기, 클래스 기반 2·3·4 분석 대상 선택, 점형블록 주변 판단, 선택된 모듈 호출과 반환 목록 합치기.
- 미구현: 세 모듈의 세부 판단, 앱 카메라와 AI의 연결, 결과의 Kotlin 전달, 자동 음성·진동.
- 아래 공통 결과 형식과 우선순위를 따른다. 점형 판단의 결과 생성·형식 테스트는 구현했으며 앱 전달과 구분한다.
- 1번 점자블록 파손·노후·가림 판단은 이번 개발 범위에서 제외한다. 기존 파일과 수동 테스트는 보존한다.

## 파일별 역할과 실행 순서

```text
scripts/ai_pipeline.py
  AI 탐지·추적·거리 추정 → List[Detection]
  → process_frame()에서 frame_interface.build_frame() 호출
      → select_situations(): 클래스명으로 분석 대상 선택
      → {frame_id, objects, situations} 반환

호출자가 frame_interface.analyze(frame_data)를 실행해야 다음 단계로 진행
  → tactile_context.analyze(frame_data)   # 2번
  → walking_hazard.analyze(frame_data)    # 3번
  → overhead_hazard.analyze(frame_data)   # 4번
  → 각 모듈의 반환 목록을 results.extend()로 합쳐 반환
```

build_frame은 모듈을 실행하지 않는다. 현재 AI 스크립트는 frame_data 반환·출력까지이며 analyze 자동 실행은 연결하지 않았다.
본 앱의 CameraPreview → FrameGate → AiFrameInput.onFrameSelected() 경로도 아직 TODO에서 끝난다.
영상에서 보았던 점자블록 중앙 경로선·경로 침범 판단은 현재 저장소 코드에 없다. 이를 전제로 개발하지 않는다.

## 공통 입력: frame_data

```python
frame_data = {
    "frame_id": 42,
    "objects": [Detection(...)],
    "situations": ["TACTILE_CONTEXT", "WALKING_HAZARD"],
}
```

| 필드 | 의미 |
| --- | --- |
| frame_id | 같은 촬영 프레임의 예측을 묶는 정수 식별자 |
| objects | 해당 프레임의 전체 Detection 객체 목록. 딕셔너리 목록이 아님 |
| situations | 실행할 분석 종류. 위험 확정 결과가 아님 |

Detection은 app/src/main/python/detection.py에 있다.

| 속성 | 형식·의미 |
| --- | --- |
| id | int, 추적 ID. 추적값이 없으면 현재 코드가 프레임 내 순번으로 대체하므로 항상 지속 ID라고 가정하면 안 됨 |
| class_name | str, 클래스명. 모델별 숫자 ID 대신 이 이름으로 비교 |
| confidence | float, 객체 탐지 신뢰도. 위험 판단의 신뢰도와는 다름 |
| distance_m | Optional[float], 추정 거리. 깊이 결과가 없거나 유효하지 않으면 None. 점형 판단에서는 병합 전에 제외 |
| bbox | List[int], [x1, y1, x2, y2] 픽셀 좌표 |
| contour | 좌표 쌍 목록 또는 None. 마스크가 없는 경우를 처리해야 함 |

속성은 obj.class_name, obj.bbox처럼 접근한다. 모듈에는 관심 객체만 잘라 보내지 않고 전체 objects를 전달한다.
현재 frame_data에는 이미지 크기·촬영 시각이 없다. 위치를 비율로 비교하거나 시간 조건을 구현하려면 공통 계약 변경을 먼저 협의한다.
640×480은 PC 예제 입력이며 모든 앱 입력의 고정 크기라고 가정하지 않는다.

## 상황 선택 규칙

| 상황 | 자동 선택 조건 | 담당 파일 |
| --- | --- | --- |
| 2 / TACTILE_CONTEXT | tactile_dot이 하나 이상 있음 | app/src/main/python/tactile_context.py |
| 3 / WALKING_HAZARD | 아래 지상 클래스 중 하나 이상 있음 | app/src/main/python/walking_hazard.py |
| 4 / OVERHEAD_HAZARD | overhang이 하나 이상 있음 | app/src/main/python/overhead_hazard.py |

3번 클래스: stairs, curb, bollard, pole, tree_trunk, bicycle, movable_signage, vehicle, person, facility.
선택 순서는 2 → 3 → 4이고 각 상황은 한 번만 들어간다. 이는 안내 우선순위가 아니다.
조건에 맞는 객체가 없으면 situations는 빈 목록이다.
build_frame에 situations를 직접 지정하면 자동 선택하지 않는다. []도 직접 지정한 값으로 취급한다.

## 2번 담당자가 구현할 범위

수정 중심 파일은 tactile_context.py의 analyze(frame_data)다. 반환은 아래 공통 형식의 목록이다.

1. objects에서 tactile_dot과 주변 시설 후보를 찾는다.
2. stairs, crosswalk, curb, elevator, elevator_sign, traffic_light, facility, toilet_sign 등의 위치 관계를 검토한다.
3. 같은 화면에 있다는 이유만으로 점형 블록과 연결된 시설이라고 확정하지 않는다.
4. 안내 근거가 충분할 때 결과를 만들고, 없으면 []를 반환한다.

현재 점형 판단은 가로 가운데 1/3에 중심이 있는 점형 구역 중 5m 이내 가장 가까운 것을 고른다. 선형 접촉이나 세로 위치는 대상 선택 조건이 아니다. 진입선은 선택한 점형에 접촉하고 아래쪽으로 이어지는 선만 후보로 삼으며, 측면 분기선을 임의로 제외하지 않는다. 표지판 안내는 시설 도착으로 확정하지 않고 표지 관찰로 표현한다. 거리값은 계산·직렬화 단계에서 정밀도를 유지한다.

예: 점형 블록 주변의 횡단보도·계단 안내. 표지판만 탐지됐다면 시설 자체가 확인된 것처럼 표현하지 않는다.
traffic_light는 신호 색상 정보가 없으므로 신호가 녹색이거나 건너도 된다고 판단하지 않는다.
모듈에서 AI 모델을 다시 실행하거나 Android TTS·진동을 직접 호출하지 않는다.
구체적인 공간 조건·신뢰도 기준은 담당자가 구현·검증하며, 이 문서가 임계값을 확정하지는 않는다.

## 모든 상황 모듈의 공통 반환 계약

반환은 List[dict]다. 항목 하나는 아래 네 키를 사용한다.

| 키 | 형식 | 의미 |
| --- | --- | --- |
| situation | str | TACTILE_CONTEXT / WALKING_HAZARD / OVERHEAD_HAZARD |
| object_id | int | 안내의 주 대상 Detection.id. frame_data.objects에 있는 객체를 참조 |
| message | str | 화면과 TTS에 사용할 비어 있지 않은 한국어 안내 문장 |
| priority | str | INFO / CAUTION / URGENT 중 하나 |

여러 객체의 관계를 판단하더라도 object_id에는 대표 대상을 넣는다.
예를 들어 점형 블록 주변 계단 안내는 계단을 주 대상으로 정할 수 있다.
해당 결과가 어느 프레임에서 나왔는지는 호출자가 보유한 frame_data.frame_id와 함께 관리한다.

```python
# 형식 설명용 예시다. 현재 모듈이 실제로 생성하는 결과는 아니다.
[
    {
        "situation": "TACTILE_CONTEXT",
        "object_id": 7,
        "message": "점형 블록 주변에 계단이 있습니다.",
        "priority": "INFO",
    }
]
```

결과가 여러 개면 여러 항목을 반환하고, 안내 근거가 없으면 []를 반환한다.
None이나 딕셔너리 하나를 반환하지 않는다. extend는 목록 항목을 합치는 방식이므로 규칙을 맞춰야 한다.
빈 결과는 안전하다는 의미가 아니다.

## 우선순위와 결과 소비

| 값 | 의미 |
| --- | --- |
| INFO | 주변 시설 등 안내할 가치가 있는 환경 정보 |
| CAUTION | 주의가 필요한 상황 |
| URGENT | 즉시 대응이 필요하다고 판단한 상황 |

문자열은 대문자 표기를 사용한다. DEBUG·ERROR는 프로그램 로그 용어이므로 사용하지 않는다.
모듈 종류마다 등급을 고정하지 않는다. 각 모듈은 자신이 확인한 조건에 따라 등급을 정한다.
URGENT 조건은 검증이 필요하다. 현재 거리 환산값만으로 긴급 등급을 확정하지 않는다. 거리 미상(None)을 임의 거리로 대체하지 않는다.

analyze는 우선순위 정렬·중복 제거 없이 결과를 합친다.
여러 URGENT의 순서, 반복 안내 간격, 같은 객체의 상충하는 안내 통합은 공통 안내 처리에서 추후 정한다.
신뢰할 수 있는 거리 정보가 확보된 후 거리 기반 동률 처리를 검토한다. 현재 2→3→4 합치기 순서를 위험 순위로 사용하지 않는다.

목표 연결: results → PythonBridge → Kotlin 공통 안내 처리 → 화면 / TTS / 진동.
현재 이 결과 전달 경로는 미구현이다. FeedbackCoordinator.kt의 공통 선택 로직은 구현했으나 Python 변환·화면 연결은 아직 없다. 자세한 사용법은 feedback-coordinator.md를 참고한다.

## 담당자와 AI 에이전트의 작업 체크

- 최신 main을 pull한 뒤 별도 feature 브랜치에서 작업한다.
- tactile_context.py와 해당 테스트를 중심으로 수정하고 다른 담당자 모듈은 임의로 바꾸지 않는다.
- 입력 없음, 점형 블록 없음, 주변 시설 없음, contour 없음, 여러 객체 입력을 테스트한다.
- 반환 항목의 네 키·자료형·우선순위와 객체 ID 참조를 테스트한다.
- 모든 모듈이 전체 frame_data를 읽을 수 있게 입력을 임의로 수정하지 않는다.
- 공통 계약 변경이 필요하면 영향 설명 후 contracts.md와 이 문서를 함께 갱신한다.
- 테스트: python -m unittest discover -s app/src/test/python -v
- PR에는 판단 근거·검증 결과·미검증 조건을 적는다. 카메라와 연결된 실제 보행 안내가 동작한다고 주장하지 않는다.
