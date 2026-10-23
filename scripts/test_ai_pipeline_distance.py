"""실제 모델 실행 없이 깊이 실패 전달·거리 변환 경로를 검증한다."""
import contextlib
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
# YOLO 모델 로딩이나 다운로드 없이 검출 출력을 주입한다.
with patch.dict(sys.modules, {"ultralytics": SimpleNamespace(YOLO=Mock())}):
    from ai_pipeline import BlindWalkAIPipeline
import frame_interface
import tactile_context


class PipelineDistanceTest(unittest.TestCase):
    def setUp(self):
        tactile_context.reset_state()
        self.pipeline = BlindWalkAIPipeline.__new__(BlindWalkAIPipeline)
        self.pipeline.depth_sess = None
        self.pipeline.scale_k = 1000.0
        self.pipeline.enable_tracking = False
        self.pipeline.conf_threshold = 0.25
        self.pipeline.device = "cpu"
        self.pipeline.class_names = {0: "tactile_dot"}
        box = SimpleNamespace(cls=[0], conf=[0.9], id=None,
                              xyxy=np.array([[280, 200, 360, 240]]))
        self.pipeline.yolo = Mock(return_value=[SimpleNamespace(boxes=[box], masks=None)])
        self.image = np.zeros((480, 640, 3), dtype=np.uint8)

    def test_missing_depth_model_preserves_detection_without_distance(self):
        objects = self.pipeline.process_image(self.image)
        self.assertEqual(len(objects), 1)
        self.assertIsNone(objects[0].distance_m)
        self.assertIsNone(objects[0].to_dict()["distance_m"])

    def test_depth_inference_error_returns_unknown_distance(self):
        self.pipeline.depth_sess = Mock()
        self.pipeline.depth_sess.run.side_effect = RuntimeError("depth test error")
        with contextlib.redirect_stderr(io.StringIO()) as warnings:
            objects = self.pipeline.process_image(self.image)
        self.assertIsNone(objects[0].distance_m)
        self.assertIn("depth test error", warnings.getvalue())

    def test_valid_depth_is_converted(self):
        with patch.object(self.pipeline, "_estimate_depth_map", return_value=np.full((480, 640), 500.0)):
            objects = self.pipeline.process_image(self.image)
        self.assertAlmostEqual(objects[0].distance_m, 2.0, places=5)

    def test_invalid_depth_values_do_not_become_numeric_distances(self):
        for value in (float("nan"), float("inf"), float("-inf"), 0.0, -1.0):
            with self.subTest(value=value):
                depth = np.full((480, 640), value)
                with patch.object(self.pipeline, "_estimate_depth_map", return_value=depth):
                    objects = self.pipeline.process_image(self.image)
                self.assertIsNone(objects[0].distance_m)

    def test_missing_depth_does_not_pass_five_meter_context_selection(self):
        frame = self.pipeline.process_frame(1, self.image)
        self.assertIn("TACTILE_CONTEXT", frame["situations"])
        self.assertEqual(frame_interface.analyze(frame), [])

    def test_valid_depth_reaches_context_announcement(self):
        with patch.object(self.pipeline, "_estimate_depth_map", return_value=np.full((480, 640), 500.0)):
            frame = self.pipeline.process_frame(1, self.image)
        result = frame_interface.analyze(frame)
        self.assertEqual(len(result), 1)
        self.assertIn("2.0m", result[0]["message"])


if __name__ == "__main__":
    unittest.main()
