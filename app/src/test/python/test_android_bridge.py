import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "main" / "python"))
import frame_interface


class AndroidBridgeTest(unittest.TestCase):
    def test_real_detection_json_reaches_situation_modules(self):
        objects = [dict(id=3, class_name="overhang", confidence=0.9,
                        distance_m=None, bbox=[10, 20, 100, 200], contour=None)]
        results = json.loads(frame_interface.analyze_json(7, json.dumps(objects), 640, 480))
        self.assertEqual(results, [dict(situation="OVERHEAD_HAZARD", object_id=3,
                                       message="돌출물 주의", priority="CAUTION")])

    def test_frame_size_and_class_policy_are_used(self):
        obj = dict(id=2, class_name="vehicle", confidence=0.9,
                   distance_m=None, bbox=[280, 250, 360, 440], contour=None)
        results = json.loads(frame_interface.analyze_json(1, json.dumps([obj]), 640, 480))
        self.assertEqual(results[0]["priority"], "URGENT")
        self.assertEqual(results[0]["message"], "전방에 차량")
        self.assertEqual(json.loads(frame_interface.analyze_json(2, "[]", 640, 480)), [])


if __name__ == "__main__":
    unittest.main()
