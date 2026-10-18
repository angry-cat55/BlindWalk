# 상황 판단 모듈의 임시 계약

실제 AI 모델이 선정되지 않은 상태의 임시 계약이다. 모델 출력 구조를 미리 확정하지 않는다.

| 타입 | 역할 | 현재 형태 |
| --- | --- | --- |
| DetectionFrame | 공통 AI 인식 결과 입력 | 필드 없는 클래스 |
| SituationAnalyzer | 상황 판단 모듈 공통 인터페이스 | analyze(frame: DetectionFrame): List<RiskEvent> |
| RiskEvent | 상황 판단 결과 한 건 | 필드 없는 클래스 |

네 분석기는 모두 emptyList()를 반환한다. 빈 목록은 안전하다는 판정이 아니라 미구현 상태이다.
필요한 필드와 의미는 모델 선정 후 팀 공통 협의로 정하고 이 문서도 수정한다.

호출 흐름:
- MainActivity → CameraScreen → CameraPreview: 후면 카메라 미리보기
- AI 버튼 → MockInferenceEngine.infer(): 고정 문자열 표시
- 상황 판단 버튼 → 해당 Analyzer.analyze(DetectionFrame()) → 빈 목록 반환 → UI 미구현 안내
- 피드백 버튼 → HapticFeedback.vibrate() / SpeechFeedback.speak()

Mock 문자열은 DetectionFrame으로 변환되지 않는다. 카메라 프레임을 분석기에 연결하는 파이프라인은 없다.
