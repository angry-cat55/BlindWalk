import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "main" / "python"))
import frame_interface


class FrameInterfaceTest(unittest.TestCase):
    # 선택한 모듈만 호출하고 같은 프레임과 반환 결과를 전달하는지 확인한다.
    def test_selected_modules_receive_same_frame_and_combine_results(self):
        frame = {"frame_id": 7, "objects": [], "situations": ["TACTILE_CONTEXT", "OVERHEAD_HAZARD"]}
        with (
            patch("frame_interface.tactile_anomaly.analyze") as anomaly,
            patch("frame_interface.tactile_context.analyze", return_value=["context"]) as context,
            patch("frame_interface.walking_hazard.analyze") as walking,
            patch("frame_interface.overhead_hazard.analyze", return_value=["overhead"]) as overhead,
        ):
            self.assertEqual(frame_interface.analyze(frame), ["context", "overhead"])
            self.assertIs(context.call_args.args[0], frame)
            self.assertIs(overhead.call_args.args[0], frame)
            anomaly.assert_not_called()
            walking.assert_not_called()

    # 상황이 지정되지 않았으면 분석기를 실행하지 않는다.
    def test_empty_situations_do_not_call_analyzers(self):
        with patch("frame_interface.tactile_anomaly.analyze") as analyzer:
            self.assertEqual(frame_interface.analyze({"frame_id": 0, "objects": [], "situations": []}), [])
            analyzer.assert_not_called()

    # 버튼이 선택한 상황은 자동 판단 없이 테스트 호출로만 전달된다.
    def test_button_target_reaches_analyzer(self):
        with patch("frame_interface.walking_hazard.analyze", return_value=[]) as analyzer:
            self.assertEqual(frame_interface.run_test("WALKING_HAZARD"), [])
            frame = analyzer.call_args.args[0]
            self.assertEqual(frame["situations"], ["WALKING_HAZARD"])
            self.assertEqual(frame["objects"], [])


if __name__ == "__main__":
    unittest.main()
