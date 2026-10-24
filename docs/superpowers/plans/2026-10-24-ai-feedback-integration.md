# 카메라부터 안내까지 연결 계획

사용자 승인 범위: 병합된 main을 pull한 뒤 기존 부품을 실제 추론·상황 판단·피드백으로 연결한다. 별도 실험 앱은 수정하지 않는다.

1. 실제 모델 metadata 확인: YOLO FP32 NCHW 1×3×640×640, 출력 1×54×8400·1×32×160×160. 좌표는 1/640 정규화됨. MiDaS 동적 양자화 NCHW 1×3×256×256.
2. LiteRT Interpreter와 ONNX Runtime Android의 CPU 실행을 추가한다. 모델은 models/active에서 Gradle 생성 assets로 복사해 중복 소스 파일을 만들지 않는다.
3. 선택 프레임을 crop·회전 후 가로 640×480 RGB로 맞춘다. YOLO는 회색 letterbox·RGB/255 NCHW, 깊이는 256×256 ImageNet 정규화 NCHW를 사용한다.
4. 모델 출력 decode·class별 NMS·점자블록 mask contour와 추정 거리를 Detection JSON으로 만든다. 모바일 ByteTrack은 미구현이며 ID는 프레임 내 순번임을 명시한다.
5. PythonBridge가 build_frame → analyze를 실행하고 공통 결과를 Kotlin FeedbackResult로 변환한다. 기존 담당자 상황 모듈은 수정하지 않는다.
6. 분석 전용 단일 executor·KEEP_ONLY_LATEST·200ms gate를 유지한다. 중지 시 결과 폐기·TTS/진동 종료·모델 close를 분석 스레드에서 순서대로 수행한다.
7. 화면에는 선택된 안내 문구만 추가한다. bbox/경로선 overlay는 이번 연결 범위에 넣지 않는다.
8. 실제 출력 decoder·JSON bridge·세션 폐기 테스트 후 Android build/lint/unit test와 가능한 기기 모델 실행을 확인한다. 모델의 미터 보정 정확도·실제 FPS는 측정 전 보장하지 않는다.

실제 추론은 Android native로 실행하고 Python은 기존 표준 라이브러리 판단 계층을 유지한다. 자동 commit/push/PR은 이번 요청 범위가 아니다.

검증 기록: Kotlin 테스트14개, Python101개 통과. 에뮬레이터 Android16에서 실제 두 모델 실행·Python 결과→Coordinator 테스트를 포함한 instrumentation3개 통과. 실제 카메라 시작→카메라 실행 중→뒤로→메인과 카메라 appops 종료를 확인했다. 실제 보행 영상 정확도·실기기 음성/진동·휴대폰 FPS는 미검증이다.

실기기 추가 검증: SM-N971N / Android12 / arm64에서 AiIntegrationTest3개 통과(실제두모델, Python→Coordinator, 한국어TTS요청·완료콜백·진동요청). 실제 카메라에서 objects=0 장면의 YOLO426ms/decode9ms 관측, 처리량 대략2장/초 수준이며 Preview렌더FPS를 측정한 값은 아니다. 카메라 실행 중 화면과 종료 후 appops해제를 확인했다. 실제 소리 청취·진동 체감·보행영상 정확도·미터 거리 보정은 별도 확인이 필요하다.
