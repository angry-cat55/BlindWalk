# BlindWalk

ROKEY 스터디원 4명이 개발하는 한국형 AI 보행 유도시설 위험 인식 Android 시제품의 초기 Skeleton.
패키지는 `com.example.blindwalk`이다. 실제 AI와 상황 판단 기능은 아직 구현하지 않았다.

## 개발 환경
| 항목 | 프로젝트 설정 |
| --- | --- |
| Android Studio | 사용자 입력: __________ |
| Gradle Wrapper / AGP | 9.5.0 / 9.3.3 |
| Kotlin Compose 플러그인 | 2.2.10 (AGP 내장 Kotlin 사용) |
| Compose BOM | 2026.02.01 |
| JDK | daemon 기준 25 (gradle/gradle-daemon-jvm.properties) |
| Java 소스·타깃 호환성 | 11 |
| SDK | compile 37 / target 37 / min 24 |
| CameraX | 1.6.2 |
| Chaquopy / Python | 17.1.0 / 3.14 |
| 지원 CPU | arm64-v8a / x86_64 |

기존 Android 버전은 유지했다. CameraX와 Python 내장 실행용 Chaquopy를 Version Catalog로 관리한다.
AI 모델과 추론 프레임워크·외부 Python 패키지는 설치하지 않았다.
개인 SDK 경로는 local.properties에서 설정하며 공유하지 않는다.

## 주요 구조
```text
app/src/main/
├── java/com/example/blindwalk/     # Android 기능만 Kotlin으로 유지
│   ├── MainActivity.kt            # Compose 진입점
│   ├── camera/CameraPreview.kt    # 후면 미리보기·생명주기
│   ├── ui/CameraScreen.kt         # 권한·일곱 버튼·메시지
│   ├── ui/theme/                 # 기존 테마
│   ├── bridge/PythonBridge.kt     # Python 함수 호출·결과 전달
│   └── feedback/
│       ├── HapticFeedback.kt      # 테스트 진동
│       └── SpeechFeedback.kt      # 테스트 TTS
└── python/                       # 팀원들의 주 개발 영역
    ├── mock_inference.py         # 고정 Mock 문자열
    ├── frame_interface.py        # 공통 데이터·상황별 호출 연결
    ├── tactile_anomaly.py        # 점자블록 이상 담당
    ├── tactile_context.py        # 점형블록 주변 담당
    ├── walking_hazard.py         # 일반 보행 위험 담당
    └── overhead_hazard.py        # 머리 높이 장애물 담당
app/src/test/python/              # 표준 unittest 호출 연결 테스트
AGENTS.md                          # 공통 개발 지침
docs/contracts.md                  # 임시 입출력 계약
```

## 현재 테스트 기능
- 카메라 권한 요청과 후면 CameraX Preview.
- AI 인식 테스트: `선형 점자블록 감지 (Mock)` 고정 문자열 반환.
- 상황 판단 버튼 네 개: `PythonBridge → frame_interface.run_test → 해당 Python analyze` 호출 후 `아직 구현되지 않은 기능입니다` 표시.
- 진동 테스트: 150ms 진동 한 번.
- TTS 테스트: `보행 보조 서비스 음성 안내 테스트입니다.` 한국어 발화.
  기기에 TTS 엔진과 한국어 음성 데이터가 필요하다.

네 분석기의 본문은 TODO와 `return []`뿐이다. `build_frame`은 빈 공통 입력을 만들며 모델 출력 변환과 situations 자동 선택은 TODO다.
별도 라우터 없이 frame_interface.py가 지정된 상황 모듈을 직접 호출한다. 모델, 실시간 분석 파이프라인, 서버와 DB는 없다.
이 시제품은 실제 보행 안전성을 검증하지 않았다. 미탐지와 빈 결과는 안전을 의미하지 않는다.

## 목표 서비스 흐름
`카메라 → 하나 이상의 AI 모델 예측 → frame_interface.py에서 frame_id·objects·situations 구성 → 해당 상황 모듈 호출 → 판단 결과 → Kotlin 진동·TTS`

공통 처리 파일은 어떤 분석을 실행할지 정하고, 각 담당 모듈은 구체적 위험을 판단한다.
이 흐름은 향후 목표이며 현재 카메라 영상은 Python이나 AI에 전달되지 않는다. 자동 안내도 구현하지 않았다.
실제 모델 추론을 Kotlin/Python 중 어디서 실행할지는 모델 선정 후 결정한다.

## 테스트 화면에서 실제 서비스로의 전환
현재 일곱 버튼은 개발용이다. 최종 목표는 사용자가 시작을 누르면 카메라 인식·상황 판단·음성 및 진동 안내가 이어지는 서비스다. 시작/중지와 실시간 인식 연결은 아직 없다.

| 파일·코드 | 향후 처리 |
| --- | --- |
| mock_inference.py | 실제 추론 연결 검증 후 삭제 |
| CameraScreen.kt | 파일은 유지하고 테스트 버튼을 시작·중지·안내 화면으로 교체 |
| PythonBridge.kt | 유지. Mock infer()·버튼용 analyze(situation)를 실제 데이터·결과 전달로 교체 |
| frame_interface.py | 유지. 테스트용 run_test()는 삭제하고 build_frame → analyze로 연결 |
| 네 Python 상황 모듈 | 유지하고 담당 판단 로직 구현 |
| 카메라·진동·TTS | 유지·확장. Preview 외 프레임 분석 연결과 자동 안내는 추가 개발 필요 |

현재 `버튼 → PythonBridge → run_test → 빈 상황 함수` 경로를 향후 `시작 → 카메라 프레임 → AI 추론 → build_frame → analyze → 상황 모듈 → 안내`로 바꾼다.
PythonBridge 전체를 삭제하는 것이 아니라 테스트용 진입점을 실제 서비스 호출로 교체한다. 관련 테스트와 문서도 함께 갱신하며, 지금은 위 코드를 미리 삭제하지 않는다.

## 실행
1. `git clone https://github.com/angry-cat55/BlindWalk.git` 실행 후 폴더를 Android Studio로 연다.
2. **AGENTS.md를 먼저 읽고** docs/contracts.md의 계약을 확인한다.
3. SDK Manager에서 프로젝트가 요구하는 SDK 37을 설치하고 JDK 25를 준비한다.
4. PC에 Python 3.14를 설치해 `py -3.14`(Windows) 또는 `python3.14`(macOS/Linux)로 실행 가능하게 한다. Chaquopy가 자동 탐색하므로 개인 경로는 코드에 적지 않는다.
5. Gradle Sync 후 USB 디버깅을 허용한 기기 또는 arm64-v8a/x86_64 에뮬레이터를 선택하고 Run한다.
6. 카메라 권한을 허용하고 일곱 버튼을 확인한다. 화면이 작으면 버튼 영역을 스크롤한다.

Windows 빌드·기존 단위 테스트:
```powershell
.\gradlew.bat :app:assembleDebug :app:testDebugUnitTest
py -3.14 -m unittest discover -s app/src/test/python -v
```

macOS/Linux에서는 `./gradlew`를 사용한다. Android Studio 버전은 사용자가 입력한다.
Python 테스트는 macOS/Linux에서 `python3.14 -m unittest discover -s app/src/test/python -v`로 실행한다.
Gradle Wrapper와 기존 리소스·테스트는 유지한다.
협업은 `main`과 `feature/기능명` 브랜치만 사용한다. 작업 전 main을 pull하고 별도 feature 브랜치를 만든 뒤, 완료한 브랜치를 push해 main 대상 PR로 검토받는다. 자세한 명령과 규칙은 AGENTS.md를 따른다.
