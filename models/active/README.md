# 🤖 BlindWalk Active AI Models Specification

본 디렉토리는 온디바이스 시각장애인 보행 보조 시스템 `BlindWalk`에서 실시간 인지 및 거리 추정을 위해 사용하는 **현재 기본 활성 모델(Active Models)**을 보관합니다.

---

## 1. 모델 파일 구성

| 파일명 | 모델 종류 | 포맷 | 크기 | 입력 규격 | 역할 및 활용 환경 |
|---|---|---|---|---|---|
| **`yolo11n_seg_18cls.pt`** | YOLO11n-seg (18 Classes Master) | PyTorch | 5.8 MB | 640×640 (RGB) | PC/연구용 인스턴스 세그멘테이션 & 트래킹 (`ai_pipeline.py`) |
| **`yolo11n_seg_18cls.tflite`** | YOLO11n-seg (18 Classes Master) | TFLite FP32 | 11.2 MB | 640×640 (RGB) | **안드로이드 실기기(NPU/GPU 가속)** 앱 탑재용 (`assets`) |
| **`yolo11n_seg_16cls.pt`** | YOLO11n-seg (16 Classes Legacy) | PyTorch | 5.8 MB | 640×640 (RGB) | 16클래스 호환 가중치 |
| **`yolo11n_seg_16cls.tflite`** | YOLO11n-seg (16 Classes Legacy) | TFLite FP32 | 11.9 MB | 640×640 (RGB) | 16클래스 호환 가중치 |
| **`depth.onnx`** | MiDaS_small (Quantized) | ONNX | 16.2 MB | 256×256 (RGB) | 단안 깊이 추정 기반 정량적 미터 거리(`distance_m`) 산출 |

---

## 2. YOLO11n-seg 18클래스 최종 분류표 (Master)

모델 가중치 내부의 `model.names` 딕셔너리에 등록된 공식 18개 클래스 분류 체계입니다:

| ID | 영문 클래스명 | 한국어 명칭 | 4대 상황 연계 | 설명 및 보행 보조 목적 |
|:---:|---|---|:---:|---|
| **0** | `tactile_line` | 선형 점자블록 | `TACTILE_ANOMALY` | 보행자의 연속적 직진 보행 경로를 유도하는 선형 점자블록 |
| **1** | `tactile_dot` | 점형 점자블록 | `TACTILE_ANOMALY`<br>`TACTILE_CONTEXT` | 정지, 분기점, 계단/횡단보도 진입 전 위험 경고 랜드마크 |
| **2** | `stairs` | 계단 | `TACTILE_CONTEXT`<br>`WALKING_HAZARD` | 오르막/내리막 계단 단차 및 낙상 위험 구역 |
| **3** | `curb` | 연석 / 단차 | `WALKING_HAZARD` | 보도와 차도를 구분하는 경계석 및 수직 단차 (발 걸림 주의) |
| **4** | `crosswalk` | 횡단보도 | `TACTILE_CONTEXT` | 차도 횡단용 횡단보도 구역 (보행 신호 및 방향 유도) |
| **5** | `bollard` | 볼라드 | `WALKING_HAZARD`<br>`TACTILE_ANOMALY` | 보도 위 차량 진입 방지용 고정 말뚝 (무릎/정강이 충돌 주의) |
| **6** | `pole` | 기둥 | `WALKING_HAZARD` | 전봇대, 신호등 기둥, 금속/콘크리트 가로 시설물 기둥 |
| **7** | `tree_trunk` | 가로수 밑동 | `WALKING_HAZARD` | 보도 폭을 좁히는 가로수 몸통 및 돌출 뿌리 |
| **8** | `bicycle` | 이륜 이동체 | `WALKING_HAZARD` | 보도에 방치/주행 중인 자전거, 전동 킥보드, 오토바이 |
| **9** | `movable_signage`| 이동식 적재물 / 입간판 | `WALKING_HAZARD`<br>`TACTILE_ANOMALY` | 상가 앞 배너 입간판, 의자, 화분, 쇼핑카트 등 지면 장애물 |
| **10**| `vehicle` | 도로/보도 차량 | `WALKING_HAZARD` | 정차/주차 또는 보도로 진입하는 자동차, 트럭, 버스 |
| **11**| `person` | 보행자 | `WALKING_HAZARD` | 마주 오거나 앞서 걷는 일반 보행자 및 휠체어 이동약자 |
| **12**| `traffic_light` | 신호등 | `TACTILE_CONTEXT` | 횡단보도 및 교차로의 보행자 신호등 기둥 |
| **13**| `facility` | 공공 시설물 | `TACTILE_CONTEXT` | 버스 정류장 쉘터, 벤치, 우체통, 무인안내기(키오스크) |
| **14**| `overhang` | 머리 높이 돌출물 | `OVERHEAD_HAZARD` | 보행자 머리 높이(지상 1.5m~2.2m)로 튀어나온 간판, 처마, 나뭇가지 |
| **15**| `elevator` | 승강기 / 엘리베이터 | `TACTILE_CONTEXT` | 건물/지하철 엘리베이터 본체 및 출입문 |
| **16**| `elevator_sign` | 엘리베이터 표지판 | `TACTILE_CONTEXT` | 승강기 탑승 위치를 안내하는 시각 표지판 |
| **17**| `toilet_sign` | 화장실 표지판 | `TACTILE_CONTEXT` | 장애인/일반 화장실 위치 안내 표지판 |

---

## 3. MiDaS Depth 모델 (`depth.onnx`) 규격 및 거리 산출 원리

* **아키텍처**: Intel ISL `MiDaS_small` 경량 단안 깊이 추정 모델
* **입력**: `256 × 256 × 3` (RGB, ImageNet 정규화)
* **출력**: `1 × 256 × 256` (상대적 역심도 Disparity 맵)
* **거리(`distance_m`) 환산 공식**:
  1. 256×256 깊이 맵을 원본 4:3 해상도(640×480)로 선형 보간 리사이즈.
  2. 검출된 객체의 마스크 다각형(`contour`) 내부 또는 바운딩 박스 중심 ROI의 깊이 중앙값($D_{med}$)을 추출.
  3. 미터 거리 변환:
     $$\text{distance\_m} = \text{round}\left(\frac{K}{D_{med} + \epsilon}, 2\right)$$
     *(기본 $K=1000.0$, 최소 0.3m ~ 최대 15.0m 클리핑 적용)*

---

## 4. 파이썬 파이프라인 연동 예시

```python
from ai_pipeline import BlindWalkAIPipeline

# 활성 모델 로드
pipeline = BlindWalkAIPipeline(
    model_path="models/active/yolo11n_seg_16cls.pt",
    depth_model_path="models/active/depth.onnx"
)

# 4:3 카메라 프레임 처리 (frame_id=1)
frame_data = pipeline.process_frame(frame_id=1, image_bgr=camera_image)
# frame_data['objects'] 에 List[Detection] 담김
```

