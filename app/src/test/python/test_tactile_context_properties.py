"""입력 순서·좌표·거리 오류를 바꿔도 유지돼야 하는 선택 규칙."""
import copy
import math
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "main" / "python"))
from detection import Detection
import tactile_context


class TactileContextPropertiesTest(unittest.TestCase):
    def dot(self, object_id, x, y, distance, confidence=0.9):
        return Detection(object_id, "tactile_dot", confidence, distance,
                         [x - 2, y - 2, x + 2, y + 2])

    def analyze(self, objects, width=640):
        # 각 장면은 독립 세션이다. 연속 프레임 테스트는 별도 파일에서 다룬다.
        tactile_context.reset_state()
        return tactile_context.analyze({"objects": objects}, frame_width=width)

    def test_randomized_selection_1000_frames_with_invalid_distances(self):
        rng = random.Random(2026102401)
        for case in range(1000):
            width = rng.choice((320, 480, 640, 900, 1280, 1920))
            # 세로 간격을 벌려 서로 다른 점형 구역임을 보장한다.
            dots = [self.dot(i + 1, rng.randint(4, width - 4), 20 + i * 44,
                             rng.choice((None, -1.0, math.nan, math.inf,
                                         round(rng.uniform(0.1, 6.0), 4))))
                    for i in range(10)]
            eligible = [d for d in dots if d.distance_m is not None
                        and math.isfinite(d.distance_m) and 0 <= d.distance_m <= tactile_context.MAX_VALID_DISTANCE_M
                        and width / 3 <= d.bbox[0] + 2 <= width * 2 / 3]
            # 동률의 우선순위는 미정이므로 최소 거리의 후보 집합과 비교한다.
            nearest = min((d.distance_m for d in eligible), default=None)
            expected_ids = {d.id for d in eligible if d.distance_m == nearest}
            rng.shuffle(dots)
            with self.subTest(case=case, width=width):
                result = self.analyze(dots, width)
                self.assertEqual(len(result), int(bool(expected_ids)))
                if result:
                    self.assertIn(result[0]["object_id"], expected_ids)

    def test_reflecting_scene_horizontally_preserves_target(self):
        rng = random.Random(2026102402)
        for case in range(100):
            dots = [self.dot(i, rng.randint(10, 630), 20 + i * 80, i + 0.5)
                    for i in range(6)]
            reflected = copy.deepcopy(dots)
            for dot in reflected:
                x1, y1, x2, y2 = dot.bbox
                dot.bbox = [640 - x2, y1, 640 - x1, y2]
            with self.subTest(case=case):
                self.assertEqual(self.analyze(dots), self.analyze(reflected))

    def test_changing_horizontal_resolution_preserves_target(self):
        dots = [self.dot(1, 100, 50, 0.5), self.dot(2, 240, 200, 2.0),
                self.dot(3, 400, 350, 4.0)]
        baseline = self.analyze(dots)
        for width in (320, 480, 900, 1280, 1920):
            resized = copy.deepcopy(dots)
            for dot in resized:
                dot.bbox[0] *= width / 640
                dot.bbox[2] *= width / 640
            with self.subTest(width=width):
                self.assertEqual(self.analyze(resized, width), baseline)

    def test_moving_scene_vertically_preserves_target(self):
        dots = [self.dot(1, 260, 80, 3.0), self.dot(2, 380, 220, 1.0)]
        baseline = self.analyze(dots)
        for offset in (0, 40, 120, 200):
            shifted = copy.deepcopy(dots)
            for dot in shifted:
                dot.bbox[1] += offset
                dot.bbox[3] += offset
            with self.subTest(offset=offset):
                self.assertEqual(self.analyze(shifted), baseline)

    def test_invalid_detection_bridge_cannot_merge_separate_targets(self):
        # 거리 미상 블록을 사이에 넣어도 떨어진 두 구역이 합쳐지면 안 된다.
        valid = [self.dot(1, 240, 150, 3.0), self.dot(2, 400, 150, 2.0)]
        baseline = self.analyze(valid)
        for distance in (None, -0.1, math.nan, math.inf, -math.inf):
            bridge = [self.dot(10 + i, x, 150, distance)
                      for i, x in enumerate((270, 300, 330, 360, 390))]
            with self.subTest(distance=distance):
                self.assertEqual(self.analyze(valid + bridge), baseline)

    def test_higher_confidence_does_not_replace_closer_separate_target(self):
        dots = [self.dot(1, 260, 100, 1.0, 0.3),
                self.dot(2, 380, 300, 4.0, 0.99)]
        self.assertEqual(self.analyze(dots)[0]["object_id"], 1)

    def test_nearest_candidate_is_reselected_when_distances_change(self):
        dots = [self.dot(1, 260, 100, 1.0), self.dot(2, 380, 300, 4.0)]
        self.assertEqual(self.analyze(dots)[0]["object_id"], 1)
        dots[0].distance_m = 4.0
        dots[1].distance_m = 1.0
        self.assertEqual(self.analyze(dots)[0]["object_id"], 2)

    def test_multiple_clusters_are_selected_independently_of_input_order(self):
        dots = [self.dot(1, 260, 80, 4.0), self.dot(2, 280, 80, 3.5),
                self.dot(3, 360, 300, 2.0), self.dot(4, 380, 300, 1.5)]
        rng = random.Random(2026102403)
        for case in range(40):
            rng.shuffle(dots)
            with self.subTest(case=case):
                result = self.analyze(dots)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["object_id"], 4)

    def test_distance_just_above_five_is_excluded_before_message_rounding(self):
        for distance in (5.000001, 5.001, 5.004, 5.049):
            with self.subTest(distance=distance):
                self.assertEqual(self.analyze([self.dot(1, 320, 200, distance)]), [])


if __name__ == "__main__":
    unittest.main()
