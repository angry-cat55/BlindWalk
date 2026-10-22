import unittest
import sys
import os

# app/src/main/python 경로 추가
APP_PYTHON_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "main", "python")
)
if APP_PYTHON_DIR not in sys.path:
    sys.path.insert(0, APP_PYTHON_DIR)

from detection import Detection
import frame_interface


class DetectionInterfaceTest(unittest.TestCase):
    def test_detection_dataclass_creation_and_to_dict(self):
        """Detection 데이터클래스 생성 및 to_dict 직렬화 검증"""
        det = Detection(
            id=1,
            class_name="tactile_line",
            confidence=0.92345,
            distance_m=1.234,
            bbox=[100, 150, 250, 400],
            contour=[[100, 150], [250, 150], [250, 400], [100, 400]],
        )
        self.assertEqual(det.id, 1)
        self.assertEqual(det.class_name, "tactile_line")
        self.assertEqual(det.bbox, [100, 150, 250, 400])
        self.assertEqual(len(det.contour), 4)

        d = det.to_dict()
        self.assertEqual(d["id"], 1)
        self.assertEqual(d["class_name"], "tactile_line")
        self.assertEqual(d["confidence"], 0.9234)
        self.assertEqual(d["distance_m"], 1.23)
        self.assertEqual(d["bbox"], [100, 150, 250, 400])
        self.assertEqual(d["contour"], [[100, 150], [250, 150], [250, 400], [100, 400]])

    def test_detection_without_contour_defaults_to_none(self):
        """contour가 없는 경우 None 허용 여부 검증"""
        det = Detection(
            id=2,
            class_name="bollard",
            confidence=0.88,
            distance_m=2.5,
            bbox=[50, 50, 100, 150],
        )
        self.assertIsNone(det.contour)
        d = det.to_dict()
        self.assertIsNone(d["contour"])

    def test_build_frame_with_detections(self):
        """build_frame에 frame_id 및 Detection 리스트 주입 시 정합성 검증"""
        det1 = Detection(id=1, class_name="stairs", confidence=0.9, distance_m=2.1, bbox=[10, 20, 30, 40])
        det2 = Detection(id=2, class_name="curb", confidence=0.85, distance_m=0.8, bbox=[5, 10, 15, 20])

        frame_data = frame_interface.build_frame(
            frame_id=42,
            objects=[det1, det2],
            situations=["TACTILE_ANOMALY", "WALKING_HAZARD"],
        )
        self.assertEqual(frame_data["frame_id"], 42)
        self.assertEqual(len(frame_data["objects"]), 2)
        self.assertEqual(frame_data["objects"][0].class_name, "stairs")
        self.assertEqual(frame_data["objects"][1].class_name, "curb")
        self.assertEqual(frame_data["situations"], ["TACTILE_ANOMALY", "WALKING_HAZARD"])

    def test_analyze_receives_detections_in_frame_data(self):
        """상황 분석 함수(analyze)가 Detection 객체를 안전하게 전달받는지 검증"""
        det = Detection(id=1, class_name="tactile_dot", confidence=0.95, distance_m=0.5, bbox=[0, 0, 100, 100])
        frame_data = frame_interface.build_frame(
            frame_id=10,
            objects=[det],
            situations=["TACTILE_ANOMALY", "TACTILE_CONTEXT", "WALKING_HAZARD", "OVERHEAD_HAZARD"],
        )
        # 현재 상황 모듈들은 TODO 상태(return [])이므로 빈 리스트 반환
        results = frame_interface.analyze(frame_data)
        self.assertIsInstance(results, list)
        self.assertEqual(results, [])

    def test_backward_compatibility_empty_call(self):
        """기존 스켈레톤 호출 방식과의 하위 호환성 검증"""
        frame_data = frame_interface.build_frame(0)
        self.assertEqual(frame_data["frame_id"], 0)
        self.assertEqual(frame_data["objects"], [])
        self.assertEqual(frame_data["situations"], [])

        test_res = frame_interface.run_test("TACTILE_ANOMALY")
        self.assertEqual(test_res, [])


if __name__ == "__main__":
    unittest.main()
