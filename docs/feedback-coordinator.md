# 공통 안내 처리 사용법

## 현재 구현과 연결 경계

feedback/FeedbackCoordinator.kt는 여러 상황의 결과에서 이번에 안내할 하나를 선택한다.
파일·DB·Keystore를 사용하지 않고 최근 기록만 메모리에 보관한다.
PythonBridge가 실제 결과를 Kotlin으로 변환하고 CameraScreen이 submit을 호출하도록 연결했다. 시작 후 선택된 안내는 실제 TTS·진동 함수에 전달된다. 실제 청취·기기 성능 검증은 별도다.

## 입력과 사용 흐름

Python의 결과 딕셔너리를 다음 Kotlin 자료형으로 변환해 전달해야 한다.

| Python 키 | Kotlin FeedbackResult 속성 |
| --- | --- |
| situation | situation: String |
| object_id | objectId: Int |
| message | message: String |
| priority | priority: FeedbackPriority (INFO / CAUTION / URGENT) |

변환 시 알 수 없는 등급·잘못된 자료형을 임의 등급으로 바꾸지 않는다. 현재 Bridge는 JSON 필수 필드와 등급 이름을 검증하며 잘못된 형식은 프레임 오류로 전파한다.

```kotlin
val speech = SpeechFeedback(context)
val haptic = HapticFeedback(context)
val coordinator = FeedbackCoordinator(
    speak = { message -> speech.speak(message) },
    isSpeaking = speech::isSpeaking,
    vibrate = haptic::vibrate,
    stopSpeech = speech::stop,
)

// 화면은 coordinator를 한 번 만들고 세션 동안 유지한다.
// 결과가 올 때마다 새로 만들면 최근 안내 기록이 사라진다.
val selected = coordinator.submit(latestResults)
// selected가 있으면 화면의 현재 안내 문구를 갱신한다.
// null은 '새 발화 없음'이며 '안전'이라는 뜻이 아니다.

// 중지·백그라운드·세션 변경 때 기록과 발화를 정리한다.
coordinator.reset()
haptic.close()
// 화면이 실제 종료될 때는 TTS 엔진도 해제한다.
speech.close()
```

현재 CameraScreen에서 위 연결을 유지한다. 일시정지 시 coordinator.reset과 진동 취소를 수행하며 TTS 엔진은 같은 화면에서 재사용한다. 화면 종료 시 TTS를 close한다. 상태 음성은 백그라운드에서 재시도하지 않으며 이미 선택된 위험 안내를 덮어쓰지 않는다.
생성·submit·reset·SpeechFeedback 제어는 메인 스레드에서 수행한다.
AI 결과가 분석 스레드에서 오면 메인 스레드로 전달한 뒤 submit한다.

## 선택 정책

1. 같은 프레임에서 동일 objectId의 결과는 가장 높은 등급 하나만 남긴다. 동률은 입력 순서다.
2. 같은 객체 ID·문구·등급은 마지막 발화 요청 성공 후 5초간 제한한다.
3. ID가 달라도 같은 문구·등급은 3초간 제한한다. 추적 ID 변화에 대응하지만 서로 다른 동종 객체도 잠시 묶일 수 있다.
4. URGENT → CAUTION → INFO 순서로 고른다. 동률이면 마지막 안내가 더 오래된 대상, 미안내 대상끼리는 입력 순서다.
5. 발화 중에는 새 결과를 저장하거나 큐에 쌓지 않는다. 새 URGENT만 낮은 등급 발화를 교체한다. URGENT끼리는 중단하지 않는다.
6. speak가 요청을 받았을 때만 기록한다. INFO는 음성만, CAUTION·URGENT는 기존 짧은 진동도 요청한다.

기록은 각 맵 최대 64개·최근 30초다. 시간은 단조 시각을 사용한다.
계속 최신 결과를 submit하는 호출 구조를 전제로 한다. 발화 완료 시 과거 후보를 자동 재생하지 않는다.
긴 URGENT가 계속 선택되면 낮은 등급은 밀릴 수 있다. 안전 우선 정책이며 모든 결과의 안내를 보장하지 않는다.
같은 객체가 다른 ID로 바뀌거나 ID가 재사용될 수 있으므로 완벽한 객체 동일성 판단은 아니다.

## TTS 상태

SpeechFeedback.speak(message)는 문자열을 받고 기존 발화를 교체한다. 기존 speak() 테스트 호출도 유지한다.
isSpeaking은 재생 대기 상태도 포함한다. 완료·오류·중단 콜백은 발화 ID로 구분한다.
이전 발화의 콜백이 새 발화 상태를 지우지 않도록 처리한다.
발화 요청 성공은 실제 사용자 청취 완료를 보장하지 않는다. 나중에 비동기 오류가 나도 기록은 즉시 되돌리지 않는다.

## 남은 작업과 제약

- 실제 보행 영상과 기기에서 PythonBridge 결과·음성·진동 검증.
- 화면 상태 갱신과 reset/close는 연결했으며 빠른 시작·중지 검증을 유지한다.
- 기존 tactile_context는 결과 생성 시 자체 3초 쿨다운을 적용한다. 공통 선택에서 밀린 결과도 잠시 숨겨질 수 있다. 2번 담당자와 중복 제한 책임을 조정해야 하며 이번 작업에서는 수정하지 않았다.
- 실제 기기의 한국어 TTS·긴급 중단·진동 확인. 현재 단위 테스트는 가짜 출력 함수로 선택 정책을 검증한다.
