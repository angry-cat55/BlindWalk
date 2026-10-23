"""로컬 영상의 1초 간격 프레임에 실제 모델·점형 판단을 실행하고 관찰 기록을 저장한다."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import cv2
import torch

from ai_pipeline import BlindWalkAIPipeline
import frame_interface
import tactile_context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("videos", nargs="+", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    summaries = []
    for path in args.videos:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise RuntimeError(f"영상을 열 수 없음: {path}")
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0:
            cap.release()
            raise RuntimeError(f"영상 FPS 확인 불가: {path}")
        pipeline = BlindWalkAIPipeline(enable_tracking=True)
        tactile_context.reset_state()
        output = args.output_dir / path.stem
        writer = cv2.VideoWriter(str(output.with_suffix(".mp4")), cv2.VideoWriter_fourcc(*"mp4v"), 1, (640, 480))
        if not writer.isOpened():
            cap.release()
            raise RuntimeError(f"결과 영상을 쓸 수 없음: {output}")
        counts = Counter()
        started = time.monotonic()
        try:
            with output.with_suffix(".jsonl").open("w") as log:
                for second in range(int(frame_count / fps) + 1):
                    source_index = round(second * fps)
                    if source_index >= frame_count:
                        break
                    cap.set(cv2.CAP_PROP_POS_FRAMES, source_index)
                    ok, image = cap.read()
                    if not ok:
                        counts["read_errors"] += 1
                        continue
                    h, w = image.shape[:2]
                    crop_w, crop_h = (int(h * 4 / 3), h) if w / h >= 4 / 3 else (w, int(w * 3 / 4))
                    left, top = (w - crop_w) // 2, (h - crop_h) // 2
                    image = cv2.resize(image[top:top + crop_h, left:left + crop_w], (640, 480))
                    frame = pipeline.process_frame(second + 1, image)
                    frame["timestamp"] = source_index / fps
                    results = frame_interface.analyze(frame)
                    objects = [{**obj.to_dict(), "distance_raw_m": obj.distance_m} for obj in frame["objects"]]
                    log.write(json.dumps({"source_frame": source_index, "time_s": frame["timestamp"],
                                          "objects": objects, "results": results}, ensure_ascii=False, allow_nan=False) + "\n")
                    dots = [obj for obj in frame["objects"] if obj.class_name == "tactile_dot"]
                    counts["sampled_frames"] += 1
                    counts["dot_frames"] += bool(dots)
                    counts["announcements"] += len(results)
                    counts["unknown_distance_objects"] += sum(obj.distance_m is None for obj in frame["objects"])
                    for x in (640 // 3, 640 * 2 // 3):
                        cv2.line(image, (x, 0), (x, 479), (255, 200, 0), 2)
                    for dot in dots:
                        x1, y1, x2, y2 = dot.bbox
                        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 220, 255), 2)
                        label = f"dot #{dot.id}: {dot.distance_m:.2f}m" if dot.distance_m is not None else f"dot #{dot.id}: unknown"
                        cv2.putText(image, label, (x1, max(40, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
                    cv2.putText(image, f"t={second}s | dots={len(dots)} | announcements={len(results)}", (8, 22),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
                    writer.write(image)
                    if second % 20 == 0:
                        print(f"{path.name}: {counts['sampled_frames']} frames", flush=True)
        finally:
            cap.release()
            writer.release()
        summaries.append({"video": str(path.resolve()), "duration_s": frame_count / fps,
                          "sampling": "1 frame per source second", "counts": dict(counts),
                          "elapsed_s": time.monotonic() - started, "model": pipeline.model_path,
                          "depth_model": pipeline.depth_model_path, "scale_k": pipeline.scale_k,
                          "accuracy_validated": False})
        (args.output_dir / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2))
        print(json.dumps(summaries[-1], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
