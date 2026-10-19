# Python 상황 판단의 임시 계약

모델이 미정인 초기 Skeleton이다. 실제 AI 출력 구조·깊이 단위·판단 결과 항목은 추후 팀이 협의한다.

## 공통 입력
모든 상황 모듈은 `analyze(frame_data)`를 사용하고 Python 목록을 반환한다.

```python
frame_data = {
    "frame_id": 0,
    "objects": [],
    "situations": [],
}
```

- `frame_id`: 같은 촬영 프레임의 예측을 묶는 식별자. 버튼 테스트에서는 0을 사용한다.
- `objects`: 공통 객체 정보 목록. 향후 label·bbox·confidence·깊이 등을 정리할 예정이며 현재 항목 형식은 확정하지 않는다.
- `situations`: 실행할 분석 종류 목록. 확정된 위험을 의미하지 않으며 여러 상황을 동시에 지정할 수 있다.
- 상황 이름: `TACTILE_ANOMALY`, `TACTILE_CONTEXT`, `WALKING_HAZARD`, `OVERHEAD_HAZARD`.

## 함수와 담당 범위
- `frame_interface.build_frame(frame_id, model_results=None)`: 향후 하나 이상의 AI 결과를 objects로 정리하고 situations를 선택한다. 현재 model_results를 사용하지 않고 빈 입력만 반환한다.
- `frame_interface.analyze(frame_data)`: situations에 지정된 모듈을 각각 호출하고 반환 목록을 합친다. 별도 라우터 파일은 없다.
- `frame_interface.run_test(situation)`: 버튼 연결 확인 전용. 빈 프레임에 상황 하나를 직접 지정한 뒤 analyze를 호출한다. AI 기반 상황 판단이 아니다.
- 네 상황 모듈의 `analyze(frame_data)`: 현재 TODO와 `return []`만 있다. 향후 세부 위험 판단을 담당한다.
- 판단 결과: 현재 빈 목록. 항목의 필드는 미정이다. 빈 결과는 안전하다는 의미가 아니다.

## 호출 흐름
현재: `테스트 버튼 → PythonBridge → run_test → 공통 입력 구성 → 해당 Python 모듈 → 빈 목록 → UI 미구현 안내`.
Mock 버튼: `PythonBridge → mock_inference.infer → 고정 Mock 문자열`.
목표: `카메라 → 하나 이상의 AI 예측 → build_frame → analyze → 해당 상황 모듈 → 결과 → Kotlin 음성·진동`.

카메라와 Python 사이의 프레임 전달, 실제 모델 추론, 모델 결과 변환, 상황 자동 선택, 자동 피드백은 구현하지 않는다.
Mock 문자열을 실제 AI 결과로 취급하지 않는다. 계약 변경 시 이 문서와 AGENTS.md를 함께 수정한다.
