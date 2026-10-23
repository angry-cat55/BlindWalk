"""
tactile_context.py
점형블록 주변 환경 분석 및 갈림길(분기점) / 도착점(시설물 연계) 판단 모듈.

핵심 원칙:
1. 카메라가 사용자 진행 방향을 바라본다는 전제로 화면 가로 가운데 1/3을 대상으로 합니다.
2. 위아래 위치나 선형블록 접촉 여부와 무관하게 5.0m 이내의 가장 가까운 점형 구역을 선택합니다.
3. 서로 맞닿아 있는 인접 점형 블록들은 단일 점형 구역(Merged Cluster)으로 병합하여 분석합니다.
4. 해당 타겟 점형블록에서 좌/우로 분기되는 갈림길(Branch) 또는
   시설물(횡단보도/계단/엘리베이터)과 연계된 도착점(Destination)을 판정합니다.
5. docs/situation-handoff.md의 공통 4대 키 규격(situation, object_id, message, priority)을 준수합니다.
"""

import math
import time
from typing import List, Dict, Any, Optional, Set
from detection import Detection


# 안내 유효 거리 기준 (미터) - 최대 5.0m
MIN_VALID_DISTANCE_M = 0.0
MAX_VALID_DISTANCE_M = 5.0

# 동일 지점/클러스터 중복 안내 방지 쿨다운 시간 (초)
COOLDOWN_SECONDS = 3.0

# 최근 안내 상태 기록 (인접 블록 중 일부가 소멸되어도 중복 발화 방지)
_last_announcement: Dict[str, Any] = {
    "member_ids": set(),
    "timestamp": 0.0,
    "distance_m": 0.0,
    "category": None,
}


def reset_state():
    """상태 초기화 (테스트 격리 및 세션 리셋용)"""
    global _last_announcement
    _last_announcement = {
        "member_ids": set(),
        "timestamp": 0.0,
        "distance_m": 0.0,
        "category": None,
    }

# 목적지/안내 연계 대상 시설물 클래스 매핑
FACILITY_CLASSES = {
    "crosswalk": "횡단보도",
    "elevator": "엘리베이터",
    "elevator_sign": "엘리베이터 표지",
    "stairs": "계단",
    "traffic_light": "신호등",
    "toilet_sign": "화장실 표지"
}


def _box_center(bbox: List[int]) -> tuple:
    """바운딩 박스의 중심점 (cx, cy) 계산"""
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _boxes_touch(box1: List[int], box2: List[int], margin: int = 35) -> bool:
    """두 바운딩 박스가 마진 범위 내에서 맞닿거나 겹치는지 검사."""
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2
    return not (
        (x1_max + margin < x2_min) or
        (x1_min - margin > x2_max) or
        (y1_max + margin < y2_min) or
        (y1_min - margin > y2_max)
    )


class DotCluster:
    """맞닿아 있는 여러 점형 블록들을 하나로 통합한 점형 구역 클러스터"""
    def __init__(self, dots: List[Detection]):
        self.dots = dots
        # 클러스터에 포함된 모든 점형 블록의 ID 집합 (일부 소멸 시 중복 방지 추적용)
        self.member_ids: Set[int] = {d.id for d in dots}
        # 대표 ID: 가장 가깝거나 신뢰도 높은 블록
        sorted_dots = sorted(dots, key=lambda d: (d.distance_m if d.distance_m is not None else 999.0, -d.confidence))
        self.primary_id = sorted_dots[0].id

        # 통합 바운딩 박스
        x1 = min(d.bbox[0] for d in dots)
        y1 = min(d.bbox[1] for d in dots)
        x2 = max(d.bbox[2] for d in dots)
        y2 = max(d.bbox[3] for d in dots)
        self.bbox = [x1, y1, x2, y2]

        # 대표 거리 (가장 가까운 거리)
        valid_dists = [d.distance_m for d in dots if d.distance_m is not None]
        self.distance_m = min(valid_dists) if valid_dists else None
        self.center = _box_center(self.bbox)


def _should_suppress_announcement(target_cluster: DotCluster, category: str, now: float) -> bool:
    """
    최근 안내된 클러스터의 구성원이 일부 남아있거나 동일 지점을 통과 중인 경우 중복 안내 억제.
    """
    elapsed = now - _last_announcement["timestamp"]
    if elapsed > COOLDOWN_SECONDS:
        return False

    # 1. 이전 안내 클러스터의 멤버 블록 중 하나라도 현재 클러스터에 포함되어 있으면 중복 억제
    # (예: A와 B가 묶여 안내된 후, A가 사라지고 B만 남아도 다시 말하지 않음)
    if bool(_last_announcement["member_ids"] & target_cluster.member_ids):
        return True

    # 2. 동일 범주(category) 안내이고, 이전 안내 거리보다 가까워지며 통과 중인 경우 스킵
    if _last_announcement["category"] == category and target_cluster.distance_m <= _last_announcement["distance_m"] + 0.5:
        return True

    return False


def _record_announcement(target_cluster: DotCluster, category: str, now: float):
    """안내 발화 상태 갱신"""
    global _last_announcement
    _last_announcement["member_ids"] = set(target_cluster.member_ids)
    _last_announcement["timestamp"] = now
    _last_announcement["distance_m"] = target_cluster.distance_m
    _last_announcement["category"] = category


def _cluster_touching_dots(dot_blocks: List[Detection], touch_margin: int = 25) -> List[DotCluster]:
    """
    서로 맞닿아 있거나 인접한 점형 블록들을 하나의 클러스터로 병합 (Connected Components).
    도로에 2x2, 3x3 형태로 모여 있는 점형 블록 구역을 단일 허브로 취급.
    """
    if not dot_blocks:
        return []

    n = len(dot_blocks)
    visited = [False] * n
    clusters = []

    for i in range(n):
        if visited[i]:
            continue

        # BFS / DFS로 맞닿은 블록 탐색
        cluster_dots = []
        queue = [i]
        visited[i] = True

        while queue:
            curr_idx = queue.pop(0)
            curr_dot = dot_blocks[curr_idx]
            cluster_dots.append(curr_dot)

            for neighbor_idx in range(n):
                if not visited[neighbor_idx]:
                    neighbor_dot = dot_blocks[neighbor_idx]
                    if _boxes_touch(curr_dot.bbox, neighbor_dot.bbox, margin=touch_margin):
                        visited[neighbor_idx] = True
                        queue.append(neighbor_idx)

        clusters.append(DotCluster(cluster_dots))

    return clusters


def _find_active_footpath(linear_blocks: List[Detection], target_bbox: List[int]) -> Optional[Detection]:
    """점형 구역에 접촉하고 아래쪽으로 이어지는 선만 진입선 후보로 본다."""
    target_x, target_y = _box_center(target_bbox)
    candidates = []
    for line in linear_blocks:
        line_x, line_y = _box_center(line.bbox)
        # 좌우 분기선이나 전방 선형블록을 진입선으로 제외하지 않는다.
        if line_y - target_y > abs(line_x - target_x) and _boxes_touch(line.bbox, target_bbox, margin=50):
            candidates.append(line)
    return max(candidates, key=lambda line: line.bbox[3]) if candidates else None


def analyze(frame_data: Dict[str, Any], frame_width: int = 640) -> List[Dict[str, Any]]:
    """
    frame_data 내 Detection 객체들을 분석하여 유효 거리(<=5.0m) 내 점형블록(클러스터) 기반
    분기점(갈림길) 및 도착점을 산출한다.
    frame_width는 bbox 좌표계의 영상 가로 픽셀 수다. 기본값은 PC 예제의 640이다.
    반환은 docs/situation-handoff.md의 4대 키(situation, object_id, message, priority)를 준수한다.
    """
    objects: List[Detection] = frame_data.get("objects", [])
    if not objects:
        return []

    # 1. 클래스별 객체 분리
    linear_blocks = [o for o in objects if o.class_name == "tactile_line"]
    # 거리 미상·음수·비유한 값은 병합 전에 제외해 정상 점형에 영향을 주지 않는다.
    raw_dot_blocks = [
        o for o in objects
        if o.class_name == "tactile_dot" and o.distance_m is not None
        and math.isfinite(o.distance_m) and o.distance_m >= MIN_VALID_DISTANCE_M
    ]
    facilities = [o for o in objects if o.class_name in FACILITY_CLASSES]

    if not raw_dot_blocks:
        return []

    # 2. 붙어 있는 점형 블록들을 하나의 클러스터 구역으로 병합
    dot_clusters = _cluster_touching_dots(raw_dot_blocks, touch_margin=30)

    # 3. 통합 점형 구역의 중심이 가운데 1/3에 있고 5m 이내인 후보만 선택한다.
    # 선형블록 접촉 여부나 화면 세로 위치는 타겟 선택 조건이 아니다.
    target_clusters = [
        cluster for cluster in dot_clusters
        if frame_width / 3 <= cluster.center[0] <= frame_width * 2 / 3
        and MIN_VALID_DISTANCE_M <= cluster.distance_m <= MAX_VALID_DISTANCE_M
    ]
    if not target_clusters:
        return []

    target_cluster = min(target_clusters, key=lambda cluster: cluster.distance_m)
    # 진입 유도선은 기존 분기 분석에서만 제외하며 타겟 선정에는 사용하지 않는다.
    active_path = _find_active_footpath(linear_blocks, target_cluster.bbox)
    is_connected = active_path is not None and _boxes_touch(active_path.bbox, target_cluster.bbox, margin=50)
    cluster_center = target_cluster.center
    cluster_dist = round(target_cluster.distance_m, 1)

    # 5. 해당 타겟 점형 클러스터에서 뻗어나가는 선형 블록 가지(Spokes) 분석
    outgoing_branches = []
    for line in linear_blocks:
        if active_path and line.id == active_path.id:
            continue  # 내가 밟고 온 진입 경로는 제외

        if _boxes_touch(target_cluster.bbox, line.bbox, margin=40):
            line_center = _box_center(line.bbox)
            dx = line_center[0] - cluster_center[0]
            dy = line_center[1] - cluster_center[1]

            # 클러스터 중심 기준 좌우 또는 전방으로 뻗은 가지인지 판별
            if dx < -25:
                outgoing_branches.append("LEFT")
            elif dx > 25:
                outgoing_branches.append("RIGHT")
            elif dy < -10:
                outgoing_branches.append("STRAIGHT")

    outgoing_branches = sorted(list(set(outgoing_branches)))

    now = frame_data.get("timestamp", time.time())
    category = None
    results = []

    # 6. 분기점 vs 도착점 최종 판정 (공통 4대 키 형식 준수)
    # Case A: 뻗어나가는 선형 가지가 2개 이상 (갈림길 / T자 / 사거리)
    if len(outgoing_branches) >= 2 or ("LEFT" in outgoing_branches and "RIGHT" in outgoing_branches):
        category = "BRANCH"
        if not _should_suppress_announcement(target_cluster, category, now):
            branch_desc = "좌측 및 우측" if ("LEFT" in outgoing_branches and "RIGHT" in outgoing_branches) else ", ".join(outgoing_branches)
            results.append({
                "situation": "TACTILE_CONTEXT",
                "object_id": target_cluster.primary_id,
                "message": f"전방 {cluster_dist}m 앞 갈림길입니다 ({branch_desc} 방향).",
                "priority": "CAUTION"
            })
            _record_announcement(target_cluster, category, now)

    # Case B: 뻗어나가는 선형 가지가 1개 (방향 전환 / 굴절점)
    elif len(outgoing_branches) == 1 and outgoing_branches[0] in ("LEFT", "RIGHT"):
        category = "TURN"
        if not _should_suppress_announcement(target_cluster, category, now):
            direction_korean = "좌회전" if outgoing_branches[0] == "LEFT" else "우회전"
            results.append({
                "situation": "TACTILE_CONTEXT",
                "object_id": target_cluster.primary_id,
                "message": f"전방 {cluster_dist}m 앞 {direction_korean} 유도 블록입니다.",
                "priority": "CAUTION"
            })
            _record_announcement(target_cluster, category, now)

    # Case C: 뻗어나가는 선형 가지 없음 (경로 종료 또는 목적지 도착)
    else:
        # 점형 클러스터 전방/주변에 위치한 시설물 탐색
        nearby_facility = None
        for fac in facilities:
            fac_center = _box_center(fac.bbox)
            if fac_center[1] <= cluster_center[1] + 60 and abs(fac_center[0] - cluster_center[0]) < 200:
                nearby_facility = fac
                break

        if nearby_facility:
            category = "FACILITY"
            if not _should_suppress_announcement(target_cluster, category, now):
                fac_name = FACILITY_CLASSES.get(nearby_facility.class_name, "목적 시설")
                results.append({
                    "situation": "TACTILE_CONTEXT",
                    "object_id": nearby_facility.id,
                    "message": (f"전방 {cluster_dist}m 앞 점형블록 주변에 {fac_name}가 있습니다."
                                if nearby_facility.class_name.endswith("_sign")
                                else f"전방 {cluster_dist}m 앞 {fac_name} 도착점(정지선)입니다."),
                    "priority": "INFO"
                })
                _record_announcement(target_cluster, category, now)
        elif active_path and is_connected:
            category = "STOP"
            if not _should_suppress_announcement(target_cluster, category, now):
                results.append({
                    "situation": "TACTILE_CONTEXT",
                    "object_id": target_cluster.primary_id,
                    "message": f"전방 {cluster_dist}m 앞 정지선입니다 (경로 종료).",
                    "priority": "CAUTION"
                })
                _record_announcement(target_cluster, category, now)
        else:
            # 단독 점형도 안내하되 연결 근거 없이 경로 종료로 단정하지 않는다.
            category = "DOT"
            if not _should_suppress_announcement(target_cluster, category, now):
                results.append({
                    "situation": "TACTILE_CONTEXT",
                    "object_id": target_cluster.primary_id,
                    "message": f"전방 {cluster_dist}m 앞 점형블록이 있습니다.",
                    "priority": "CAUTION"
                })
                _record_announcement(target_cluster, category, now)

    return results
