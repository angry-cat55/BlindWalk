import math

CLASS_POLICY = {
    "vehicle": ("차량", "URGENT"),
    "person": ("사람", "CAUTION"),
    "facility": ("시설물", "CAUTION"),
    "stairs": ("계단", "CAUTION"),
    "curb": ("단차", "CAUTION"),
    "bollard": ("볼라드", "CAUTION"),
    "pole": ("기둥", "CAUTION"),
    "tree_trunk": ("가로수", "CAUTION"),
    "bicycle": ("자전거", "CAUTION"),
    "movable_signage": ("적재물", "CAUTION"),
}

MAX_HAZARD_DISTANCE_M = 2.0
FOOT_RATIO = 0.15
OVERLAP_RATIO = 0.10
SAMPLE_GRID = 10

def _valid_polygon(contour):
    if not contour or len(contour) < 3:
        return False
    return all(len(point) == 2 and all(math.isfinite(value) for value in point) for point in contour)

def _contains(polygon, x, y):
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing_x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside

def _overlaps(foot, polygons):
    if not polygons:
        return False
    x1, y1, x2, y2 = foot
    hits = 0
    for row in range(SAMPLE_GRID):
        y = y1 + (row + 0.5) * (y2 - y1) / SAMPLE_GRID
        for column in range(SAMPLE_GRID):
            x = x1 + (column + 0.5) * (x2 - x1) / SAMPLE_GRID
            if any(_contains(polygon, x, y) for polygon in polygons):
                hits += 1
    return hits / (SAMPLE_GRID * SAMPLE_GRID) > OVERLAP_RATIO

def _foot_region(bbox, width, height):
    if len(bbox) != 4 or not all(math.isfinite(value) for value in bbox):
        return None
    x1, y1, x2, y2 = bbox
    if x2 <= x1 or y2 <= y1:
        return None
    bottom_top = y2 - (y2 - y1) * FOOT_RATIO
    foot = (max(0, x1), max(0, bottom_top), min(width, x2), min(height, y2))
    if foot[2] <= foot[0] or foot[3] <= foot[1]:
        return None
    return foot

def analyze(frame_data):
    width = frame_data.get("image_width")
    height = frame_data.get("image_height")
    if not all(isinstance(value, (int, float)) and math.isfinite(value) and value > 0 for value in (width, height)):
        return []

    objects = frame_data.get("objects", [])
    tactile_polygons = [
        obj.contour for obj in objects
        if obj.class_name in {"tactile_line", "tactile_dot"} and _valid_polygon(obj.contour)
    ]
    forward_polygon = [
        (width * 0.40, height * 0.50),
        (width * 0.60, height * 0.50),
        (width * 0.80, height),
        (width * 0.20, height),
    ]
    results = []

    for obj in objects:
        if obj.class_name not in CLASS_POLICY:
            continue

        # 2.0m 거리 필터: 2.0m를 초과하는 원거리 장애물은 안내 대상에서 배제
        if obj.distance_m is not None and obj.distance_m > MAX_HAZARD_DISTANCE_M:
            continue

        foot = _foot_region(obj.bbox, width, height)
        if foot is None:
            continue

        # Depth 추정값이 없는 경우 화면 상단(원거리) 객체 배제
        if obj.distance_m is None and foot[3] < height * 0.50:
            continue

        if _overlaps(foot, tactile_polygons):
            location = "점자블록 위"
        elif _overlaps(foot, [forward_polygon]):
            location = "전방"
        else:
            cx = (obj.bbox[0] + obj.bbox[2]) / 2.0
            if cx < width / 3.0:
                location = "좌측"
            elif cx > width * 2.0 / 3.0:
                location = "우측"
            else:
                location = "전방"

        label, priority = CLASS_POLICY[obj.class_name]
        results.append({
            "situation": "WALKING_HAZARD",
            "object_id": obj.id,
            "message": f"{location} {label}",
            "priority": priority,
        })

    return results