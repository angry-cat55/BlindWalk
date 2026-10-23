import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "main" / "python"))

from detection import Detection
import frame_interface
import overhead_hazard


def detection(name, object_id, bbox=None):
    return Detection(
        id=object_id,
        class_name=name,
        confidence=0.9,
        distance_m=None,
        bbox=bbox if bbox is not None else [0, 0, 100, 100],
    )


class OverheadHazardTest(unittest.TestCase):
    def test_empty_or_other_classes_return_empty(self):
        self.assertEqual(overhead_hazard.analyze({}), [])
        self.assertEqual(overhead_hazard.analyze({"objects": []}), [])
        self.assertEqual(overhead_hazard.analyze({
            "objects": [detection("pole", 1), detection("facility", 2)],
        }), [])

    def test_each_overhang_returns_short_caution_without_geometry_filter(self):
        objects = [
            detection("overhang", 7, [0, 0, 10, 20]),
            detection("person", 8),
            detection("overhang", 9, [600, 400, 640, 480]),
        ]
        results = overhead_hazard.analyze({"objects": objects})

        self.assertEqual(results, [
            {
                "situation": "OVERHEAD_HAZARD",
                "object_id": object_id,
                "message": "돌출물 주의",
                "priority": "CAUTION",
            }
            for object_id in (7, 9)
        ])
        self.assertEqual(len(objects), 3)

    def test_automatic_selection_and_module_call(self):
        frame = frame_interface.build_frame(42, [detection("overhang", 3)])
        self.assertEqual(frame["situations"], ["OVERHEAD_HAZARD"])
        self.assertEqual(frame_interface.analyze(frame), [{
            "situation": "OVERHEAD_HAZARD",
            "object_id": 3,
            "message": "돌출물 주의",
            "priority": "CAUTION",
        }])


if __name__ == "__main__":
    unittest.main()
