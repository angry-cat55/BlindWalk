import os
import sys
import unittest

# app/src/main/python 경로 추가
APP_PYTHON_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "main", "python")
)
if APP_PYTHON_DIR not in sys.path:
    sys.path.insert(0, APP_PYTHON_DIR)

from detection import Detection
import tactile_context


class TactileContextTest(unittest.TestCase):
    def setUp(self):
        """각 테스트 시작 전 상태 초기화"""
        tactile_context.reset_state()

    def test_empty_frame_returns_empty_list(self):
        """빈 프레임 데이터 입력 시 빈 리스트 반환 검증"""
        self.assertEqual(tactile_context.analyze({}), [])
        self.assertEqual(tactile_context.analyze({"objects": []}), [])

    def test_no_dot_blocks_returns_empty_list(self):
        """점형 블록(tactile_dot)이 없는 경우 빈 리스트 반환 검증"""
        line = Detection(id=1, class_name="tactile_line", confidence=0.9, distance_m=1.0, bbox=[280, 300, 360, 480])
        self.assertEqual(tactile_context.analyze({"objects": [line]}), [])

    def test_side_dot_returns_empty_list(self):
        """가운데 구역 밖의 점형블록은 대상에서 제외"""
        dot = Detection(id=1, class_name="tactile_dot", confidence=0.9, distance_m=2.0, bbox=[50, 50, 100, 100])
        self.assertEqual(tactile_context.analyze({"objects": [dot]}), [])

    def test_distance_filtering_5m(self):
        """유효거리 2.0m 기준: 2.0m 이하는 유효, 2.0m 초과는 무시 검증"""
        foot_line = Detection(id=1, class_name="tactile_line", confidence=0.95, distance_m=0.8, bbox=[280, 320, 360, 480])

        # 1.8m 거리의 점형 블록 (2.0m 이내 -> 유효)
        dot_within = Detection(id=2, class_name="tactile_dot", confidence=0.9, distance_m=1.8, bbox=[280, 270, 360, 325])
        res_within = tactile_context.analyze({"objects": [foot_line, dot_within]})
        self.assertEqual(len(res_within), 1)
        self.assertIn("정지선", res_within[0]["message"])
        self.assertIn("1.8m", res_within[0]["message"])

        # 2.5m 거리의 점형 블록 (2.0m 초과 -> 무시)
        dot_far = Detection(id=3, class_name="tactile_dot", confidence=0.9, distance_m=2.5, bbox=[280, 270, 360, 325])
        res_far = tactile_context.analyze({"objects": [foot_line, dot_far]})
        self.assertEqual(res_far, [])

    def test_touching_dot_blocks_clustered_into_single_block(self):
        """서로 붙어있는 여러 점형 블록들이 단일 구역(Cluster)으로 병합되어 중복 이벤트 없이 1건만 반환되는지 검증"""
        foot_line = Detection(id=1, class_name="tactile_line", confidence=0.95, distance_m=1.0, bbox=[280, 320, 360, 480])

        # 도로에 2x2로 맞닿아 설치된 점형 블록 4장
        dot1 = Detection(id=10, class_name="tactile_dot", confidence=0.92, distance_m=2.0, bbox=[280, 240, 320, 280])
        dot2 = Detection(id=11, class_name="tactile_dot", confidence=0.88, distance_m=1.9, bbox=[320, 240, 360, 280])  # dot1 오른쪽 접촉
        dot3 = Detection(id=12, class_name="tactile_dot", confidence=0.90, distance_m=2.1, bbox=[280, 280, 320, 320])  # dot1 아래 접촉
        dot4 = Detection(id=13, class_name="tactile_dot", confidence=0.85, distance_m=2.0, bbox=[320, 280, 360, 320])  # dot2 아래 접촉

        # 좌/우 분기선
        left_line = Detection(id=20, class_name="tactile_line", confidence=0.9, distance_m=2.2, bbox=[160, 260, 280, 300])
        right_line = Detection(id=21, class_name="tactile_line", confidence=0.9, distance_m=2.2, bbox=[360, 260, 480, 300])

        objects = [foot_line, dot1, dot2, dot3, dot4, left_line, right_line]
        results = tactile_context.analyze({"objects": objects})

        # 4개의 점형 블록이 각각 결과를 내지 않고 1개의 대표 갈림길 결과로 병합되어야 함
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["situation"], "TACTILE_CONTEXT")
        self.assertEqual(res["priority"], "CAUTION")
        self.assertIn("갈림길", res["message"])
        self.assertIn("1.9m", res["message"])  # 가장 가까운 블록(dot2)의 거리 반영

    def test_branching_directions(self):
        """좌/우 분기 및 단일 방향 전환(굴절점) 판정 검증"""
        foot_line = Detection(id=1, class_name="tactile_line", confidence=0.9, distance_m=1.0, bbox=[280, 320, 360, 480])
        dot = Detection(id=2, class_name="tactile_dot", confidence=0.9, distance_m=2.0, bbox=[280, 260, 360, 320])

        # 좌회전 유도선만 있는 경우
        left_line = Detection(id=3, class_name="tactile_line", confidence=0.9, distance_m=2.1, bbox=[180, 270, 280, 310])
        res_left = tactile_context.analyze({"objects": [foot_line, dot, left_line]})
        self.assertEqual(len(res_left), 1)
        self.assertIn("좌회전", res_left[0]["message"])

        # 우회전 유도선 테스트 (독립 시나리오를 위해 상태 리셋)
        tactile_context.reset_state()
        right_line = Detection(id=4, class_name="tactile_line", confidence=0.9, distance_m=2.1, bbox=[360, 270, 460, 310])
        res_right = tactile_context.analyze({"objects": [foot_line, dot, right_line]})
        self.assertEqual(len(res_right), 1)
        self.assertIn("우회전", res_right[0]["message"])

    def test_facility_destination_detection(self):
        """점형 블록과 시설물(횡단보도, 계단, 엘리베이터 등) 연계 도착점 판정 검증"""
        dot = Detection(id=1, class_name="tactile_dot", confidence=0.9, distance_m=1.5, bbox=[280, 280, 360, 340])
        crosswalk = Detection(id=101, class_name="crosswalk", confidence=0.88, distance_m=2.0, bbox=[200, 100, 440, 290])

        results = tactile_context.analyze({"objects": [dot, crosswalk]})
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["situation"], "TACTILE_CONTEXT")
        self.assertEqual(res["object_id"], 101)  # 시설물 ID 참조
        self.assertEqual(res["priority"], "INFO")
        self.assertIn("횡단보도 정지선", res["message"])

    def test_branching_combinations(self):
        """삼거리(직좌우), 직좌, 직우, 좌우 갈림길 문구 판정 검증"""
        foot_line = Detection(id=1, class_name="tactile_line", confidence=0.9, distance_m=1.0, bbox=[280, 320, 360, 480])
        dot = Detection(id=2, class_name="tactile_dot", confidence=0.9, distance_m=1.8, bbox=[280, 260, 360, 320])
        left = Detection(id=3, class_name="tactile_line", confidence=0.9, distance_m=1.8, bbox=[180, 270, 280, 310])
        right = Detection(id=4, class_name="tactile_line", confidence=0.9, distance_m=1.8, bbox=[360, 270, 460, 310])
        straight = Detection(id=5, class_name="tactile_line", confidence=0.9, distance_m=1.8, bbox=[280, 200, 360, 260])

        # 1. 직좌우 -> 삼거리 갈림길
        tactile_context.reset_state()
        res = tactile_context.analyze({"objects": [foot_line, dot, left, right, straight]})
        self.assertEqual(len(res), 1)
        self.assertIn("삼거리 갈림길", res[0]["message"])

        # 2. 직좌 -> 직진·좌측 갈림길
        tactile_context.reset_state()
        res = tactile_context.analyze({"objects": [foot_line, dot, left, straight]})
        self.assertEqual(len(res), 1)
        self.assertIn("직진·좌측 갈림길", res[0]["message"])

        # 3. 직우 -> 직진·우측 갈림길
        tactile_context.reset_state()
        res = tactile_context.analyze({"objects": [foot_line, dot, right, straight]})
        self.assertEqual(len(res), 1)
        self.assertIn("직진·우측 갈림길", res[0]["message"])

        # 4. 좌우 -> 좌우 갈림길
        tactile_context.reset_state()
        res = tactile_context.analyze({"objects": [foot_line, dot, left, right]})
        self.assertEqual(len(res), 1)
        self.assertIn("좌우 갈림길", res[0]["message"])

    def test_wide_cluster_offset_straight_branch(self):
        """가로로 넓은 점형 클러스터에서 직진 블록의 중심 x좌표가 편향(offset)되어도 직좌로 정확히 판정되는지 검증"""
        # 점형 클러스터 폭: 350px (중심: 355, 300)
        dot = Detection(id=1, class_name="tactile_dot", confidence=0.9, distance_m=1.8, bbox=[180, 280, 530, 320])
        foot_line = Detection(id=2, class_name="tactile_line", confidence=0.9, distance_m=1.0, bbox=[300, 320, 380, 480])

        # 직진 블록: x좌표가 좌측으로 60px 치우침 (중심: 295, 242.5 -> dx = -60px)
        offset_straight = Detection(id=3, class_name="tactile_line", confidence=0.85, distance_m=1.9, bbox=[260, 210, 330, 275])

        # 좌측 분기선: 점형 클러스터 좌측 바깥으로 뻗음
        left = Detection(id=4, class_name="tactile_line", confidence=0.9, distance_m=1.9, bbox=[80, 280, 180, 320])

        tactile_context.reset_state()
        res = tactile_context.analyze({"objects": [foot_line, dot, offset_straight, left]})
        self.assertEqual(len(res), 1)
        # 과거 알고리즘에서는 dx=-60으로 인해 직진이 좌회전으로 오분류되었으나, 기하학적 접촉 면 알고리즘에서는 직진·좌측으로 정상 판정
        self.assertIn("직진·좌측 갈림길", res[0]["message"])

    def test_result_schema_conformance(self):
        """반환 결과가 docs/situation-handoff.md 공통 4대 키를 엄격히 준수하는지 검증"""
        dot = Detection(id=5, class_name="tactile_dot", confidence=0.95, distance_m=1.8, bbox=[280, 280, 360, 340])
        stairs = Detection(id=50, class_name="stairs", confidence=0.9, distance_m=1.9, bbox=[250, 150, 390, 300])

        results = tactile_context.analyze({"objects": [dot, stairs]})
        self.assertEqual(len(results), 1)
        item = results[0]

        # 4대 필수 키 존재 및 타입 검증
        self.assertIn("situation", item)
        self.assertIn("object_id", item)
        self.assertIn("message", item)
        self.assertIn("priority", item)

        self.assertIsInstance(item["situation"], str)
        self.assertEqual(item["situation"], "TACTILE_CONTEXT")
        self.assertIsInstance(item["object_id"], int)
        self.assertIsInstance(item["message"], str)
        self.assertTrue(len(item["message"]) > 0)
        self.assertIn(item["priority"], ["INFO", "CAUTION", "URGENT"])

    def test_cluster_partial_disappearance_does_not_repeat_announcement(self):
        """
        보행 중 붙어있던 블록 중 하나가 화면 밖으로 사라져 단독 블록만 남았을 때도
        중복 발화가 방지(Suppress)되는지 검증
        """
        foot_line = Detection(id=1, class_name="tactile_line", confidence=0.9, distance_m=1.0, bbox=[280, 320, 360, 480])
        # 블록 A(id=10)와 블록 B(id=11) 연접
        dot_a = Detection(id=10, class_name="tactile_dot", confidence=0.9, distance_m=1.8, bbox=[280, 240, 320, 280])
        dot_b = Detection(id=11, class_name="tactile_dot", confidence=0.9, distance_m=1.7, bbox=[320, 240, 360, 280])
        left_line = Detection(id=20, class_name="tactile_line", confidence=0.9, distance_m=1.8, bbox=[160, 250, 280, 290])

        # 프레임 1 (t=100.0): 블록 A와 B가 모두 있어 클러스터 [A, B]로 1회 안내 발화
        frame1 = {
            "timestamp": 100.0,
            "objects": [foot_line, dot_a, dot_b, left_line]
        }
        res1 = tactile_context.analyze(frame1)
        self.assertEqual(len(res1), 1)
        self.assertIn("좌회전", res1[0]["message"])

        # 프레임 2 (t=101.0, 1초 뒤): 보행 전진으로 dot_a는 화면 밖으로 나가 소멸되고 dot_b만 남음
        frame2 = {
            "timestamp": 101.0,
            "objects": [foot_line, dot_b, left_line]
        }
        res2 = tactile_context.analyze(frame2)
        # dot_b는 방금 안내한 클러스터의 일원이므로 중복 발화 없이 빈 리스트([]) 반환되어야 함
        self.assertEqual(res2, [])

        # 프레임 3 (t=104.0, 4초 뒤 쿨다운 경과): 새로운 블록 C(id=30)가 나타났을 때는 정상 안내
        dot_c = Detection(id=30, class_name="tactile_dot", confidence=0.9, distance_m=1.9, bbox=[280, 240, 360, 280])
        frame3 = {
            "timestamp": 104.5,
            "objects": [foot_line, dot_c, left_line]
        }
        res3 = tactile_context.analyze(frame3)
        self.assertEqual(len(res3), 1)
        self.assertIn("좌회전", res3[0]["message"])

    def test_isolated_middle_dot_at_any_height(self):
        # 세로 위치나 선형블록 없이도 가운데 점형 자체를 안내한다.
        for y in (0, 220, 440):
            with self.subTest(y=y):
                tactile_context.reset_state()
                dot = Detection(1, "tactile_dot", 0.9, 1.8, [290, y, 350, y + 40])
                result = tactile_context.analyze({"objects": [dot]})
                self.assertEqual(result[0]["object_id"], 1)
                self.assertIn("점형블록", result[0]["message"])
                self.assertNotIn("경로 종료", result[0]["message"])

    def test_nearest_in_middle_third_wins_over_center_and_sides(self):
        center = Detection(1, "tactile_dot", 0.9, 1.9, [300, 40, 340, 80])
        nearer = Detection(2, "tactile_dot", 0.9, 1.2, [220, 200, 260, 240])
        left = Detection(3, "tactile_dot", 0.9, 0.5, [30, 350, 70, 390])
        right = Detection(4, "tactile_dot", 0.9, 0.4, [550, 350, 590, 390])
        result = tactile_context.analyze({"objects": [center, left, right, nearer]})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["object_id"], 2)

    def test_disconnected_dot_wins_over_farther_connected_dot(self):
        line = Detection(1, "tactile_line", 0.9, 1.0, [300, 300, 340, 480])
        connected = Detection(2, "tactile_dot", 0.9, 1.9, [290, 240, 350, 290])
        disconnected = Detection(3, "tactile_dot", 0.9, 1.2, [220, 20, 260, 60])
        result = tactile_context.analyze({"objects": [line, connected, disconnected]})
        self.assertEqual(result[0]["object_id"], 3)

    def test_five_meter_boundary_without_line(self):
        for distance, count in ((2.0, 1), (2.01, 0)):
            with self.subTest(distance=distance):
                tactile_context.reset_state()
                dot = Detection(1, "tactile_dot", 0.9, distance, [280, 80, 360, 120])
                self.assertEqual(len(tactile_context.analyze({"objects": [dot]})), count)

    def test_middle_third_boundaries_with_actual_frame_width(self):
        # 폭 900의 가운데 구역은 300~600. 물체 중심 기준이며 경계를 포함한다.
        for x, count in ((299, 0), (300, 1), (600, 1), (601, 0)):
            with self.subTest(x=x):
                tactile_context.reset_state()
                dot = Detection(1, "tactile_dot", 0.9, 2.0, [x - 10, 50, x + 10, 70])
                result = tactile_context.analyze({"objects": [dot]}, frame_width=900)
                self.assertEqual(len(result), count)


if __name__ == "__main__":
    unittest.main()
