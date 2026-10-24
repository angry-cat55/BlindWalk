# 현재 3번 모듈은 객체의 위치로 안내 대상을 고르고,
# 클래스로 우선순위를 정하는 방식이다.
#
# 1. 입력 데이터를 받는다.
# frame_data에서 전체 객체 목록과 이미지 너비·높이를 읽는다.
# 이미지 크기가 없으면 위치를 추측하지 않고 []를 반환한다.
#
# 2. 두 가지 영역을 준비한다.
# - 점자블록 영역: tactile_line, tactile_dot의 contour를 사용한다.
#   contour가 없으면 해당 블록은 건너뛴다.
# - 전방 영역: 화면 아래쪽 중앙에 사다리꼴을 만든다.
#   실제 경로 인식이 아니라, 휴대폰이 정면을 본다는 가정의 임시 영역이다.
#
# 3. 대상 객체의 아래쪽을 확인한다.
# 정해둔 10개 클래스만 분석한다. 각 객체의 bbox 아래쪽 15%를
# 바닥에 닿는 부분으로 가정한다.
# 그 부분에 100개의 표본점을 놓고 다음 순서로 확인한다.
# - 점자블록 영역 안에 10개 초과가 들어가면 → "점자블록 위 …"
# - 아니면 전방 사다리꼴 안에 10개 초과가 들어가면 → "전방에 …"
# - 둘 다 아니면 → 안내 대상에서 제외
# 두 조건에 모두 해당해도 점자블록 안내 하나만 만든다.
#
# 4. 클래스별 우선순위를 붙인다.
# - URGENT: 차량
# - INFO: 사람, 시설물
# - CAUTION: 계단, 단차, 볼라드, 기둥, 가로수, 자전거, 적재물
# 거리나 접근 속도는 사용하지 않는다. URGENT도 충돌 임박을 측정한 값이
# 아니라 차량을 먼저 안내하기 위한 기본 정책이다.
#
# 5. 짧은 안내 결과를 반환한다.
# 예를 들어 점자블록 위 볼라드라면:
# - situation: WALKING_HAZARD
# - object_id: 해당 볼라드 ID
# - message: 점자블록 위 볼라드
# - priority: CAUTION
# 선택된 객체들의 결과를 리스트로 반환한다.
# 정렬·반복 안내 제한·TTS·진동은 이 모듈에서 하지 않는다.
#
# 하단 15%, 겹침 10%, 사다리꼴 모양은 초기 실험 기준이며
# 실제 영상으로 검증·조정해야 한다.

import math


# 클래스별 짧은 이름과 기본 안내 우선순위다.
# URGENT는 차량의 기본 안내 정책이며 충돌 임박을 측정한 결과가 아니다.
CLASS_POLICY = {
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

# 시연 코드의 하단 15%·겹침 10%를 초기 실험 기준으로 사용한다.
# 아래 기준과 중앙 사다리꼴은 실제 영상에서 조정·검증해야 한다.
FOOT_RATIO = 0.15
OVERLAP_RATIO = 0.10
SAMPLE_GRID = 10


def _valid_polygon(contour):
    """외곽선이 없거나 유효한 다각형 좌표가 아니면 사용하지 않는다."""
    if not contour or len(contour) < 3:
        return False

    return all(
        len(point) == 2 and all(math.isfinite(value) for value in point)
        for point in contour
    )


def _contains(polygon, x, y):
    """수평선을 그어 다각형 안쪽인지 확인한다. OpenCV 없이 계산한다."""
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
    """하단 영역의 10×10 표본으로 다각형들과 겹치는 비율을 근사한다."""
    if not polygons:
        return False

    x1, y1, x2, y2 = foot
    hits = 0

    # 각 칸의 중심을 검사한다. 여러 점자블록이 겹쳐도 한 번만 센다.
    for row in range(SAMPLE_GRID):
        y = y1 + (row + 0.5) * (y2 - y1) / SAMPLE_GRID

        for column in range(SAMPLE_GRID):
            x = x1 + (column + 0.5) * (x2 - x1) / SAMPLE_GRID
            if any(_contains(polygon, x, y) for polygon in polygons):
                hits += 1

    return hits / (SAMPLE_GRID * SAMPLE_GRID) > OVERLAP_RATIO


def _foot_region(bbox, width, height):
    """원본 bbox의 하단 15%를 구하고 영상 범위 안으로 제한한다."""
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
    """전체 객체에서 진행 영역에 걸친 대상을 골라 공통 결과 목록을 반환한다."""
    width = frame_data.get("image_width")
    height = frame_data.get("image_height")

    # 영상 크기를 추측하지 않는다. 기존 크기 없는 호출은 빈 결과로 유지한다.
    if not all(
        isinstance(value, (int, float)) and math.isfinite(value) and value > 0
        for value in (width, height)
    ):
        return []

    objects = frame_data.get("objects", [])
    tactile_polygons = [
        obj.contour
        for obj in objects
        if obj.class_name in {"tactile_line", "tactile_dot"}
        and _valid_polygon(obj.contour)
    ]

    # 정면을 보는 휴대폰을 가정한 임시 진행 영역이다. 실제 경로 추정은 아니다.
    # 위쪽은 좁고 아래쪽은 넓다. 좌표를 비율로 정해 해상도에 맞춘다.
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

        foot = _foot_region(obj.bbox, width, height)
        if foot is None:
            continue

        # 두 조건에 모두 맞으면 더 구체적인 '점자블록 위'를 우선한다.
        # 객체 하나는 결과 하나만 만든다. 프레임 간 반복 제한은 별도 담당이다.
        if _overlaps(foot, tactile_polygons):
            location = "점자블록 위"
        elif _overlaps(foot, [forward_polygon]):
            location = "전방에"
        else:
            continue

        label, priority = CLASS_POLICY[obj.class_name]
        results.append({
            "situation": "WALKING_HAZARD",
            "object_id": obj.id,
            "message": f"{location} {label}",
            "priority": priority,
        })

    # 거리 비교·정렬·음성·진동은 하지 않고 판단 결과만 반환한다.
    return results
