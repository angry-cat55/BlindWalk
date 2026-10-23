import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "main" / "python"))

from detection import Detection
import frame_interface
import walking_hazard


def detection(name, box, object_id=1, contour=None, distance=None):
    return Detection(object_id, name, 0.9, distance, box, contour)


class WalkingHazardTest(unittest.TestCase):
    def frame(self, *objects, width=640, height=480):
        return {
            "frame_id": 1,
            "objects": list(objects),
            "image_width": width,
            "image_height": height,
        }

    def test_class_priority_and_short_message(self):
        classes = {
            "vehicle": ("차량", "URGENT"),
            "person": ("사람", "INFO"),
            "facility": ("시설물", "INFO"),
            "stairs": ("계단", "CAUTION"),
            "curb": ("단차", "CAUTION"),
            "bollard": ("볼라드", "CAUTION"),
            "pole": ("기둥", "CAUTION"),
            "tree_trunk": ("가로수", "CAUTION"),
            "bicycle": ("자전거", "CAUTION"),
            "movable_signage": ("적재물", "CAUTION"),
        }
        for name, (label, priority) in classes.items():
            with self.subTest(name=name):
                obj = detection(name, [280, 250, 360, 440], object_id=7)
                self.assertEqual(walking_hazard.analyze(self.frame(obj)), [{
                    "situation": "WALKING_HAZARD",
                    "object_id": 7,
                    "message": f"전방에 {label}",
                    "priority": priority,
                }])

    def test_side_and_upper_objects_are_not_announced(self):
        for box in ([0, 250, 50, 440], [280, 0, 360, 100]):
            self.assertEqual(walking_hazard.analyze(self.frame(detection("vehicle", box))), [])

    def test_tactile_overlap_takes_precedence_and_works_outside_center(self):
        block = detection("tactile_line", [0, 300, 640, 480], object_id=2,
                          contour=[[0, 300], [640, 300], [640, 480], [0, 480]])
        for box in ([280, 250, 360, 440], [10, 250, 80, 440]):
            results = walking_hazard.analyze(self.frame(block, detection("bollard", box)))
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["message"], "점자블록 위 볼라드")

    def test_bbox_overlap_without_foot_overlap_is_not_tactile_overlap(self):
        block = detection("tactile_dot", [0, 200, 100, 300], object_id=2,
                          contour=[[0, 200], [100, 200], [100, 300], [0, 300]])
        obj = detection("bollard", [10, 220, 80, 440])
        self.assertEqual(walking_hazard.analyze(self.frame(block, obj)), [])

    def test_missing_contour_does_not_use_tactile_bbox_as_mask(self):
        block = detection("tactile_line", [0, 200, 100, 480])
        obj = detection("bollard", [10, 220, 80, 440], object_id=2)
        self.assertEqual(walking_hazard.analyze(self.frame(block, obj)), [])

    def test_distance_does_not_change_priority_and_unknown_classes_are_ignored(self):
        for distance in (None, 0.5, 100):
            objects = [detection("vehicle", [280, 250, 360, 440], distance=distance),
                       detection("overhang", [280, 250, 360, 440], object_id=2)]
            results = walking_hazard.analyze(self.frame(*objects))
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["priority"], "URGENT")

    def test_missing_size_and_invalid_boxes_return_empty(self):
        obj = detection("vehicle", [280, 250, 360, 440])
        self.assertEqual(walking_hazard.analyze({"objects": [obj]}), [])
        for box in ([1, 1, 1, 2], [5, 5, 1, 1], [-100, 0, -1, 100]):
            self.assertEqual(walking_hazard.analyze(self.frame(detection("vehicle", box))), [])
        self.assertEqual(walking_hazard.analyze(self.frame(obj, width=0)), [])

    def test_normalized_area_is_independent_of_resolution(self):
        small = detection("bicycle", [280, 250, 360, 440])
        large = detection("bicycle", [560, 500, 720, 880])
        self.assertEqual(walking_hazard.analyze(self.frame(small)),
                         walking_hazard.analyze(self.frame(large, width=1280, height=960)))

    def test_build_frame_passes_size_to_analyzer(self):
        frame = frame_interface.build_frame(
            42, [detection("bicycle", [280, 250, 360, 440])],
            image_width=640, image_height=480,
        )
        self.assertEqual(frame["image_width"], 640)
        self.assertEqual(frame["image_height"], 480)
        self.assertEqual(frame_interface.analyze(frame)[0]["message"], "전방에 자전거")

    def test_overlap_threshold_and_multiple_contour_union(self):
        # 정확히 10%면 제외하고, 여러 블록 영역은 중복 없이 합산한다.
        foot = (0, 0, 100, 100)
        strip = [[0, 0], [10, 0], [10, 100], [0, 100]]
        second = [[90, 0], [100, 0], [100, 100], [90, 100]]
        self.assertFalse(walking_hazard._overlaps(foot, [strip]))
        self.assertFalse(walking_hazard._overlaps(foot, [strip, strip]))
        self.assertTrue(walking_hazard._overlaps(foot, [strip, second]))

    def test_invalid_contour_and_partial_offscreen_box(self):
        block = detection("tactile_line", [0, 0, 100, 480],
                          contour=[[0, 0], [float("nan"), 0], [100, 480]])
        side = detection("person", [0, 250, 50, 440], object_id=2)
        self.assertEqual(walking_hazard.analyze(self.frame(block, side)), [])

        # 화면 밖 좌표는 잘라서 계산한다. 무한대 좌표는 제외한다.
        partial = detection("vehicle", [-100, 250, 360, 440])
        self.assertEqual(len(walking_hazard.analyze(self.frame(partial))), 1)
        invalid = detection("vehicle", [0, 0, float("inf"), 440])
        self.assertEqual(walking_hazard.analyze(self.frame(invalid)), [])


if __name__ == "__main__":
    unittest.main()
