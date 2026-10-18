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

기존 버전은 유지했다. CameraX camera2/lifecycle/view만 Version Catalog에 추가했다.
개인 SDK 경로는 local.properties에서 설정하며 공유하지 않는다.

## 주요 구조
```text
app/src/main/java/com/example/blindwalk/
├── MainActivity.kt                 # Compose 진입점
├── camera/CameraPreview.kt         # 후면 미리보기·생명주기
├── ui/CameraScreen.kt              # 권한 요청·테스트 버튼·메시지
├── ui/theme/                      # 기존 Compose 테마
├── inference/MockInferenceEngine.kt # 고정 Mock 문자열
├── model/
│   ├── DetectionFrame.kt          # 임시 공통 입력
│   └── RiskEvent.kt               # 임시 판단 결과
├── situation/
│   ├── SituationAnalyzer.kt       # 공통 함수 계약
│   ├── TactileAnomalyAnalyzer.kt   # 점자블록 이상 담당
│   ├── TactileContextAnalyzer.kt   # 점형블록 주변 담당
│   ├── WalkingHazardAnalyzer.kt    # 일반 보행 위험 담당
│   └── OverheadHazardAnalyzer.kt   # 머리 높이 장애물 담당
└── feedback/
    ├── HapticFeedback.kt          # 짧은 진동 한 번
    └── SpeechFeedback.kt          # 한국어 테스트 발화
AGENTS.md                          # 공통 개발 지침
docs/contracts.md                  # 임시 입출력 계약
```

## 현재 테스트 기능
- 카메라 권한 요청과 후면 CameraX Preview.
- AI 인식 테스트: `선형 점자블록 감지 (Mock)` 고정 문자열 반환.
- 상황 판단 버튼 네 개: 각 담당 함수 호출 후 `아직 구현되지 않은 기능입니다` 표시.
- 진동 테스트: 150ms 진동 한 번.
- TTS 테스트: `보행 보조 서비스 음성 안내 테스트입니다.` 한국어 발화.
  기기에 TTS 엔진과 한국어 음성 데이터가 필요하다.

네 분석기의 본문은 TODO와 emptyList()뿐이다. 모델, 추론 프레임워크, 분석 파이프라인, 서버와 DB는 없다.
이 시제품은 실제 보행 안전성을 검증하지 않았다. 미탐지와 빈 결과는 안전을 의미하지 않는다.

## 실행
1. `git clone https://github.com/angry-cat55/PathSense.git` 실행 후 폴더를 Android Studio로 연다.
2. **AGENTS.md를 먼저 읽고** docs/contracts.md의 계약을 확인한다.
3. SDK Manager에서 프로젝트가 요구하는 SDK 37을 설치하고 JDK 25를 준비한다.
4. Gradle Sync 후 USB 디버깅을 허용한 Android 기기를 선택하고 Run한다.
5. 카메라 권한을 허용하고 일곱 버튼을 확인한다. 화면이 작으면 버튼 영역을 스크롤한다.

Windows 빌드·기존 단위 테스트:
```powershell
.\gradlew.bat :app:assembleDebug :app:testDebugUnitTest
```

macOS/Linux에서는 `./gradlew`를 사용한다. Android Studio 버전은 사용자가 입력한다.
Gradle Wrapper와 기존 리소스·테스트는 유지한다.
협업은 `main`과 `feature/기능명` 브랜치만 사용한다. 작업 전 main을 pull하고 별도 feature 브랜치를 만든 뒤, 완료한 브랜치를 push해 main 대상 PR로 검토받는다. 자세한 명령과 규칙은 AGENTS.md를 따른다.
