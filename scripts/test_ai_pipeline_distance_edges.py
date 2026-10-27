"""가짜 검출·ONNX 출력으로 거리 경계와 마스크/프레임 전달을 검증한다."""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
with patch.dict(sys.modules, {"ultralytics": SimpleNamespace(YOLO=Mock())}):
    from ai_pipeline import BlindWalkAIPipeline
import frame_interface
import tactile_context


def box(bbox, class_id=0, track_id=None):
    return SimpleNamespace(cls=[class_id], conf=[0.923456], id=track_id,
                           xyxy=np.array([bbox], dtype=np.float32))


class PipelineDistanceEdgesTest(unittest.TestCase):
    def setUp(self):
        tactile_context.reset_state()
        self.pipeline = BlindWalkAIPipeline.__new__(BlindWalkAIPipeline)
        self.pipeline.depth_sess = None
        self.pipeline.scale_k = 1000.0
        self.pipeline.enable_tracking = False
        self.pipeline.conf_threshold = 0.25
        self.pipeline.device = "cpu"
        self.pipeline.tracker = "bytetrack.yaml"
        self.pipeline.class_names = {0: "tactile_dot", 1: "person"}
        self.image = np.zeros((48, 64, 3), dtype=np.uint8)
        self.set_result([box([28, 20, 36, 28])])

    def set_result(self, boxes, polygons=None):
        masks = None if polygons is None else SimpleNamespace(xy=polygons)
        self.result = SimpleNamespace(boxes=boxes, masks=masks)
        self.pipeline.yolo = Mock(return_value=[self.result])

    def detect(self, depth):
        with patch.object(self.pipeline, "_estimate_depth_map", return_value=depth):
            return self.pipeline.process_image(self.image)

    def depth_for_distance(self, distance):
        # 환산식의 역산으로 표시 반올림 전의 거리 경계를 입력한다.
        return np.full(self.image.shape[:2], self.pipeline.scale_k / distance - 1e-4)

    def test_mask_samples_polygon_interior_instead_of_bbox_background(self):
        polygon = np.array([[10, 10], [28, 10], [10, 28]], dtype=np.float32)
        self.set_result([box([10, 10, 50, 40])], [polygon])
        mask = np.zeros(self.image.shape[:2], dtype=np.uint8)
        cv2.fillPoly(mask, [polygon.astype(np.int32)], 1)
        depth = np.full(self.image.shape[:2], 100.0)
        depth[mask == 1] = 500.0
        objects = self.detect(depth)
        self.assertAlmostEqual(objects[0].distance_m, 2.0, places=5)
        self.assertEqual(len(objects[0].contour), 3)

    def test_each_object_uses_its_own_mask(self):
        polygons = [np.array([[2, 2], [10, 2], [10, 10], [2, 10]]),
                    np.array([[40, 30], [50, 30], [50, 40], [40, 40]])]
        self.set_result([box([2, 2, 10, 10]), box([40, 30, 50, 40])], polygons)
        depth = np.full(self.image.shape[:2], 100.0)
        for polygon, value in zip(polygons, (500.0, 250.0)):
            mask = np.zeros(self.image.shape[:2], dtype=np.uint8)
            cv2.fillPoly(mask, [polygon.astype(np.int32)], 1)
            depth[mask == 1] = value
        np.testing.assert_allclose([obj.distance_m for obj in self.detect(depth)], [2.0, 4.0], atol=1e-5)

    def test_missing_mask_for_later_object_uses_its_bbox(self):
        polygon = np.array([[2, 2], [10, 2], [10, 10]])
        self.set_result([box([2, 2, 10, 10]), box([40, 30, 50, 40])], [polygon])
        objects = self.detect(np.full(self.image.shape[:2], 500.0))
        self.assertIsNotNone(objects[0].contour)
        self.assertIsNone(objects[1].contour)
        np.testing.assert_allclose([obj.distance_m for obj in objects], [2.0, 2.0], atol=1e-5)

    def test_too_short_mask_falls_back_to_bbox(self):
        for polygon in ([], [[20, 20]], [[20, 20], [30, 20]]):
            with self.subTest(points=len(polygon)):
                self.set_result([box([20, 20, 40, 40])], [np.array(polygon)])
                obj = self.detect(np.full(self.image.shape[:2], 500.0))[0]
                self.assertAlmostEqual(obj.distance_m, 2.0, places=5)
                self.assertIsNone(obj.contour)

    def test_outside_polygon_with_no_image_pixels_falls_back_to_bbox_center(self):
        polygon = np.array([[-30, -30], [-20, -30], [-20, -20]])
        self.set_result([box([20, 20, 40, 40])], [polygon])
        depth = np.full(self.image.shape[:2], 100.0)
        depth[30, 30] = 500.0
        self.assertAlmostEqual(self.detect(depth)[0].distance_m, 2.0, places=5)

    def test_partial_outside_polygon_samples_only_pixels_inside_image(self):
        polygon = np.array([[-10, -10], [10, -10], [10, 10], [-10, 10]])
        self.set_result([box([-10, -10, 10, 10])], [polygon])
        depth = np.full(self.image.shape[:2], 100.0)
        depth[:11, :11] = 500.0
        obj = self.detect(depth)[0]
        self.assertEqual(obj.bbox, [0, 0, 10, 10])
        self.assertAlmostEqual(obj.distance_m, 2.0, places=5)

    def test_bbox_coordinates_are_clipped_without_losing_detection(self):
        cases = [([-10, -20, 100, 100], [0, 0, 63, 47]),
                 ([-20, 10, -2, 20], [0, 10, 0, 20]),
                 ([80, 60, 100, 90], [63, 47, 63, 47]),
                 ([0, 0, 64, 48], [0, 0, 63, 47])]
        for bbox, expected in cases:
            with self.subTest(bbox=bbox):
                self.set_result([box(bbox)])
                obj = self.detect(np.full(self.image.shape[:2], 500.0))[0]
                self.assertEqual(obj.bbox, expected)
                self.assertAlmostEqual(obj.distance_m, 2.0, places=5)

    def test_single_pixel_image_and_degenerate_bbox_keep_valid_depth(self):
        self.image = np.zeros((1, 1, 3), dtype=np.uint8)
        self.set_result([box([0, 0, 1, 1])])
        obj = self.detect(np.array([[500.0]]))[0]
        self.assertEqual(obj.bbox, [0, 0, 0, 0])
        self.assertAlmostEqual(obj.distance_m, 2.0, places=5)

    def test_mixed_valid_unknown_objects_keep_ids_classes_and_distances(self):
        self.set_result([box([4, 4, 12, 12], track_id=[81]),
                         box([28, 20, 36, 28], class_id=1, track_id=[91]),
                         box([48, 32, 56, 40], track_id=[101])])
        depth = np.full(self.image.shape[:2], 500.0)
        depth[20:28, 28:36] = np.nan
        depth[32:40, 48:56] = 250.0
        objects = self.detect(depth)
        self.assertEqual([obj.id for obj in objects], [81, 91, 101])
        self.assertEqual([obj.class_name for obj in objects], ["tactile_dot", "person", "tactile_dot"])
        self.assertIsNone(objects[1].distance_m)
        np.testing.assert_allclose([objects[0].distance_m, objects[2].distance_m], [2.0, 4.0], atol=1e-5)
        # 거리 미상은 JSON null로 보내고 비유한 숫자는 내보내지 않는다.
        encoded = json.dumps([obj.to_dict() for obj in objects], allow_nan=False)
        serialized = json.loads(encoded)
        self.assertIsNone(serialized[1]["distance_m"])
        np.testing.assert_allclose([serialized[0]["distance_m"], serialized[2]["distance_m"]], [2.0, 4.0], atol=1e-5)

    def test_nonfinite_pixel_in_one_roi_does_not_contaminate_other_objects(self):
        self.set_result([box([4, 4, 12, 12]), box([40, 30, 48, 38])])
        depth = np.full(self.image.shape[:2], 500.0)
        depth[8, 8] = np.nan
        objects = self.detect(depth)
        self.assertIsNone(objects[0].distance_m)
        self.assertAlmostEqual(objects[1].distance_m, 2.0, places=5)

    def test_distance_conversion_lower_limit(self):
        for raw_m in (0.01, 0.1, 0.299, 0.3):
            with self.subTest(raw_m=raw_m):
                self.assertEqual(self.detect(self.depth_for_distance(raw_m))[0].distance_m, 0.3)

    def test_distance_conversion_upper_limit(self):
        for raw_m in (15.0, 15.1, 100.0, 10000.0):
            with self.subTest(raw_m=raw_m):
                self.assertAlmostEqual(self.detect(self.depth_for_distance(raw_m))[0].distance_m, 15.0, places=5)

    def test_distance_conversion_across_usable_range(self):
        for raw_m in (0.31, 0.75, 1.25, 2.01, 4.99, 5.0, 5.01, 9.5, 14.99):
            with self.subTest(raw_m=raw_m):
                self.assertAlmostEqual(self.detect(self.depth_for_distance(raw_m))[0].distance_m, raw_m, places=5)

    def test_nonpositive_or_nonfinite_scale_cannot_create_valid_distance(self):
        for scale in (0.0, -1000.0, float("nan"), float("inf"), float("-inf")):
            with self.subTest(scale=scale):
                self.pipeline.scale_k = scale
                self.assertIsNone(self.detect(np.full(self.image.shape[:2], 500.0))[0].distance_m)

    def test_valid_onnx_output_restores_original_image_shape(self):
        for h, w in ((48, 64), (72, 128), (64, 48), (1, 1)):
            with self.subTest(shape=(h, w)):
                self.pipeline.depth_sess = Mock()
                self.pipeline.depth_sess.run.return_value = [np.full((1, 8, 8), 500.0, dtype=np.float32)]
                image = np.zeros((h, w, 3), dtype=np.uint8)
                depth = self.pipeline._estimate_depth_map(image)
                self.assertEqual(depth.shape, (h, w))
                self.assertEqual(depth.dtype, np.float32)
                np.testing.assert_array_equal(depth, np.full((h, w), 500.0))

    def test_onnx_input_is_rgb_float32_nchw_with_imagenet_normalization(self):
        self.image[:] = [0, 128, 255]
        original = self.image.copy()
        self.pipeline.depth_sess = Mock()
        self.pipeline.depth_sess.run.return_value = [np.full((1, 8, 8), 500.0, dtype=np.float32)]
        obj = self.pipeline.process_image(self.image)[0]
        args = self.pipeline.depth_sess.run.call_args.args
        self.assertIsNone(args[0])
        tensor = args[1]["input"]
        self.assertEqual(tensor.shape, (1, 3, 256, 256))
        self.assertEqual(tensor.dtype, np.float32)
        rgb = np.array([1.0, 128 / 255, 0.0], dtype=np.float32)
        expected = (rgb - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
        np.testing.assert_allclose(tensor[0, :, 100, 100], expected, rtol=1e-6)
        np.testing.assert_array_equal(self.image, original)
        self.assertAlmostEqual(obj.distance_m, 2.0, places=5)

    def test_onnx_depth_resize_preserves_spatial_orientation(self):
        self.pipeline.depth_sess = Mock()
        self.pipeline.depth_sess.run.return_value = [np.array([[[100, 200], [300, 400]]], dtype=np.float32)]
        depth = self.pipeline._estimate_depth_map(self.image)
        self.assertEqual([depth[0, 0], depth[0, -1], depth[-1, 0], depth[-1, -1]],
                         [100, 200, 300, 400])

    def test_empty_onnx_output_is_unknown_without_discarding_yolo_detection(self):
        self.pipeline.depth_sess = Mock()
        self.pipeline.depth_sess.run.return_value = []
        with contextlib.redirect_stderr(io.StringIO()):
            objects = self.pipeline.process_image(self.image)
        self.assertEqual(len(objects), 1)
        self.assertIsNone(objects[0].distance_m)

    def test_onnx_invalid_depth_map_does_not_serialize_nan_or_infinity(self):
        for value in (float("nan"), float("inf"), -5.0, 0.0):
            with self.subTest(value=value):
                self.pipeline.depth_sess = Mock()
                self.pipeline.depth_sess.run.return_value = [np.full((1, 8, 8), value, dtype=np.float32)]
                obj = self.pipeline.process_image(self.image)[0]
                self.assertIsNone(json.loads(json.dumps(obj.to_dict(), allow_nan=False))["distance_m"])

    def test_depth_session_recovers_on_frame_after_inference_error(self):
        self.pipeline.depth_sess = Mock()
        self.pipeline.depth_sess.run.side_effect = [RuntimeError("temporary failure"),
                                                  [np.full((1, 8, 8), 500.0, dtype=np.float32)]]
        with contextlib.redirect_stderr(io.StringIO()):
            first = self.pipeline.process_frame(1, self.image)
        second = self.pipeline.process_frame(2, self.image)
        self.assertIsNone(first["objects"][0].distance_m)
        self.assertAlmostEqual(second["objects"][0].distance_m, 2.0, places=5)
        self.assertEqual([first["frame_id"], second["frame_id"]], [1, 2])

    def test_empty_yolo_output_preserves_frame_without_fabricated_objects(self):
        for boxes in (None, []):
            with self.subTest(boxes=boxes):
                self.set_result(boxes)
                self.assertEqual(self.pipeline.process_frame(19, self.image),
                                 {"frame_id": 19, "objects": [], "situations": [], "image_width": 64, "image_height": 48})

    def test_tracking_path_preserves_distance_and_tracker_id(self):
        self.pipeline.enable_tracking = True
        self.result.boxes[0].id = [56]
        self.pipeline.yolo.track.return_value = [self.result]
        obj = self.detect(np.full(self.image.shape[:2], 500.0))[0]
        self.assertEqual(obj.id, 56)
        self.assertAlmostEqual(obj.distance_m, 2.0, places=5)
        self.pipeline.yolo.assert_not_called()
        self.assertEqual(self.pipeline.yolo.track.call_args.kwargs,
                         {"conf": 0.25, "persist": True, "tracker": "bytetrack.yaml",
                          "verbose": False, "device": "cpu"})

    def test_process_frame_preserves_explicit_disabled_analysis_and_unknown_distance(self):
        frame = self.pipeline.process_frame(42, self.image, situations=[])
        self.assertEqual(frame["frame_id"], 42)
        self.assertEqual(frame["situations"], [])
        self.assertIsNone(frame["objects"][0].distance_m)
        self.assertEqual(frame_interface.analyze(frame), [])

    def test_sampling_does_not_mutate_depth_or_model_outputs(self):
        polygon = np.array([[10, 10], [30, 10], [30, 30], [10, 30]])
        self.set_result([box([10, 10, 30, 30])], [polygon])
        depth = np.full(self.image.shape[:2], 500.0)
        original_depth = depth.copy()
        original_bbox = self.result.boxes[0].xyxy.copy()
        original_polygon = polygon.copy()
        self.detect(depth)
        np.testing.assert_array_equal(depth, original_depth)
        np.testing.assert_array_equal(self.result.boxes[0].xyxy, original_bbox)
        np.testing.assert_array_equal(polygon, original_polygon)

    def test_exact_five_meters_remains_eligible_after_pipeline(self):
        self.image = np.zeros((480, 640, 3), dtype=np.uint8)
        self.set_result([box([280, 200, 360, 240])])
        with patch.object(self.pipeline, "_estimate_depth_map", return_value=self.depth_for_distance(5.0)):
            frame = self.pipeline.process_frame(1, self.image)
        self.assertEqual(len(frame_interface.analyze(frame)), 1)

    def test_distance_above_five_meters_must_not_enter_context_after_rounding(self):
        # 확정된 5m 제한은 표시 반올림 전에도 적용해야 하므로 5.004m는 대상 밖이다.
        self.image = np.zeros((480, 640, 3), dtype=np.uint8)
        self.set_result([box([280, 200, 360, 240])])
        with patch.object(self.pipeline, "_estimate_depth_map", return_value=self.depth_for_distance(5.004)):
            frame = self.pipeline.process_frame(1, self.image)
        self.assertEqual(frame_interface.analyze(frame), [])


if __name__ == "__main__":
    unittest.main()
