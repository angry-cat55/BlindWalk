# Android 객체 추적 구현 계획

**목표:** 사용자 확정 요구사항에 따라 짧은 미탐지 전후 ID를 연결한다. 구현 방식 선택 및 실행은 사용자가 위임했다. commit/push/merge는 하지 않는다.

**구조:** 모델 실행과 별개인 Kotlin `ObjectTracker.update(observations, observedAtMillis)`를 AiFrameInput에 둔다. 클래스·IoU·크기·중심 이동과 제한된 등속 예측을 사용하고 모호한 연결을 거부한다. ByteTrack이 아니다. PC는 외부 Ultralytics 구현에 의존하므로 직접 재사용하지 않는다. 디코더 confidence 0.25/NMS/30개 제한을 보존한다.

**제약:** 마지막 실제 프레임 선택 시각(elapsedRealtime ms)에서 1000ms 초과 시 만료. 유실 예측은 시각을 연장하지 않는다. 현재 관측의 id만 교체해 UI/Python에 전달한다. ROI·거리·모델·클래스·Python 판단·피드백 정책 보존. 상태는 AiFrameInput 세션 소유이며 같은 분석 executor에서 갱신/해제한다. 최대256개 보관, 상한 도달 시 오래된 유실 기록 제거, 세션 내 ID 재사용 금지.

## 작업과 검증

- [x] 추적 단위 테스트를 먼저 추가하고 실패 확인: 연속 관측/후보 ID 변화, 1000/1001ms 경계, 빈 관측 시 만료, 가변 간격·이동, 동종 일대일/순서 반전, 모호함/원거리/크기/클래스 불일치, 현재 관측 필드 보존, reset, 저장 상한.
- [x] ObjectTracker 구현 후 같은 테스트 및 전체 Kotlin 테스트 실행.
- [x] AiFrameInput에서 infer 이후 tracker에 전달하고 그 목록을 UI 결과와 Python 입력에 공통 사용. close에서 reset, 취소 후 반환 폐기, 최소 진단 로그 추가. UI의 기존 새 결과 전체 교체·1.2초 표시 만료는 유지.
- [x] 추적 ID와 실제 PythonBridge·상황 판단·Coordinator의 왕복 Android 테스트 추가. JVM에서는 추적 ID로 3초/5초 피드백 경계 및 빈 결과 무발화를 확인. Python 테스트 전체 실행.
- [x] README/AGENTS/contracts/ai-team-handoff/feedback 문서와 Recognition/Detection 주석 갱신. assembleDebug/testDebugUnitTest/lintDebug 및 가능한 연결 기기 테스트 실행.
- [x] 독립 코드 리뷰 후 중요한 결함을 테스트와 함께 수정하고 최종 검증.

## 검토 초점

- 동일 클래스가 교차하거나 후보 비용이 비슷하면 ID 전환 위험이 있다. 근거 부족 시 새 ID가 우선이다.
- 느린 추론으로 관측 간격이 1초를 초과하면 연속 탐지라도 새 ID다. TTL을 연장하지 않는다.
- 빈 프레임은 오래된 실제 관측 시각을 갱신하지 않는다.
- 새 세션은 별도 tracker이며 늦은 결과는 기존 disposed/cancelled 경계로 폐기한다.
- 화면은 새 추론 결과 사이에 최신 실제 관측을 기존 최대1.2초 유지한다. 유실 기록을 추가하거나 매 Preview 프레임마다 지우지 않는다.

## 리뷰 및 판단 기록

- 독립 읽기 리뷰의 Important: 모호한 교차 뒤 남은 유실 가설이 새 트랙과 계속 경쟁해 ID가 반복 변경됨. x좌표 [60,340]→[100,300]→[200] 후 정지하는 회귀 테스트의 실패를 확인했다. 직전 활성 트랙 우선·활성 후보가 없는 관측만 유실 매칭으로 수정하고 전체 Kotlin 테스트 통과를 확인했다. 이는 오래된 가설보다 최근 관측 연속성을 우선하는 판단이며, 겹친 다른 실제 객체가 들어오면 오연결 가능성은 여전히 있다.
- 보관 상한 판단: 초기128개는 최대5FPS·결과30개에서 1000ms 경계 포함180개를 조기에 제거할 수 있었다. 회귀 실패를 확인한 뒤256개로 늘렸다. 향후 처리율/결과 제한을 늘리면 상한을 다시 검토해야 한다.
- 보류한 Minor: Python 전역 잠금의 취소/초기화 경쟁조건을 자동 재현하는 테스트는 추가하지 않았다. 코드는 독립 리뷰했고 세션 tracker.reset과 실제 Python ID 왕복은 테스트하지만 빠른 카메라 중지/재시작 경쟁은 실행 검증하지 않았다.
- 실영상 추적 정확도·bbox 깜빡임·TTS 반복 감소·실기기 GPU/지속 성능은 이번 합성 테스트로 판단하지 않는다.

## 최종 실행 증거

- `:app:assembleDebug :app:testDebugUnitTest :app:lintDebug :app:connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.example.blindwalk.AiIntegrationTest`: BUILD SUCCESSFUL. Kotlin35개, Android 에뮬레이터 합성 통합4개 통과. lint 오류0·경고30.
- `python -m unittest discover -s app/src/test/python -v`: 101개 통과(Python3.12). 호스트3.14 미설치로 `py -3.14` 실행 불가. 앱 내3.14는 Android 통합 테스트에서 사용했다. Chaquopy 빌드는 호스트3.14 부재로 .pyc 사전 컴파일 경고가 있지만 APK 빌드는 성공했다.
- `git diff --check`: 통과. commit/push/merge 없음. 별도 worktree 없이 사용자 프로젝트의 feature/android-object-tracking에서 변경을 보존했다.
