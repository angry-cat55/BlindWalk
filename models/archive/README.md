# 📦 BlindWalk Archived Models (구버전 실험 모델 보관소)

본 디렉토리는 초기 프로토타입 개발 및 단계별 성능 비교 과정에서 생성되었던 구버전 모델 가중치 파일들을 보관합니다.

---

## 1. 보관 모델 목록

| 파일명 | 모델 구조 | 포맷 | 크기 | 학습 데이터 및 설명 |
|---|---|---|---|---|
| **`yolo11n_seg_18cls.pt`** | YOLO11n-seg (18cls) | PyTorch | 5.8 MB | 18개 세부 클래스 초기 실험 모델 (mAP 0.65 수준) |
| **`yolo11n_seg_18cls.tflite`** | YOLO11n-seg (18cls) | TFLite FP32 | 11.2 MB | 18개 클래스 모바일 변환 모델 |
| **`yolo11n_seg_16cls.pt`** | YOLO11n-seg (16cls) | PyTorch | 5.8 MB | 연석/노면 포함 16개 클래스 초기 실험 모델 |
| **`yolo11n_seg_16cls.tflite`** | YOLO11n-seg (16cls) | TFLite FP32 | 11.9 MB | 16개 클래스 모바일 변환 모델 |

---

## 2. 아카이브 사유
- **연석(`curb`) 및 배경 오학습 문제**: 16/18 클래스 모델은 연석과 인도 바닥의 라벨 모호성으로 인해 점자블록 마스크 mAP가 0.46 수준에 머물렀습니다.
- **소실점 극소 노이즈**: 20×20px 미만 원경 노이즈로 인한 다운샘플링 왜곡 현상이 존재했습니다.
- **최신 활성 모델로의 대체**: 상기 문제점을 전수 정제한 `dataset_unified_11cls_pruned20px` 데이터셋과 백본을 3.1배 스케일업한 **`yolo11s_seg_11cls.tflite` (mAP50 0.782)**로 전환하여 [`models/active/`](../active/)에 단독 배치하였습니다.
