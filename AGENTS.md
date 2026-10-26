# 프로젝트 공통 지침

## 프로젝트 목적
ROKEY 부트캠프 스터디원 4명이 함께 개발하는 Android 온디바이스 AI 보행 보조 시제품이다.
모두가 AI 모델 학습, 추론 결과 분석, 상황 판단 로직 개발에 참여한다.
현재 코드는 가로 UI·카메라·실제 온디바이스 모델·Python 판단·공통 피드백을 연결한 시제품이다. 실제 보행 안전성과 거리 정확도는 검증 전이다.

## 최종적으로 만들 서비스
스마트폰 카메라 영상에서 점자블록 및 보행 위험을 인식하고, 시각장애인에게 상황에 맞는 음성·진동 안내를 제공하는 온디바이스 시제품을 목표로 한다.
점자블록 파손·가림·단절, 점형블록 주변 환경, 일반 보행 위험, 머리 높이 장애물의 네 상황을 다룬다. 서버·DB는 사용하지 않는다.
Kotlin은 CameraX·Compose UI·권한·진동·TTS와 Python 연결을 담당하고, Python은 공통 AI 결과 처리와 상황 판단을 담당한다.
목표 흐름은 `카메라 → 하나 이상의 AI 예측 → frame_interface.py → 해당 상황 모듈 → 판단 결과 → Kotlin 음성·진동 안내`이다.
`frame_interface.py`는 같은 프레임의 예측을 공통 `objects`로 정리하고 `situations`를 결정한 뒤 해당 모듈을 직접 호출한다. 별도 situation_router.py는 만들지 않는다.
세부 위험 판단은 담당 모듈에 둔다. 실제 모델 추론의 실행 언어와 엔진은 모델 선정 후 정하며, 동일 모델을 모듈마다 중복 실행하지 않는다.
이것은 최종 목표 설명이다. 현재 본 앱은 자동 가로 카메라 진입→같은 화면에서 일시정지/재시작 흐름과 초당 최대 약5장 원본 프레임 선택을 구현한다. Python 인터페이스는 Detection 목록을 묶고 클래스명으로 2·3·4 분석 대상을 자동 선택한다. 2번 점형 주변 판단·3번 위치와 클래스 기반 안내·4번 돌출물 존재 안내는 Python에 구현했다. 본 앱과 저장소 모델·Python 분석·공통 피드백을 연결했다. 실제 영상·기기 성능과 거리 정확도는 별도 검증 대상이다.

## 현재 카메라 입력 범위
- CameraPreview.kt는 Preview30FPS 목표와 ImageAnalysis를 바인딩한다. 기기·조명에 따른 실제 FPS는 별도 검증한다.
- FrameGate.kt가 단조 시각으로 직전 선택 후200ms 이상 지난 최신 프레임만 고른다. KEEP_ONLY_LATEST·전용 executor·finally close로 적체를 방지한다.
- camera/AiFrameInput.kt의 onFrameSelected(frameId, image)가 실제 AI 연결점이다. crop·회전 후 640×480으로 맞춰 Kotlin 추론을 실행하고 PythonBridge로 예측을 전달한다.
- 화면은 16:9이며 cropRect와 rotationDegrees 적용 후 중앙 4:3을 추가 crop해 추론한다. 원본 buffer와 모델 입력 텐서는 구분한다. 현재 모바일 전처리·NCHW 계약은 docs/contracts.md를 따른다.
- ImageProxy와 planes는 동기 콜백 안에서만 유효하며 반환 후 보관/접근하면 안 된다. AI 결과용 Python frame_data와 별개 계약이다.
- AI 연결 작업 전 docs/ai-team-handoff.md의 파일별 흐름·원본 데이터 소유권·현재/향후 경계도 확인한다.
- 일시정지·뒤로·백그라운드 시 프레임 선택과 카메라를 정리하며 같은 화면에서 다시 시작한다. jh-test 실험은 별개다.

## Skeleton에서 실제 서비스로 전환할 때
기존 일곱 테스트 버튼은 본 앱 UI에서 제거했다. Mock·Bridge·상황 모듈의 기존 테스트 함수는 보존되어 있지만 현재 화면에서는 호출하지 않는다.
현재 시작 동작은 카메라·프레임 선택·실제 모델·Python 분석·공통 안내까지 실행한다. 모델 정확도와 실제 보행 안전성은 보장하지 않는다.

- `mock_inference.py`는 테스트 전용이다. 실제 추론 연결을 검증한 뒤 삭제하고 Mock을 실제 예측으로 사용하지 않는다.
- `CameraScreen.kt`는 자동 촬영·일시정지/재시작 화면을 제공한다. 검출 영역과 선택된 판단 결과 문구도 표시한다.
- `PythonBridge.kt`는 Android↔Python 연결로 유지한다. Mock 호출용 `infer()`와 버튼용 `analyze(situation)`는 실제 데이터·판단 결과를 전달하는 호출로 교체한다. 기존 analyze(situation)는 보존된 테스트 진입점이며 실제 앱은 analyzeFrame→analyze_json 경로를 사용한다.
- `frame_interface.py`는 유지한다. 버튼 전용 `run_test()`는 삭제하고 실제 경로는 `build_frame → analyze`로 연결한다. 현재 build_frame은 전체 Detection 목록을 유지하고 situations 생략 시 2·3·4 분석 대상을 자동 선택한다.
- 네 Python 상황 모듈과 진동·TTS 파일은 유지한다. 현재 모바일은 Kotlin LiteRT·ONNX 추론과 결과 전달을 사용한다. Python 담당 모듈에서 모델을 중복 실행하지 않는다.
- 테스트 전용 함수 제거 시 이를 참조하는 버튼·Bridge·테스트·문서를 함께 정리한다. 공통 분석 호출 테스트는 유지하고 실제 계약에 맞게 갱신한다.

이 목록의 AI 관련 부분은 향후 전환 지침이다. 요청받지 않은 코드 삭제·실제 AI 인식·자동 안내를 미리 구현하지 않는다.

## AI 에이전트 작업 원칙
1. 시작 전 AGENTS.md, README.md, docs/contracts.md를 읽는다.
2. 기존 구조와 담당 모듈 역할을 먼저 파악한다.
3. 요청받은 기능과 관련된 파일만 수정한다.
4. 사용자가 요청하지 않은 기능은 임의로 구현하지 않는다.
5. 불필요한 리팩터링이나 구조 변경을 하지 않는다.
6. 코드는 짧고 이해하기 쉽게 작성한다.
7. 중요한 로직에는 간결한 한글 주석을 작성한다.
8. 기존 공통 함수와 데이터 타입을 우선 활용한다.
9. 새 라이브러리 추가 전 기존 의존성으로 해결 가능한지 확인한다.
10. 완료 후 수정 파일, 변경 이유, 실행한 테스트 결과와 한계를 설명한다.

불확실한 내용은 사실·추론·추측을 구분하고 확인 불가 시 모른다고 명시한다.
단순 동의보다 근거와 트레이드오프를 제시하고 더 나은 대안은 솔직하게 제안한다.
독립적인 읽기 작업이 둘 이상이고 시간·검증·컨텍스트 측면에서 이점이 있으면 서브에이전트를 사용한다.
결과는 메인 에이전트가 검증·통합하며 동일 파일 수정은 병렬화하지 않는다.
취업·스펙 질문은 목표 직무와 지역의 최신 공식 JD와 기술 동향을 검색·인용하고 반복되는 핵심 역량을 중심으로 조언한다.

## 팀원별 담당 모듈
- app/src/main/python/tactile_anomaly.py: 점자블록 이상 판단
- app/src/main/python/tactile_context.py: 점형블록 주변 환경 분석
- app/src/main/python/walking_hazard.py: 일반 보행 위험 판단
- app/src/main/python/overhead_hazard.py: 머리 높이 장애물 판단

각 담당자는 자신의 기능을 구현하며 다른 팀원 모듈을 임의로 수정하지 않는다.
공통 인터페이스나 다른 팀원 코드 수정이 필요하면 먼저 사용자에게 변경 내용과 영향을 설명한다.

## 공통 추론 규칙
실제 모델 추론은 Kotlin MobileInferenceEngine에서 공통으로 실행한다.
각 상황 판단 모듈은 공통으로 전달받은 AI 결과를 분석한다.
동일한 AI 모델을 여러 모듈이 중복 실행하지 않는 것을 원칙으로 한다.
저장소 모델 실행을 위해 LiteRT 1.4.2·ONNX Runtime Android 1.24.3만 사용한다. 새 엔진·모델 추가는 별도 요청 범위다.

## 공통 데이터 계약
모든 Python 상황 모듈은 `analyze(frame_data)` 함수를 따른다. `Detection.distance_m`은 거리 추정 불가 시 `None`이며 임의의 기본 거리로 대체하지 않는다. 점형 판단은 거리 미상·음수·비유한 값을 병합 전에 제외한다. `tactile_context`는 점형 주변 판단을 구현했으며 walking_hazard는 위치·클래스 기반 3번 안내를 구현했으며 4번은 overhang마다 돌출물 주의·CAUTION을 반환한다. 1번 모듈만 TODO 상태다.
공통 입력은 `frame_id`, `objects`, `situations`를 가진 Python 딕셔너리이며 반환은 판단 결과 목록이다. 결과 항목은 situation·object_id·message·priority를 가진 딕셔너리로 통일한다. priority는 INFO·CAUTION·URGENT다. 2·3·4번은 이 형식으로 반환하며 PythonBridge가 공통 결과를 Kotlin으로 변환한다. 상황 모듈 개발 전 docs/situation-handoff.md도 읽는다.
`situations`는 확정된 위험이 아니라 분석할 상황 종류의 목록이다. build_frame은 situations 생략 시 tactile_dot→TACTILE_CONTEXT, 지상 장애물 10종→WALKING_HAZARD, overhang→OVERHEAD_HAZARD를 자동 선택한다. 구체적 클래스 목록은 docs/contracts.md를 따른다. TACTILE_ANOMALY는 자동 선택하지 않는다. 직접 지정한 situations(빈 목록 포함)는 테스트 호환을 위해 유지한다.
Kotlin의 PythonBridge는 호출과 결과 전달만 담당하고 판단 로직은 넣지 않는다. Kotlin의 별도 상황 인터페이스·모델 타입을 중복 유지하지 않는다.
실제 모델 출력이 확정되면 공통 협의를 통해 변경할 수 있다.
계약 변경 시 docs/contracts.md도 함께 수정한다.

## AI-Native 개발 순서
1. 담당 기능과 관련 파일 확인
2. 기존 인터페이스와 입출력 확인
3. 구현 계획을 짧게 설명
4. 요청받은 기능만 구현
5. 가능한 범위에서 빌드 및 테스트
6. 구현 결과와 한계 보고

각 팀원은 AI 코딩 에이전트를 활용하되 공통 규칙을 준수한다.

## Android 개발 환경
기존 Android Studio 설정과 Gradle Wrapper를 유지한다.
Gradle, AGP, Kotlin, JDK 버전 호환성을 유지하고 Version Catalog로 의존성을 관리한다.
라이브러리나 빌드 설정 변경 시 이유를 설명한다.
Python 실행에는 Chaquopy 17.1.0과 Python 3.14를 사용한다. 현재 CPU 대상은 arm64-v8a·x86_64이며 외부 Python 패키지는 설치하지 않는다.
Python 담당자는 PC에서 표준 라이브러리만으로 테스트할 수 있게 Android 의존 코드를 상황 모듈에 넣지 않는다.
개인 파일 경로, SDK 경로, 비밀 정보를 코드에 하드코딩하지 않는다.

## GitHub 협업
- 브랜치는 `main`과 `feature/기능명`만 사용한다. `develop`, `release` 등 다른 종류의 브랜치는 만들지 않는다.
- `main`은 팀이 공유하는 기준 코드다. 가능한 한 항상 빌드 가능한 상태로 유지한다.
- `feature/기능명`은 각자의 작업 공간이다. 기능 추가뿐 아니라 오류 수정·문서 작업도 반드시 별도 feature 브랜치에서 시작한다.
- `main`에서 파일을 수정하거나 직접 커밋·푸시하지 않는다. 로컬에서 feature를 main에 직접 merge하거나 main으로 직접 push하지 않는다.
- 완료한 feature 브랜치를 GitHub에 push한 뒤, `base: main` / `compare: 자신의 feature 브랜치`로 Pull Request(PR, 변경 검토 요청)를 올린다.
- PR 검토 후 GitHub에서 main으로 통합한다. AI 에이전트는 사용자 요청 없이 PR을 merge하지 않는다.
- 다른 담당 모듈을 불필요하게 수정하지 않는다.
- 공통 파일 변경 시 영향 범위를 PR에 명시한다.
- 커밋 메시지는 `타입: 한국어 요약` 형식으로 짧게 작성한다. 예: `feat: 초기 스켈레톤 구성`.
- 변경 목적에 맞는 접두사를 사용한다: `feat:` 기능 추가, `fix:` 오류 수정, `docs:` 문서 변경, `refactor:` 리팩터링, `test:` 테스트, `chore:` 설정·기타 작업.
- 명시적인 요청 없이 Git 초기화, 원격 설정, Commit, Push, Merge를 실행하지 않는다.

### 새 작업을 시작할 때
진행 중인 변경이 있다면 먼저 기존 feature 브랜치에 보존한다. 변경을 버리는 명령은 사용하지 않는다.
작업 폴더가 깨끗한지 확인한 뒤 main을 최신 상태로 받고, 그 main에서 새 브랜치를 만든다.

```bash
git status
git switch main
git pull --ff-only origin main
git switch -c feature/tactile-anomaly
```

`feature/tactile-anomaly`는 예시다. 담당 작업마다 `feature/tactile-context`, `feature/walking-hazard`, `feature/overhead-hazard`처럼 서로 다른 이름을 정한다.
`pull`이 실패하거나 충돌이 발생하면 원인을 확인하고 해결한 뒤 진행한다. 실패를 무시하고 새 브랜치를 만들지 않는다.
이미 작업 중인 브랜치를 이어서 개발할 때는 새 브랜치를 만들지 않고 해당 브랜치로 이동한다.

### 작업을 완료했을 때
빌드·테스트 후 변경 파일을 확인하고, 자신의 파일만 선택해 커밋한다.

```bash
git status
git add <수정한 파일 경로>
git commit -m "feat: 점자블록 이상 판단 추가"
git push -u origin feature/tactile-anomaly
```

위 명령의 파일 경로·커밋 내용·브랜치명은 실제 작업에 맞게 바꾼다.
GitHub 저장소에서 Compare & pull request를 누르고 대상이 main인지 확인한다.
PR에는 변경 이유, 수정 모듈, 공통 파일 영향, 테스트 결과와 미검증 항목을 적는다.
PR 검토 중 수정도 같은 feature 브랜치에 커밋·push한다. push만으로 main에 반영되지는 않는다.
PR 병합 후 다음 작업은 다시 `main 이동 → pull → 새 feature 생성` 순서로 시작한다.
타인의 커밋을 덮어쓰는 force push는 하지 않는다.

## 안전 및 검증
학습 및 공모전용 시제품이며 실제 보행 안전성을 검증한 제품이 아니다.
Mock 출력과 실제 AI 예측을 구분한다.
AI가 탐지하지 못했다는 이유로 보행환경이 안전하다고 판단하지 않는다.
테스트하지 않은 기능을 정상 동작한다고 주장하지 않는다.

## 3번 모듈의 현재 정책
walking_hazard는 image_width·image_height를 받아 객체 하단 15%와 점자블록 contour/중앙 사다리꼴의 겹침을 검사한다. 크기가 없으면 []를 반환한다. 차량 URGENT, 사람·시설물 INFO, 나머지 대상 7종 CAUTION은 초기 클래스별 안내 정책이다. 거리로 등급을 정하지 않으며 음성·진동을 직접 실행하지 않는다. 상세 기준은 docs/contracts.md를 따른다.

## 4번 모듈의 현재 정책
overhead_hazard는 전체 objects에서 overhang만 골라 객체마다 돌출물 주의·CAUTION을 반환한다. 위치·거리·신뢰도로 추가 필터링하지 않으며 영상 크기가 없어도 동작한다. 하위 클래스 추측·충돌 임박 판단·TTS·진동·반복 제한은 수행하지 않는다.

## 공통 안내 처리
feedback/FeedbackCoordinator.kt는 Kotlin 결과 목록을 받아 등급·최근 안내 기록으로 하나를 선택한다. 메인 스레드에서 세션 동안 한 인스턴스를 유지하고 중지 시 reset한다. 최근 기록은 메모리만 사용한다. PythonBridge 변환과 CameraScreen의 submit 호출을 연결했다. 작업 전 docs/feedback-coordinator.md를 읽는다. 2번 모듈의 자체 쿨다운은 담당자 협의 없이 수정하지 않는다.

## 모바일 추론 연결
MobileInferenceEngine은 실제 NCHW 입력·출력 shape 및 가중치 SHA-256과 labels.json을 검증한다. 640×480은 2번 모듈의 기존 너비 계약을 유지하기 위한 모바일 분석 해상도다. infer 직후 ID는 후보 번호이며 AiFrameInput의 ObjectTracker가 세션 추적 ID로 교체한다(ByteTrack 아님). 마지막 실제 관측 선택 시각(elapsedRealtime ms)에서 1000ms 초과 시 만료하며, 같은 세션에서 ID를 재사용하지 않는다. 유실 기록은 최대256개이며 UI·Python에는 현재 관측만 전달한다. 세부 계약은 docs/contracts.md를 따른다. 2번 쿨다운과 공통 안내 정책은 유지하며 추적 ID도 객체 동일성을 보장하지 않는다. 모델·추적 상태는 분석 executor에서 닫고 중지된 세션의 결과는 UI에 전달하지 않는다.


## 현재 GPU 실행 정책
YOLO는 LiteRT GPU Delegate 우선이며 실패 시 CPU로 복귀한다. depth.onnx는 ONNX Runtime CPU 실행이다. GPU 자원의 생성·호출·해제는 동일한 분석 executor에서 수행한다. 실제 backend와 연산 위임 로그를 확인하며 GPU 사용만으로 전체 파이프라인5FPS 또는 정확도 검증 완료를 주장하지 않는다. 측정 조건과 결과는 README.md를 참고한다.

## 현재 카메라 UI 계약
화면은 16:9 전체 영상, 추론 입력은 중앙 4:3 crop 후 640×480이다. 넓은 화면 양옆은 분석하지 않는다. AiFrameResult로 추적 ID를 붙인 현재 관측 목록과 단조 선택 시각, Python 판단 결과를 함께 반환한다. 검출 표시는 1.2초, 안내 카드는 3초 후 제거한다. 새 결과(빈 목록 포함)로 전체 검출을 교체하며 유실 트랙을 표시하지 않는다. 로고 메인 화면·앱명 옆 장식·카드 왼쪽 강조선은 사용하지 않는다.
