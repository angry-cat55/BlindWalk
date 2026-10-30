# BlindWalk

ROKEY 스터디원4명이 개발하는 Android 온디바이스 AI 보행 보조 시제품이다.
본 앱은 가로 카메라에서 실제 모델 추론 → Python 상황 분석 → 공통 안내 선택 → 한국어 TTS·짧은 진동 호출까지 연결한 학습용 시제품이다. 실제 보행 안전성과 거리 보정 정확도는 검증되지 않았다.

## 실행과 현재 기능
- 휴대폰을 가로로 사용한다. 앱 실행 후 권한을 확인하고 카메라·모델 준비를 자동 시작한다.
- 넓은 16:9 후면 Preview 위에 앱 이름·실행 상태·검출 표시 전환·큰 일시정지 버튼을 배치한다.
- 일시정지·뒤로·백그라운드에서 카메라·분석·안내를 정리한다. 같은 화면의 다시 시작 버튼으로 재개한다.
- Preview는30FPS를 목표로 요청한다. 실제 달성 여부는 기기·조명에 따라 다르다.
- 원본 프레임은 약200ms 이상 간격으로 최신 한 장을 선택한다(최대 약5장/초). 추론 FPS가 아니다.
- TalkBack 버튼 이름·상태 전환 알림, 큰 조작 영역과 글꼴 확대를 고려한다.
- 과거 일곱 테스트 버튼은 화면에서 제거했다. Mock 테스트 함수는 보존하지만 현재 화면에서는 실제 추론·Python 분석·진동/TTS 경로를 호출한다.
- jh-test의 ARCore 실험은 별개 앱이며 본 앱에 포함하지 않는다.

## 주요 파일
```text
app/src/main/java/com/example/blindwalk/
├── MainActivity.kt             # 가로 Compose 진입
├── ui/CameraScreen.kt          # 메인/촬영·권한·중지·접근성
├── camera/
│   ├── CameraPreview.kt       # Preview + ImageAnalysis·생명주기
│   ├── FrameGate.kt           # 200ms 간격·지연 후 몰아보내기 방지
│   └── AiFrameInput.kt        # 원본 crop·회전·640×480 변환·실제 추론/분석
├── bridge/PythonBridge.kt      # 실제 Detection JSON 전달·결과 변환
└── feedback/                  # 공통 안내 선택·진동·TTS·외부 햅틱(Bluetooth/USB)
    └── UsbHapticManager.kt    # ESP32 블루투스 SPP 및 USB 시리얼 방향별(L/R/C) 햅틱 전송
esp32_haptic/
└── esp32_haptic.ino           # ESP32 좌(GPIO 27)·우(GPIO 25) 햅틱/LED 제어 펌웨어
app/src/main/python/
├── frame_interface.py          # Detection 묶기·2/3/4 분석 대상 선택·모듈 호출
├── mock_inference.py           # 보존된 Mock 테스트 함수
├── tactile_anomaly.py          # 점자블록 이상
├── tactile_context.py          # 점형블록 주변
├── walking_hazard.py           # 일반 보행 위험
└── overhead_hazard.py          # 머리 높이 장애물
```

Python 인터페이스는 Detection 목록의 클래스명으로 2·3·4 분석 대상을 선택한다. 선택 자체는 위험 확정이 아니며 현재 본 앱 카메라의 실제 추론 결과에 연결되어 있다.

## 실제 실행 흐름
CameraPreview → 200ms FrameGate → AiFrameInput → MobileInferenceEngine → ObjectTracker → PythonBridge → frame_interface.build_frame/analyze → FeedbackCoordinator → 화면 안내([◀ 좌측 / ▶ 우측 / ▲ 정면 햅틱] 시각화 포함)·TTS·진동(내장 진동 및 ESP32 방향별 햅틱).

- cropRect·회전을 적용한 16:9 영상의 중앙 4:3을 잘라 640×480 RGB로 맞춘다. 분석 전용 단일 스레드에서 실행하고 image는 finally에서 닫는다.
- YOLO는 회색 letterbox 640×640·RGB/255·NCHW다. MiDaS는 256×256·ImageNet 정규화·NCHW다.
- 추론이 느리면 실제 처리 FPS는 5보다 낮아진다. KEEP_ONLY_LATEST로 적체를 막는다. Preview30FPS는 별도 목표다.
- 중지·뒤로·백그라운드에서 늦은 결과를 폐기하고 TTS·진동·모델 자원을 정리한다.
- 실제 bbox·한글 클래스명·점자블록 contour를 표시하고, 같은 프레임의 안내 대상만 강조한다. 경로선·거리·FPS는 표시하지 않는다.
- 검출 표시는 선택 시각부터 1.2초 후 지우고 안내 카드는 새 안내 후 3초 뒤 지운다. 검출 표시만 끌 수 있으며 음성 판단에는 영향을 주지 않는다.
- 모델 원본은 models/active에 두고 Gradle이 필요한 두 파일만 생성 assets로 복사한다.
- 모바일은 경량 Kotlin ObjectTracker로 클래스·bbox·이동을 비교해 세션 추적 ID를 붙인다(ByteTrack 아님). 마지막 실제 관측의 단조 선택 시각부터 1초 이내이며 매칭 조건을 만족할 때만 ID를 연결한다. 1초 초과 시 만료하고 같은 세션에서 ID를 재사용하지 않는다. UI와 Python에는 현재 실제 탐지만 전달한다.
- 모델 클래스 목록은 labels.json에 추출했고 SHA-256으로 가중치와 일치 여부를 확인한다. 가중치를 바꾸면 목록과 해시도 갱신해야 한다.
- 깊이의 K=1000 미터 환산은 AI팀 PC 코드 기준이며 실제 거리 보정 정확도는 미검증이다. 거리 미상은 None으로 전달한다.

계약: [contracts](docs/contracts.md), 촬영 연결: [AI 팀 문서](docs/ai-team-handoff.md), 판단: [상황 핸드오프](docs/situation-handoff.md), 출력: [공통 안내 처리](docs/feedback-coordinator.md).

## 개발 환경
| 항목 | 설정 |
| --- | --- |
| Android Studio | 사용자 입력: __________ |
| Gradle / AGP | 9.5.0 / 9.3.3 |
| Kotlin Compose 플러그인 | 2.2.10 (AGP 내장 Kotlin) |
| Compose BOM | 2026.02.01 |
| JDK / Java 소스·타깃 | 25 / 11 |
| SDK | compile37 / target37 / min24 |
| CameraX | 1.6.2 |
| Chaquopy / Python | 17.1.0 / 3.14 |
| CPU | arm64-v8a / x86_64 |

기존 Wrapper·Version Catalog를 유지한다. 저장소 모델을 실행하기 위해 LiteRT 1.4.2와 ONNX Runtime Android 1.24.3(CPU)를 추가했다. Python AI 패키지는 설치하지 않는다.
개인 SDK 경로는 공유하지 않는 local.properties에서 설정한다.

## Clone·빌드
1. `git clone https://github.com/angry-cat55/BlindWalk.git` 후 Android Studio로 연다.
2. 개발 전 **AGENTS.md**, docs/contracts.md를 읽는다.
3. SDK37·JDK25·Python3.14를 준비하고 Gradle Sync 후 실기기를 선택해 Run한다.

```powershell
.\gradlew.bat :app:assembleDebug :app:testDebugUnitTest :app:lintDebug
py -3.14 -m unittest discover -s app/src/test/python -v
```

macOS/Linux는 ./gradlew와 python3.14를 사용한다.
main을 pull한 후 feature/기능명에서 작업하고 PR로 검토받는다. 명시적 요청 없이 commit/push/merge하지 않는다.
본 앱은 보행 안전성을 검증한 제품이 아니다. 미탐지·빈 결과는 안전을 의미하지 않는다.

3번 일반 보행 판단은 점자블록 영역 또는 임시 중앙 진행 영역에 걸린 객체를 선택하고 클래스별 등급·짧은 안내를 반환한다. 영상 크기가 필요하며 실제 영상 정확도·모바일 실행 속도는 아직 검증하지 않았다. 기준은 docs/contracts.md를 참고한다.

4번은 overhang 객체마다 돌출물 주의·CAUTION을 반환한다. 별도 위치 필터나 상세 종류 추측은 하지 않으며 공통 안내를 통해 앱 음성·진동을 요청한다.

공통 안내 선택·반복 제한 컴포넌트를 앱·Python 결과에 연결했다. 사용법과 메모리 정책은 [공통 안내 처리](docs/feedback-coordinator.md)를 참고한다.

실기기 확인: SM-N971N(Android12)에서 모델·Python 연결과 TTS요청/완료·진동요청 테스트3개 통과. 빈 검출 장면의 CPU YOLO는 약426ms(분석 약2장/초 수준)를 관측했으며 Preview30FPS 달성 측정값은 아니다. 실제 청취·진동 체감과 보행 정확도는 별도 검증 대상이다.


## GPU 실행 및 실기기 측정 (2026-10-24)
- YOLO는 LiteRT GPU Delegate를 우선 사용한다. 지원 불가·초기화·실행 실패 시 CPU로 복귀하며 실제 backend를 로그에 남긴다. 모델 확장자와 가중치는 변경하지 않았다.
- MiDaS ONNX 거리 추정은 CPU에서 실행한다. GPU 생성·호출·해제는 같은 분석 스레드에서 수행한다.
- SM-N971N(Android12)에서 YOLO 전체 394/394 연산의 OpenCL GPU 위임을 로그로 확인했다.
- 동일한 640×480 회색 입력, 각 경로 워밍업2회 후5회 측정 중앙값: CPU 1101.6ms, GPU 164.7ms(약6.7배). 전처리·YOLO·디코딩을 포함한다.
- 이 입력은 검출0개로 거리 추정을 생략한다. 따라서 전체 AI 파이프라인5FPS 달성을 의미하지 않는다. CPU 측정은 이전 카메라 관측426ms와 실행 조건이 달라 직접 비교하지 않는다.
- GPU 변경 후 실기기 통합 테스트3개(모델 실행·Python 결과 연결·TTS/진동 API)가 통과했다. 실제 영상 인식 정확도·CPU/GPU 예측 일치도·발열에 따른 지속 성능은 별도 검증 대상이다.
- 카메라 재확인 시 휴대폰 잠금 화면으로 실제 촬영 동작의 추가 확인은 하지 못했다. 변경 앱은 실기기에 설치했다.

화면은 16:9 전체 영상이며 AI는 중앙 4:3만 분석한다. 양옆에 보이는 객체는 분석하지 않을 수 있다. 임시 HTML 시안은 승인 후 삭제했다. 이 UI 변경 후 실기기 검증 여부는 아래 검증 기록을 참고한다.

UI 변경 검증(2026-10-25): 빌드·Kotlin19개·Python101개·lint(오류0) 통과. 에뮬레이터 준비/일시정지 화면과 재시작 시 카메라 연결 확인. 에뮬레이터 Preview는 검정/준비 지연이 관측되어 실제 영상 검출 오버레이의 시각적 정합은 미검증이며 실기기에서 추가 확인이 필요하다.

추가 로그 확인: 에뮬레이터가 실제 1280×720 프레임을 수신했고 YOLO·깊이 추론으로 객체1~2개를 반환했다. 에뮬레이터는 CPUfallback이며 수초의 추론 지연이 있어 1.2초를 넘는 검출 표시는 폐기한다. 실기기 검출 위치 정합·GPU 성능의 재확인은 아직 수행하지 않았다.

객체 추적의 시간·매칭·자원 계약은 [contracts](docs/contracts.md#모바일-객체-추적)를 따른다. `ObjectTracking` 로그의 intervalMs는 실제 선택 프레임 간격, selectionAgeMs는 추론·추적까지의 지연이며 new/reconnected/expired/evicted/retained를 함께 기록한다. 추적 ID는 외형 재식별 결과가 아니며 교차·급격한 카메라 이동·클래스 변경 시 끊기거나 잘못 연결될 수 있다. 유실 객체를 그리지 않으므로 bbox 깜빡임을 없애지 않는다. TTS 반복 감소·실제 영상 성능은 별도 검증 대상이다.

객체 추적 검증(2026-10-26): `assembleDebug`, Kotlin 단위35개(추적14개·추적/피드백2개 포함), `lintDebug`(오류0·경고30), Python 단위101개 통과. 호스트 Python3.14가 없어 PC 테스트는 설치된3.12로 실행했다. Medium_Phone 에뮬레이터(Android17)의 `AiIntegrationTest`4개도 통과하여 앱 내 Chaquopy Python3.14의 실제 ID 왕복·빈 입력·기존 모델 및 출력 API를 확인했다. GPU 벤치마크는 실행하지 않았다. 실영상·실기기 추적 정확도, 빠른 카메라 중지/재시작 경쟁조건의 자동 회귀 검증, 실제 청취·진동 체감·TTS 반복 감소는 미검증이다.

상단 겹침 수정(2026-10-28): 16:9 FIT_CENTER 영상의 검은 여백 경계가 앱 이름 중간을 통과하던 문제를 수정했다. 이전 투명 오버레이 구조를 유지하면서 이름을 영상 좌우 여백 너비만큼 안쪽으로 옮기고 25sp에서22sp로 줄였다. 불투명 상단 바는 사용하지 않으며 카메라·검출 오버레이의 전체 화면 크기·좌표와 AI 입력을 유지한다. 수정 후 실기기 시각 확인과 TalkBack 실제 탐색은 미검증이다.

런처 아이콘은 사용자가 선택한 B안 파랑(#205DE3)과 C안 눈 심벌 조합이다. 적응형·원형·단색 및 구형 기기용 PNG에 반영했으며 Lucide Eye 라이선스는 app/src/main/assets/licenses/lucide.txt에 보관한다. 선택이 완료된 임시 HTML 후보는 삭제했다.

최종 UI·아이콘 검증(2026-10-28): assembleDebug·Kotlin35개·lintDebug(오류0·경고25) 통과. 에뮬레이터 실행 화면에서 전체 카메라 영상 위로 이름만 안쪽에 이동한 배치와 Android 앱 정보의 파란 눈 아이콘을 확인했다. 실기기 설치·TalkBack 실제 탐색은 미검증이다.

## 외부 방향별 햅틱(ESP32) 연동 및 UI 시각화 (2026-10-30)

- **방향별 외부 햅틱 전송 (UsbHapticManager)**: 선택된 안내 대상 객체의 화면 X좌표(좌측 1/3, 중앙 1/3, 우측 1/3)와 안내 문구를 판별하여 "L"(좌측), "R"(우측), "C"(정면/양쪽) 명령을 전송한다.
- **이중 연결 지원 (Bluetooth SPP & USB Serial)**: 페어링된 ESP32 블루투스 기기(BlindWalk_Haptic 등)로 무선 전송하며, USB OTG 케이블 연결 시 시리얼(115200 bps)로도 자동 전송한다. 외부 기기 미연결 시에도 앱 내장 진동은 정상 동작한다.
- **화면 안내 카드 햅틱 시각화 (CameraScreen)**: 시연 및 직관적 상태 확인을 위해 하단 안내 카드 메시지 앞에 [◀ 좌측 햅틱], [▶ 우측 햅틱], [▲ 정면 햅틱] 방향 배지를 함께 표시한다.
- **보행자 및 좌·우 장애물 안내 범위 보완 (walking_hazard.py, FeedbackCoordinator)**: 보행자(person) 및 시설물(facility) 탐지 시에도 주의(CAUTION) 등급 및 햅틱 알림이 동작하도록 조정하고, 중앙 사다리꼴 외 좌·우 영역 객체에 대해서도 방향별(좌측/우측/전방) 안내를 생성한다.
