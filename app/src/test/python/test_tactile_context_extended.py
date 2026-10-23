"""가운데 1/3·5m 선택 조건과 연속 프레임의 추가 검증."""
import copy
import itertools
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "main" / "python"))
from detection import Detection
import frame_interface
import tactile_context


class TactileContextExtendedTest(unittest.TestCase):
    def setUp(self):
        tactile_context.reset_state()

    def dot(self, object_id=1, x=320, y=200, distance=2.0):
        return Detection(object_id, "tactile_dot", 0.9, distance,
                         [x - 10, y - 10, x + 10, y + 10])

    def test_selection_matrix_504_scenarios(self):
        # 해상도 4종 × 가로 위치 7종 × 거리 6종 × 세로 위치 3종.
        for width in (360, 640, 900, 1280):
            for ratio in (0.1, 1 / 3 - 0.001, 1 / 3, 0.5, 2 / 3, 2 / 3 + 0.001, 0.9):
                for distance in (-0.1, 0.1, 2.5, 4.999, 5.0, 5.001):
                    for y in (20, 200, 460):
                        with self.subTest(width=width, ratio=ratio, distance=distance, y=y):
                            tactile_context.reset_state()
                            x = width * ratio
                            dot = self.dot(x=x, y=y, distance=distance)
                            expected = width / 3 <= x <= width * 2 / 3 and 0 <= distance <= 5
                            result = tactile_context.analyze({"objects": [dot]}, frame_width=width)
                            self.assertEqual(bool(result), expected)

    def test_nearest_target_in_200_generated_frames(self):
        rng = random.Random(20261024)
        for case in range(200):
            with self.subTest(case=case):
                tactile_context.reset_state()
                width = rng.choice((360, 640, 900, 1280))
                # 서로 떨어진 점형으로 병합 영향 없이 선택 규칙을 확인한다.
                dots = [self.dot(i + 1, rng.randint(20, width - 20), 30 + i * 80,
                                 round(rng.uniform(0.1, 6.5), 2)) for i in range(5)]
                eligible = [dot for dot in dots
                            if width / 3 <= sum(dot.bbox[::2]) / 2 <= width * 2 / 3
                            and dot.distance_m <= 5]
                expected_id = min(eligible, key=lambda dot: dot.distance_m).id if eligible else None
                rng.shuffle(dots)
                result = tactile_context.analyze({"objects": dots}, frame_width=width)
                self.assertEqual(len(result), int(expected_id is not None))
                if result:
                    self.assertEqual(result[0]["object_id"], expected_id)

    def test_input_permutations_keep_nearest_target(self):
        dots = [self.dot(1, 240, 80, 4.0), self.dot(2, 400, 250, 1.0),
                self.dot(3, 50, 400, 0.5)]
        for objects in itertools.permutations(dots):
            with self.subTest(ids=[dot.id for dot in objects]):
                tactile_context.reset_state()
                result = tactile_context.analyze({"objects": list(objects)})
                self.assertEqual(result[0]["object_id"], 2)

    def test_no_middle_candidate_does_not_fall_back_to_sides(self):
        result = tactile_context.analyze({"objects": [self.dot(1, 60), self.dot(2, 580)]})
        self.assertEqual(result, [])

    def test_middle_candidate_beyond_five_meters_does_not_enable_side_target(self):
        result = tactile_context.analyze({"objects": [self.dot(distance=5.1), self.dot(2, 60, distance=0.5)]})
        self.assertEqual(result, [])

    def test_bbox_overlap_alone_does_not_make_center_eligible(self):
        # 가운데 영역과 일부 겹쳐도 중심점이 바깥이면 제외한다.
        dot = self.dot(x=200)
        dot.bbox = [160, 100, 240, 140]
        self.assertEqual(tactile_context.analyze({"objects": [dot]}), [])

    def test_clustering_indirect_neighbors_is_order_independent(self):
        dots = [self.dot(1, 280, distance=3.0), self.dot(2, 320, distance=2.0),
                self.dot(3, 360, distance=1.0)]
        for objects in itertools.permutations(dots):
            with self.subTest(ids=[dot.id for dot in objects]):
                tactile_context.reset_state()
                result = tactile_context.analyze({"objects": list(objects)})
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["object_id"], 3)

    def test_duplicate_detection_does_not_duplicate_result(self):
        dot = self.dot()
        result = tactile_context.analyze({"objects": [dot, dot]})
        self.assertEqual(len(result), 1)

    def test_input_objects_are_not_modified(self):
        frame = {"frame_id": 5, "objects": [self.dot(), self.dot(2, 60)],
                 "situations": ["TACTILE_CONTEXT"], "timestamp": 100.0}
        before = copy.deepcopy(frame)
        tactile_context.analyze(frame)
        self.assertEqual(frame, before)

    def test_repeated_frame_is_suppressed(self):
        dot = self.dot()
        self.assertEqual(len(tactile_context.analyze({"objects": [dot], "timestamp": 100.0})), 1)
        self.assertEqual(tactile_context.analyze({"objects": [dot], "timestamp": 101.0}), [])

    def test_cooldown_expiration_allows_announcement(self):
        dot = self.dot()
        tactile_context.analyze({"objects": [dot], "timestamp": 100.0})
        result = tactile_context.analyze({"objects": [dot], "timestamp": 103.1})
        self.assertEqual(len(result), 1)

    def test_reset_allows_same_target_in_new_session(self):
        dot = self.dot()
        frame = {"objects": [dot], "timestamp": 100.0}
        tactile_context.analyze(frame)
        tactile_context.reset_state()
        self.assertEqual(len(tactile_context.analyze(frame)), 1)

    def test_outside_candidate_does_not_start_cooldown(self):
        self.assertEqual(tactile_context.analyze({"objects": [self.dot(x=50)], "timestamp": 100.0}), [])
        self.assertEqual(len(tactile_context.analyze({"objects": [self.dot()], "timestamp": 101.0})), 1)

    def test_infinite_and_nan_distance_are_excluded(self):
        for distance in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(distance=distance):
                tactile_context.reset_state()
                self.assertEqual(tactile_context.analyze({"objects": [self.dot(distance=distance)]}), [])

    def test_missing_distance_is_not_reported_as_measured_distance(self):
        # 5m 이내인지 확인할 수 없는 점형을 임의 거리로 안내하면 안 된다.
        self.assertEqual(tactile_context.analyze({"objects": [self.dot(distance=None)]}), [])

    def test_only_out_of_range_cluster_members_do_not_hide_valid_dot(self):
        # 음수 거리 검출이 붙어 있어도 유효한 2m 점형은 남아야 한다.
        valid = self.dot(1, 310, distance=2.0)
        invalid = self.dot(2, 330, distance=-1.0)
        result = tactile_context.analyze({"objects": [valid, invalid]})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["object_id"], 1)

    def test_invalid_neighbor_distances_do_not_hide_valid_dot(self):
        for distance in (None, -1.0, float("nan"), float("inf"), float("-inf")):
            for invalid_first in (False, True):
                with self.subTest(distance=distance, invalid_first=invalid_first):
                    tactile_context.reset_state()
                    valid = self.dot(1, 310, distance=2.0)
                    invalid = self.dot(2, 330, distance=distance)
                    objects = [invalid, valid] if invalid_first else [valid, invalid]
                    result = tactile_context.analyze({"objects": objects})
                    self.assertEqual(len(result), 1)
                    self.assertEqual(result[0]["object_id"], 1)
                    self.assertIn("2.0m", result[0]["message"])

    def test_interface_routes_real_context_result(self):
        dot = self.dot()
        frame = frame_interface.build_frame(10, objects=[dot])
        self.assertIn("TACTILE_CONTEXT", frame["situations"])
        result = frame_interface.analyze(frame)
        self.assertEqual(result[0]["object_id"], dot.id)
        self.assertEqual(result[0]["situation"], "TACTILE_CONTEXT")

    def test_explicit_empty_situations_prevents_context_announcement(self):
        frame = frame_interface.build_frame(10, objects=[self.dot()], situations=[])
        self.assertEqual(frame_interface.analyze(frame), [])

    def test_unknown_classes_do_not_replace_dot_target(self):
        irrelevant = Detection(99, "unrecognized", 0.99, 0.1, [300, 100, 340, 140])
        result = tactile_context.analyze({"objects": [irrelevant, self.dot()]})
        self.assertEqual(result[0]["object_id"], 1)

    def test_output_has_only_contract_keys_and_valid_input_id(self):
        dots = [self.dot(7), self.dot(8, 60)]
        result = tactile_context.analyze({"objects": dots})
        self.assertEqual(len(result), 1)
        self.assertEqual(set(result[0]), {"situation", "object_id", "message", "priority"})
        self.assertIn(result[0]["object_id"], {dot.id for dot in dots})
        self.assertIsInstance(result[0]["message"], str)
        self.assertTrue(result[0]["message"].strip())


if __name__ == "__main__":
    unittest.main()
