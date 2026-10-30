"""연속 프레임·점형 병합·분기선·시설물의 가상 탐지 시나리오."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "main" / "python"))
from detection import Detection
import tactile_context


class TactileContextScenarioTest(unittest.TestCase):
    def setUp(self):
        tactile_context.reset_state()

    def tearDown(self):
        tactile_context.reset_state()

    def detection(self, object_id, name, bbox, distance=2.0):
        return Detection(object_id, name, 0.9, distance, bbox)

    def dot(self, object_id=1, bbox=None, distance=2.0):
        return self.detection(object_id, "tactile_dot", bbox or [290, 280, 350, 340], distance)

    def analyze(self, *objects, now=100.0):
        return tactile_context.analyze({"objects": list(objects), "timestamp": now})

    def incoming(self):
        return self.detection(20, "tactile_line", [300, 340, 340, 480], 0.5)

    def test_suppressed_frames_do_not_extend_cooldown(self):
        dot = self.dot()
        self.assertEqual(len(self.analyze(dot)), 1)
        for now in (100.2, 101.0, 102.999):
            self.assertEqual(self.analyze(dot, now=now), [])
        self.assertEqual(len(self.analyze(dot, now=103.001)), 1)

    def test_empty_frame_does_not_reset_duplicate_history(self):
        dot = self.dot()
        self.analyze(dot)
        self.assertEqual(self.analyze(now=101.0), [])
        self.assertEqual(self.analyze(dot, now=102.0), [])
        self.assertEqual(len(self.analyze(dot, now=103.1)), 1)

    def test_missing_distance_frame_does_not_erase_previous_announcement(self):
        self.analyze(self.dot())
        self.assertEqual(self.analyze(self.dot(distance=None), now=101.0), [])
        self.assertEqual(self.analyze(self.dot(distance=1.5), now=102.0), [])
        self.assertEqual(len(self.analyze(self.dot(distance=1.0), now=103.1)), 1)

    def test_same_tracked_dot_approaching_remains_suppressed(self):
        self.analyze(self.dot(distance=1.8))
        result = self.analyze(self.dot(bbox=[280, 380, 360, 460], distance=1.0), now=101.0)
        self.assertEqual(result, [])

    def test_adding_neighbor_to_announced_cluster_does_not_repeat(self):
        original = self.dot(1, [290, 250, 320, 280], 1.8)
        self.analyze(original)
        neighbor = self.dot(2, [320, 250, 350, 280], 1.5)
        self.assertEqual(self.analyze(original, neighbor, now=101.0), [])
        result = self.analyze(original, neighbor, now=103.1)
        self.assertEqual(result[0]["object_id"], 2)

    def test_beyond_five_meter_frame_does_not_delay_first_valid_announcement(self):
        self.assertEqual(self.analyze(self.dot(distance=2.5)), [])
        result = self.analyze(self.dot(distance=2.0), now=100.2)
        self.assertEqual(len(result), 1)
        self.assertIn("2.0m", result[0]["message"])

    def test_side_dot_entering_middle_third_is_announced(self):
        self.assertEqual(self.analyze(self.dot(bbox=[150, 280, 190, 320])), [])
        result = self.analyze(self.dot(bbox=[220, 280, 260, 320]), now=100.2)
        self.assertEqual(result[0]["object_id"], 1)

    def test_current_behavior_new_closer_dot_is_also_suppressed(self):
        # 정책 미확정: 이전 점형이 남아 있어도 새 구역이 같은 범주면 억제되는 현상을 기록한다.
        old = self.dot(1, [290, 40, 350, 80], 1.8)
        new = self.dot(2, [290, 390, 350, 430], 1.0)
        self.assertEqual(self.analyze(old)[0]["object_id"], 1)
        self.assertEqual(self.analyze(old, new, now=101.0), [])
        self.assertEqual(self.analyze(old, new, now=103.1)[0]["object_id"], 2)

    def test_nine_touching_tiles_form_one_region_in_either_input_order(self):
        dots = [self.dot(1 + row * 3 + col,
                         [270 + col * 30, 180 + row * 30,
                          300 + col * 30, 210 + row * 30],
                         4.0 - (row * 3 + col) * 0.25)
                for row in range(3) for col in range(3)]
        for objects in (dots, list(reversed(dots))):
            with self.subTest(ids=[dot.id for dot in objects]):
                tactile_context.reset_state()
                result = self.analyze(*objects)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["object_id"], 9)
                self.assertIn("2.0m", result[0]["message"])

    def test_invalid_bridge_cannot_merge_side_region_into_middle_region(self):
        side = self.dot(1, [180, 200, 200, 220], 0.5)
        middle = self.dot(2, [240, 200, 260, 220], 2.0)
        for distance in (None, -1.0, float("inf"), float("nan")):
            with self.subTest(distance=distance):
                tactile_context.reset_state()
                bridge = self.dot(3, [210, 200, 230, 220], distance)
                result = self.analyze(side, bridge, middle)
                self.assertEqual(result[0]["object_id"], 2)

    def test_separate_regions_keep_their_own_distances(self):
        upper = self.dot(1, [290, 40, 350, 80], 4.0)
        lower = self.dot(2, [290, 390, 350, 430], 1.0)
        result = self.analyze(upper, lower)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["object_id"], 2)
        self.assertIn("1.0m", result[0]["message"])

    def test_stairs_announcement_uses_facility_id_and_dot_distance(self):
        stairs = self.detection(80, "stairs", [280, 150, 360, 280], 3.0)
        result = self.analyze(self.dot(distance=2.0), stairs)
        self.assertEqual(result[0]["object_id"], 80)
        self.assertEqual(result[0]["priority"], "INFO")
        self.assertIn("계단", result[0]["message"])
        self.assertIn("2.0m", result[0]["message"])

    def test_elevator_sign_is_described_as_a_sign(self):
        sign = self.detection(81, "elevator_sign", [300, 100, 340, 160])
        result = self.analyze(self.dot(), sign)
        self.assertEqual(result[0]["object_id"], 81)
        self.assertIn("표지", result[0]["message"])

    def test_toilet_sign_does_not_claim_confirmed_toilet_destination(self):
        # 핸드오프 계약: 표지만 탐지됐다면 시설 자체가 확인된 것처럼 표현하지 않는다.
        sign = self.detection(82, "toilet_sign", [300, 100, 340, 160])
        result = self.analyze(self.dot(), sign)
        for item in result:
            message = item["message"]
            self.assertNotIn("화장실 도착점", message)
            if "화장실" in message:
                self.assertIn("표지", message)

    def test_traffic_light_does_not_assert_signal_color_or_permission_to_cross(self):
        light = self.detection(83, "traffic_light", [300, 60, 340, 120])
        message = self.analyze(self.dot(), light)[0]["message"]
        self.assertIn("신호등", message)
        for unsupported in ("녹색", "초록", "건너도", "횡단 가능"):
            self.assertNotIn(unsupported, message)

    def test_laterally_separated_facility_is_not_associated(self):
        facility = self.detection(84, "crosswalk", [20, 100, 80, 160])
        result = self.analyze(self.dot(), facility)
        self.assertEqual(result[0]["object_id"], 1)
        self.assertNotIn("횡단보도", result[0]["message"])

    def test_facility_behind_dot_in_image_is_not_associated(self):
        facility = self.detection(85, "stairs", [290, 420, 350, 470])
        result = self.analyze(self.dot(), facility)
        self.assertEqual(result[0]["object_id"], 1)
        self.assertNotIn("계단", result[0]["message"])

    def test_single_left_branch_without_incoming_line_is_still_a_left_turn(self):
        # 타겟 왼쪽으로만 뻗는 선을 진입선으로 간주해 버리면 분기를 놓친다.
        left = self.detection(21, "tactile_line", [160, 290, 290, 330])
        result = self.analyze(self.dot(), left)
        self.assertIn("좌회전", result[0]["message"])

    def test_single_right_branch_without_incoming_line_is_still_a_right_turn(self):
        right = self.detection(22, "tactile_line", [350, 290, 480, 330])
        result = self.analyze(self.dot(), right)
        self.assertIn("우회전", result[0]["message"])

    def test_two_side_branches_without_incoming_line_make_junction(self):
        left = self.detection(21, "tactile_line", [160, 290, 290, 330])
        right = self.detection(22, "tactile_line", [350, 290, 480, 330])
        result = self.analyze(self.dot(), left, right)
        self.assertIn("갈림길", result[0]["message"])

    def test_forward_line_is_not_mistaken_for_incoming_line(self):
        forward = self.detection(21, "tactile_line", [300, 150, 340, 280])
        result = self.analyze(self.dot(), forward)
        self.assertNotIn("경로 종료", result[0]["message"])

    def test_far_unconnected_line_does_not_imply_route_end(self):
        unrelated = self.detection(23, "tactile_line", [20, 20, 60, 80])
        message = self.analyze(self.dot(), unrelated)[0]["message"]
        self.assertIn("점형블록", message)
        self.assertNotIn("경로 종료", message)

    def test_incoming_line_and_no_outgoing_branches_produces_stop(self):
        message = self.analyze(self.dot(), self.incoming())[0]["message"]
        self.assertIn("정지선", message)
        self.assertNotIn("갈림길", message)

    def test_multiple_segments_in_same_direction_do_not_make_a_junction(self):
        left_a = self.detection(24, "tactile_line", [140, 280, 240, 320])
        left_b = self.detection(25, "tactile_line", [200, 280, 290, 320])
        result = self.analyze(self.dot(), self.incoming(), left_a, left_b)
        self.assertEqual(len(result), 1)
        self.assertIn("좌회전", result[0]["message"])
        self.assertNotIn("갈림길", result[0]["message"])

    def test_left_and_straight_branches_make_a_junction(self):
        left = self.detection(26, "tactile_line", [160, 290, 290, 330])
        straight = self.detection(27, "tactile_line", [300, 150, 340, 280])
        result = self.analyze(self.dot(), self.incoming(), left, straight)
        self.assertEqual(len(result), 1)
        self.assertIn("갈림길", result[0]["message"])
        self.assertEqual(result[0]["priority"], "CAUTION")

    def test_unconnected_line_is_not_added_as_a_junction_branch(self):
        unrelated = self.detection(28, "tactile_line", [20, 50, 80, 100])
        message = self.analyze(self.dot(), self.incoming(), unrelated)[0]["message"]
        self.assertIn("정지선", message)
        self.assertNotIn("갈림길", message)


if __name__ == "__main__":
    unittest.main()
