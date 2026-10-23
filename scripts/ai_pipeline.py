#!/usr/bin/env python3
"""
BlindWalk AI Pipeline (YOLO11n-seg + MiDaS Depth + ByteTrack Tracking)
- 4:3(예: 640x480) 카메라 입력에 대해 전처리/추론/후처리를 일원화하여 처리합니다.
- 모델 파일(가중치) 변경 시 클래스 목록(model.names)을 런타임에 동적으로 감지합니다.
- ByteTrack 다중 객체 추적(MOT)을 지원하여 연속 프레임 간 동일 객체에 지속적인 고유 ID(track_id)를 부여합니다.
- 모든 객체에 대해 BBox [x1, y1, x2, y2] 및 외곽선 다각형 Contour [[x, y], ...]를 동시 추출합니다.
- MiDaS 단안 깊이 추정 모델(depth.onnx)을 결합하여 각 객체의 추정 거리(distance_m)를 산출합니다.
- 최종 결과를 표준 Detection 데이터클래스 및 frame_data 딕셔너리로 패키징합니다.
"""

import math
import os
import sys
from typing import List, Dict, Any, Optional
import cv2
import numpy as np
import onnxruntime as ort
from ultralytics import YOLO

# BlindWalk의 공통 python 모듈 경로 등록 (app/src/main/python)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
APP_PYTHON_DIR = os.path.join(PROJECT_ROOT, "app", "src", "main", "python")
if APP_PYTHON_DIR not in sys.path:
    sys.path.insert(0, APP_PYTHON_DIR)

from detection import Detection
import frame_interface


class BlindWalkAIPipeline:
    def __init__(
        self,
        model_path: Optional[str] = None,
        depth_model_path: Optional[str] = None,
        conf_threshold: float = 0.25,
        scale_k: float = 1000.0,
        device: str = "cpu",
        enable_tracking: bool = True,
        tracker: str = "bytetrack.yaml",
    ):
        """
        AI 파이프라인 초기화
        :param model_path: YOLO 세그멘테이션 모델 경로 (.pt, .onnx, .tflite)
        :param depth_model_path: MiDaS ONNX 모델 경로 (.onnx)
        :param conf_threshold: 객체 검출 신뢰도 임계값
        :param scale_k: 깊이(Disparity) -> 미터 거리(m) 변환 스케일 계수
        :param device: 'cpu' 또는 'cuda'
        :param enable_tracking: ByteTrack 객체 지속 추적 활성화 여부
        :param tracker: 트래커 설정 파일 (기본값: 'bytetrack.yaml')
        """
        self.conf_threshold = conf_threshold
        self.scale_k = scale_k
        self.device = device
        self.enable_tracking = enable_tracking
        self.tracker = tracker

        # 기본 모델 경로 탐색 (models/active/ 18cls 우선)
        if model_path is None:
            default_18 = os.path.join(PROJECT_ROOT, "models", "active", "yolo11n_seg_18cls.pt")
            default_16 = os.path.join(PROJECT_ROOT, "models", "active", "yolo11n_seg_16cls.pt")
            if os.path.exists(default_18):
                model_path = default_18
            elif os.path.exists(default_16):
                model_path = default_16
            else:
                model_path = "yolo11n-seg.pt"

        if depth_model_path is None:
            default_depth = os.path.join(PROJECT_ROOT, "models", "active", "depth.onnx")
            depth_model_path = default_depth

        self.model_path = model_path
        self.depth_model_path = depth_model_path

        # 1. YOLO 모델 로드 및 클래스명 동적 감지
        self.yolo = None
        self.class_names: Dict[int, str] = {}
        self.load_yolo_model(model_path)

        # 2. MiDaS Depth 모델 로드
        self.depth_sess = None
        self.load_depth_model(depth_model_path)

    def load_yolo_model(self, model_path: str):
        """YOLO 모델 가중치를 동적으로 로드하고 클래스 목록을 갱신한다."""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"YOLO 모델 가중치 파일을 찾을 수 없습니다: {model_path}")
        self.yolo = YOLO(model_path)
        # 모델 메타데이터로부터 클래스명 자동 획득 (동적 적응)
        self.class_names = self.yolo.names if hasattr(self.yolo, "names") else {}
        self.model_path = model_path

    def load_depth_model(self, depth_model_path: str):
        """MiDaS ONNX 모델을 로드한다."""
        if os.path.exists(depth_model_path):
            self.depth_sess = ort.InferenceSession(depth_model_path, providers=["CPUExecutionProvider"])
            self.depth_model_path = depth_model_path
        else:
            self.depth_sess = None

    def reset_tracking(self):
        """새 영상 또는 카메라 세션 재시작 시 트래커 상태를 초기화한다."""
        if hasattr(self.yolo, "predictor") and self.yolo.predictor is not None:
            self.yolo.predictor.trackers = None

    def _estimate_depth_map(self, img_bgr: np.ndarray) -> Optional[np.ndarray]:
        """입력 이미지와 동일한 해상도의 상대 깊이 맵(2D float32)을 추정한다."""
        if self.depth_sess is None:
            return None

        h, w = img_bgr.shape[:2]
        # 1) 256x256 RGB 리사이즈 및 ImageNet 정규화
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(img_rgb, (256, 256)).astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        normalized = (resized - mean) / std
        tensor_in = np.transpose(normalized, (2, 0, 1))[np.newaxis, ...]

        # 2) ONNX 세션 추론
        try:
            raw_depth = self.depth_sess.run(None, {"input": tensor_in})[0][0]
        except Exception as exc:
            # 깊이 추론 실패는 임의 거리 대신 거리 미상으로 전달한다.
            print(f"깊이 추론 실패: {exc}", file=sys.stderr)
            return None

        # 3) 원본 4:3 영상 크기로 선형 복원
        depth_map = cv2.resize(raw_depth, (w, h), interpolation=cv2.INTER_LINEAR)
        return depth_map

    def process_image(self, img_bgr: np.ndarray) -> List[Detection]:
        """
        단일 프레임 이미지(4:3 등 임의 해상도)를 입력받아 Detection 객체 목록을 생성한다.
        - 트래킹 활성화 시 연속 프레임 간 동일 객체에 일관된 track_id를 부여한다.
        - 모든 객체에 대해 BBox와 Contour를 모두 추출한다.
        - Depth 모델로부터 객체의 distance_m을 측정한다.
        """
        h, w = img_bgr.shape[:2]

        # 1. YOLO 인스턴스 세그멘테이션 및 객체 추적(ByteTrack)
        if self.enable_tracking:
            yolo_res = self.yolo.track(
                img_bgr,
                conf=self.conf_threshold,
                persist=True,
                tracker=self.tracker,
                verbose=False,
                device=self.device,
            )[0]
        else:
            yolo_res = self.yolo(
                img_bgr,
                conf=self.conf_threshold,
                verbose=False,
                device=self.device,
            )[0]

        # 2. MiDaS 깊이 맵 추정
        depth_map = self._estimate_depth_map(img_bgr)

        detections: List[Detection] = []
        if yolo_res.boxes is None:
            return detections

        for i, box in enumerate(yolo_res.boxes):
            cls_id = int(box.cls[0])
            class_name = self.class_names.get(cls_id, f"class_{cls_id}")
            confidence = float(box.conf[0])
            xyxy = [int(x) for x in box.xyxy[0].tolist()]

            # 트래커가 부여한 지속 ID(track_id) 우선 사용
            track_id = int(box.id[0]) if (box.id is not None) else (i + 1)

            # BBox 유효 범위 클리핑
            x1 = max(0, min(w - 1, xyxy[0]))
            y1 = max(0, min(h - 1, xyxy[1]))
            x2 = max(0, min(w - 1, xyxy[2]))
            y2 = max(0, min(h - 1, xyxy[3]))
            clamped_bbox = [x1, y1, x2, y2]

            # 3. 모든 객체에 대해 Contour 추출 및 경량화 (approxPolyDP)
            contour = None
            has_mask = yolo_res.masks is not None and len(yolo_res.masks.xy) > i and len(yolo_res.masks.xy[i]) > 2
            if has_mask:
                raw_pts = [[int(pt[0]), int(pt[1])] for pt in yolo_res.masks.xy[i]]
                pts_arr = np.array(raw_pts, dtype=np.int32).reshape((-1, 1, 2))
                epsilon = 0.005 * cv2.arcLength(pts_arr, True)
                approx = cv2.approxPolyDP(pts_arr, epsilon, True)
                contour = approx.reshape(-1, 2).tolist()

            # 4. 거리(distance_m) 계산
            distance_m = None  # 깊이 결과가 없으면 거리 미상
            if depth_map is not None:
                if has_mask and contour and len(contour) >= 3:
                    # 마스크 다각형 내부 깊이값 샘플링
                    mask = np.zeros((h, w), dtype=np.uint8)
                    cv2.fillPoly(mask, [np.array(contour, dtype=np.int32)], 1)
                    depth_vals = depth_map[mask == 1]
                    depth_val = float(np.median(depth_vals)) if len(depth_vals) > 0 else float(depth_map[(y1 + y2) // 2, (x1 + x2) // 2])
                else:
                    # BBox 중심 50% ROI 영역 깊이값 샘플링
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    rw = max(1, (x2 - x1) // 4)
                    rh = max(1, (y2 - y1) // 4)
                    roi = depth_map[max(0, cy - rh) : min(h, cy + rh), max(0, cx - rw) : min(w, cx + rw)]
                    depth_val = float(np.median(roi)) if roi.size > 0 else float(depth_map[cy, cx])

                # 상대 깊이 -> 미터 단위 변환 및 클리핑 (0.3m ~ 15.0m)
                if math.isfinite(depth_val) and depth_val > 0:
                    estimated_distance = self.scale_k / (depth_val + 1e-4)
                    if math.isfinite(estimated_distance) and estimated_distance > 0:
                        # 대상 선정 전에는 정밀도를 유지한다. 반올림은 표시 시에만 한다.
                        distance_m = max(0.3, min(15.0, estimated_distance))

            det = Detection(
                id=track_id,
                class_name=class_name,
                confidence=round(confidence, 4),
                distance_m=distance_m,
                bbox=clamped_bbox,
                contour=contour,
            )
            detections.append(det)

        return detections

    def process_frame(
        self,
        frame_id: int,
        img_bgr: np.ndarray,
        situations: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        카메라 프레임 단위 통합 인터페이스:
        frame_id와 이미지를 입력받아 Detection 목록을 산출하고, 공통 frame_data 딕셔너리로 반환한다.
        """
        detections = self.process_image(img_bgr)
        return frame_interface.build_frame(frame_id=frame_id, objects=detections, situations=situations)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="BlindWalk AI Pipeline Runner with Tracking")
    parser.add_argument("--image", type=str, help="테스트할 이미지 파일 경로")
    parser.add_argument("--test-sample", action="store_true", help="내장 샘플 또는 4:3 더미 영상으로 테스트 실행")
    parser.add_argument("--video", type=str, help="테스트할 동영상 파일 경로")
    parser.add_argument("--no-track", action="store_true", help="객체 추적(ByteTrack) 비활성화")
    args = parser.parse_args()

    enable_track = not args.no_track
    print(f"[BlindWalk] AI Pipeline 초기화 중 (객체 추적: {'ON' if enable_track else 'OFF'})...")
    pipeline = BlindWalkAIPipeline(enable_tracking=enable_track)
    print(f"[BlindWalk] 모델 로드 완료: {pipeline.model_path}")
    print(f"[BlindWalk] 감지된 클래스 수: {len(pipeline.class_names)}종")

    if args.video and os.path.exists(args.video):
        cap = cv2.VideoCapture(args.video)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = int(fps / 5) # 5 FPS (200ms)
        frame_idx = 0
        proc_idx = 0
        print(f"\n[BlindWalk] 동영상 추적 테스트 시작: {args.video} (200ms 간격 5 FPS)")
        while cap.isOpened() and proc_idx < 10:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % step == 0:
                proc_idx += 1
                h, w = frame.shape[:2]
                target_w = int(h * 4.0 / 3.0)
                crop_4_3 = frame[:, (w - target_w)//2 : (w - target_w)//2 + target_w]
                resized = cv2.resize(crop_4_3, (640, 480))
                frame_data = pipeline.process_frame(frame_id=proc_idx, img_bgr=resized)
                time_s = frame_idx / fps
                print(f"[Frame {proc_idx:02d} | T={time_s:.2f}s] 검출 객체 {len(frame_data['objects'])}개:")
                for o in frame_data['objects']:
                    print(f"   • [ID: {o.id}] {o.class_name} | conf: {o.confidence:.2f} | 거리: {o.distance_m}m")
            frame_idx += 1
        cap.release()
        print("\n=== [동영상 객체 추적 테스트 성공] ===")

    elif args.image and os.path.exists(args.image):
        test_img = cv2.imread(args.image)
        frame_data = pipeline.process_frame(frame_id=1, img_bgr=test_img, situations=["TACTILE_ANOMALY"])
        print("\n=== [처리 결과 frame_data] ===")
        print(f"Frame ID: {frame_data['frame_id']}")
        for obj in frame_data["objects"]:
            print(f"  • [ID: {obj.id}] {obj.class_name} | conf: {obj.confidence:.2f} | 거리: {obj.distance_m}m")

    elif args.test_sample:
        sample_path = os.path.join(PROJECT_ROOT, "..", "AI_인지", "data", "tactile_unified_seg", "images", "val", "val_00518_186_barrier_free.jpg")
        test_img = cv2.imread(sample_path) if os.path.exists(sample_path) else np.zeros((480, 640, 3), dtype=np.uint8)
        frame_data = pipeline.process_frame(frame_id=1, img_bgr=cv2.resize(test_img, (640, 480)))
        print("\n=== [단일 샘플 처리 결과] ===")
        for obj in frame_data["objects"]:
            print(f"  • [ID: {obj.id}] {obj.class_name} | conf: {obj.confidence:.2f} | 거리: {obj.distance_m}m")
