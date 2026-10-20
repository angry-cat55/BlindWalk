# 가로 UI·카메라 입력 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task.

**Goal:** 가로 메인→시작→4:3 카메라→중지/뒤로→메인, Preview30FPS 목표와 최대5장/초 선택 연결점.
**Architecture:** 기존 Compose/CameraX를 유지한다. Preview와 ImageAnalysis를 함께 바인딩하고 단일 분석 스레드에서 최신 프레임만 선택한다.
**Tech Stack:** 기존 Kotlin·Compose·CameraX1.6.2. 새 라이브러리 없음.
**Spec:** 이 대화에서 선택한 가로 시안1과 메인/촬영 두 화면 흐름.

## Global Constraints
- 본 앱만 수정, jh-test 보존. AI·상황 판단·모델 전처리·Python 프레임 전달 미구현.
- 가로4:3 카메라 입력, 모델 입력 크기·정규화·색상 형식은 미정.
- 큰 시작/중지·TalkBack·상태 표시. AI 미연결·프레임 목표 문구는 UI에 넣지 않음.
- Commit/Push/PR은 이번 요청에 없으므로 수행하지 않음.

## Review Focus
- 권한 거절/권한 설정 후 복귀: 메인에서 재시도 가능.
- 중지/뒤로/백그라운드: 분석·카메라 정리, 오래된 콜백 무시.
- 느린 소비자: KEEP_ONLY_LATEST, 별도 큐 없음, 반드시 ImageProxy.close.
- 가로 회전: 회전 메타데이터와 cropRect 계약, 4:3 요청 실패는 명시.
- TalkBack·큰 글꼴: 상태 전환 알림, 조작 영역 접근 가능.

## Tasks
- [x] FrameGate 테스트 실패 확인 후 200ms 간격·지연 후 몰아보내기 방지 구현.
- [x] CameraPreview: Preview+ImageAnalysis, 전용 executor, 4:3·30FPS 목표, AiFrameInput 연결점.
- [x] CameraScreen: 가로 메인/촬영·권한·뒤로·생명주기·접근성, Manifest 방향.
- [x] README·AGENTS·contracts에 현재 구현과 AI 전달 규칙 반영.
- [x] 빌드·단위 테스트·lint·기존 Python 테스트·실기기 화면/로그 검증.

## Execution notes
기존 경로를 사용하는 Android Studio와 연결된 휴대폰에서 검증하기 위해 현재 체크아웃을 유지하고 feature 브랜치로 분리한다. 미추적 jh-test는 보존했다.

FrameGate 미구현 상태에서 Unresolved reference 실패를 확인한 뒤 구현했다. 최종 JVM3개·Python3개·assembleDebug·lintDebug 통과.
SM-N971N에서 메인/시작/중지/뒤로/홈 이동 후 메인 복귀를 확인했다. 카메라 분석 입력 약29.7~29.9FPS, 선택 약4.5~5FPS. Preview 표시 FPS나 AI 추론 FPS의 보장은 아니다.
실제 TalkBack 발화·큰 글꼴 설정·권한 영구 거절 화면은 미검증이다. semantics와 권한 설정 복구 경로는 구현했다. commit/push는 하지 않았다.
