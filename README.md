# BlindWalk

ROKEY 스터디원4명이 개발하는 Android 온디바이스 AI 보행 보조 시제품이다.
현재 본 앱은 가로 UI와 카메라 입력 준비 단계이며 **AI 추론·상황 판단·자동 보행 안내는 미구현**이다.

## 실행과 현재 기능
- 휴대폰을 가로로 사용한다. 메인에는 앱 이름과 큰 시작 버튼만 표시한다.
- 시작→권한 확인→왼쪽4:3 후면 Preview, 오른쪽 현재 상태·중지 버튼.
- 중지·뒤로 가기→카메라/프레임 선택 종료→메인. 백그라운드 이동 시에도 종료한다.
- Preview는30FPS를 목표로 요청한다. 실제 달성 여부는 기기·조명에 따라 다르다.
- 원본 프레임은 약200ms 이상 간격으로 최신 한 장을 선택한다(최대 약5장/초). 추론 FPS가 아니다.
- TalkBack 버튼 이름·상태 전환 알림, 큰 조작 영역과 글꼴 확대를 고려한다.
- 과거 일곱 테스트 버튼은 화면에서 제거했다. Mock·Bridge·Python 상황 모듈·진동/TTS 파일은 보존하며 현재 화면에서 호출하지 않는다.
- jh-test의 ARCore 실험은 별개 앱이며 본 앱에 포함하지 않는다.

## 주요 파일
```text
app/src/main/java/com/example/blindwalk/
├── MainActivity.kt             # 가로 Compose 진입
├── ui/CameraScreen.kt          # 메인/촬영·권한·중지·접근성
├── camera/
│   ├── CameraPreview.kt       # Preview + ImageAnalysis·생명주기
│   ├── FrameGate.kt           # 200ms 간격·지연 후 몰아보내기 방지
│   └── AiFrameInput.kt        # AI 담당자의 원본 프레임 연결점(TODO)
├── bridge/PythonBridge.kt      # 보존된 Python 테스트 연결
└── feedback/                  # 보존된 진동·TTS
app/src/main/python/
├── frame_interface.py          # 향후 AI 결과 공통화·상황별 호출
├── mock_inference.py           # 보존된 Mock 테스트 함수
├── tactile_anomaly.py          # 점자블록 이상
├── tactile_context.py          # 점형블록 주변
├── walking_hazard.py           # 일반 보행 위험
└── overhead_hazard.py          # 머리 높이 장애물
```

## AI 팀 연결 규칙
`AiFrameInput.onFrameSelected(frameId: Long, image: ImageProxy)`를 분석 전용 스레드에서 동기 호출한다.
원본 버퍼·cropRect·회전·촬영 timestamp·format·planes를 확인할 수 있다. 가로4:3은 cropRect와 회전을 반영한 유효 영역 기준이다.
콜백 반환 직후 카메라가 image.close()하므로 image/planes를 보관하면 안 된다.
입력 크기·RGB변환·정규화·텐서·Python 전달은 모델 선정 후 협의한다.
KEEP_ONLY_LATEST와 전용 executor를 사용하고 추가 프레임 큐는 만들지 않는다.
상세 계약: [docs/contracts.md](docs/contracts.md). 카메라 원본과 추론 후 Python frame_data는 별개다.
파일별 촬영·선택·전달 흐름과 팀원 작업 지점은 [AI 팀 공유 문서](docs/ai-team-handoff.md)를 참고한다.
앱 아이콘은 메인 워드마크의 보라색 Blind/Walk 두 줄을 사용한다. [아이콘 리소스 안내](docs/app-icon.md).

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

기존 Wrapper·Version Catalog를 유지하며 새로운 AI 라이브러리·모델은 설치하지 않는다.
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
