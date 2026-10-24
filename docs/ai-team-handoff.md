# 카메라·AI·상황 판단 연결 안내

## 실제 호출 흐름

```text
CameraScreen: 자동 시작·권한 확인
 → CameraPreview: Preview + ImageAnalysis
 → FrameGate: 최소 200ms 간격으로 최신 프레임 선택
 → AiFrameInput.onFrameSelected(frameId, image)
     16:9 cropRect·rotationDegrees 적용 → 중앙 4:3 crop → 640×480 RGB
 → MobileInferenceEngine.infer
     YOLO11n-seg: 실제 객체·점자블록 마스크
     MiDaS: 상대 깊이와 AI팀 기준의 거리 환산
 → PythonBridge.analyzeFrame
     Detection 목록을 JSON으로 Python에 전달
 → frame_interface.analyze_json
     Detection 생성 → build_frame → select_situations → analyze
 → 2·3·4번 모듈 결과 목록
 → PythonBridge: List<FeedbackResult>로 변환
 → 메인 스레드 FeedbackCoordinator.submit
 → 선택 문구 표시 / SpeechFeedback / HapticFeedback
```

PC용 scripts/ai_pipeline.py는 별도 실행기다. 앱에서 이 Python 스크립트나 ultralytics를 실행하지 않는다.
기존 Mock·run_test 함수는 보존하지만 현재 앱 경로에서 사용하지 않는다.

## 파일별 담당

| 파일 | 역할 |
| --- | --- |
| ui/CameraScreen.kt | 자동 촬영·일시정지, 권한, 검출 표시·안내 카드, TTS·진동 수명 관리 |
| camera/CameraPreview.kt | CameraX 바인딩, 단일 분석 executor, 늦은 결과 폐기 |
| camera/FrameGate.kt | 최소 200ms 간격 선택. 실제 추론 FPS 보장은 아님 |
| camera/AiFrameInput.kt | 원본 crop·회전·RGB 크기 조절, 추론과 Python 분석 연결 |
| inference/MobileInferenceEngine.kt | YOLO GPU 우선·ONNX CPU 추론, 입력·shape·클래스 해시 검증, 거리 환산 |
| inference/YoloDecoder.kt | 정규화 xywh 복원·클래스별 NMS·점자블록 contour |
| bridge/PythonBridge.kt | Detection JSON 전달과 4키 결과의 Kotlin 변환 |
| Python frame_interface.py | Android JSON 진입점, build_frame, 상황 선택·호출 |
| feedback/FeedbackCoordinator.kt | 등급·반복 제한 후 안내 하나 선택 |

Kotlin 경로 기준은 app/src/main/java/com/example/blindwalk/다.

## 프레임 소유권과 성능

- ImageProxy·planes는 동기 onFrameSelected 안에서만 유효하다. 반환 후 CameraPreview가 finally에서 닫는다.
- raw buffer는 모델 입력 텐서가 아니다. 16:9 crop·회전 후 중앙 4:3을 잘라 RGB 640×480으로 맞춘다.
- 640px 너비는 기존 2번 담당 모듈의 기본 계약을 유지하기 위한 모바일 크기다. 모델 텐서는 별도 640×640이다.
- Preview는 30FPS 목표이고 분석은 단일 executor에서 최대 약5장/초다. 추론이 200ms보다 느리면 실제 처리량이 낮아진다.
- KEEP_ONLY_LATEST를 유지해 원본 프레임이 쌓이지 않게 한다. 별도 영상 저장·프레임 큐는 없다.
- 중지·뒤로·백그라운드 시 결과를 무효화한다. 실행 중 모델을 즉시 닫지 않고 분석 executor 뒤에서 해제한다.
- 선택된 결과는 메인 스레드에서만 Coordinator에 전달한다. AiFrameResult에 검출 목록·선택 시각·판단 결과를 담아 UI로 보낸다. 화면에는 bbox·점자블록 contour를 그리며 경로선은 만들지 않는다.

## 모델 전처리·출력 계약

- YOLO: FP32 NCHW [1,3,640,640], RGB/255. 4:3 영상에 회색114 letterbox를 적용한다.
- 출력 [1,54,8400]: normalized cx/cy/w/h + 이미 sigmoid된18class + mask32계수.
- prototype [1,32,160,160]. 점자블록만 실제 mask의 가장 큰 외곽선으로 복원하며 다른 클래스 contour는 None이다.
- confidence0.25, 클래스별 NMS IoU0.45, 상위 후보300·결과30개 제한이다. 임계값은 실제 영상 검증 대상이다.
- MiDaS: FP32 NCHW [1,3,256,256], RGB ImageNet 정규화. 출력 크기는 실행 결과에서 읽는다.
- 객체 contour 또는 bbox 중앙50% 내부의 깊이 셀들을 표본으로 삼는다. PC의 원본 크기 보간 후 중앙값과는 해상도 차이가 있다.
- K=1000 역심도 환산·0.3~15m 제한은 AI팀 PC 기준이다. 모델 자체가 보정된 미터 깊이를 보장하는 것은 아니다.
- 유효 깊이가 없으면 None이다. 모델 로드/실행 오류는 화면 오류로 전파하며 가짜 예측으로 대체하지 않는다.

원본 모델은 models/active에 유지하고 Gradle prepareAiAssets가 두 모델만 생성 assets에 넣는다.
classes는 app/src/main/assets/ai/labels.json에 metadata에서 추출했으며 SHA-256이 모델과 다르면 실행을 중단한다.
라이브러리는 LiteRT1.4.2·ONNX Runtime Android1.24.3이고 Python AI 패키지는 추가하지 않았다.

## 담당자 주의점

- Detection 구조와 결과 4키 계약은 [contracts](contracts.md)를 따른다.
- 모바일 id는 YOLO 프레임 내 후보 번호다. PC ByteTrack 결과와 구분하며 동일 객체 추적을 보장하지 않는다.
- 기존 2번 모듈의 자체 쿨다운과 Coordinator의 ID 기반 반복 제한은 이 제약이 있다. 이번 연결에서 담당자 로직은 수정하지 않았다.
- 2번 세션 상태는 최초 분석 때 reset_session으로 초기화한다.
- [상황 핸드오프](situation-handoff.md), [공통 안내 처리](feedback-coordinator.md)를 함께 읽는다.
- 합성 입력·검정 영상의 모델 실행 성공과 실제 보행 영상 정확도·실기기 FPS·한국어 음성 청취 검증을 구분한다.

## 가중치 교체 시 labels.json 갱신

새 TFLite의 입력·출력 shape가 동일한지 먼저 확인한다. 아래 코드는 클래스 목록과 해시만 갱신하며 다른 모델 구조를 자동 지원하지 않는다.

```python
import hashlib, json, zipfile
from pathlib import Path
model = Path("models/active/yolo11n_seg_18cls.tflite")
with zipfile.ZipFile(model) as archive:
    metadata = json.loads(archive.read("metadata.json"))
labels = [metadata["names"][str(i)] for i in range(len(metadata["names"]))]
Path("app/src/main/assets/ai/labels.json").write_text(
    json.dumps({"sha256": hashlib.sha256(model.read_bytes()).hexdigest(), "labels": labels},
               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
```

## 현재 화면과 분석 범위
Preview는 16:9 전체 영상이며 추론은 중앙 4:3만 사용한다. OverlayTransform은 이 중앙 crop 위치와 FIT_CENTER 여백을 복원한다. UI는 선택 시각 기준 1.2초 지난 검출을 지우고, 실제 안내 카드도 3초 후 지운다. 검출 표시 전환은 표시만 변경하며 추론·Python·피드백 실행 여부를 바꾸지 않는다. 일시정지·뒤로·백그라운드에서 세션을 정리하고 같은 화면에서 재시작한다.
