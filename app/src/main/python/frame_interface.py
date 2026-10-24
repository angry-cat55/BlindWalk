from typing import List, Optional, Dict, Any
from detection import Detection
import tactile_anomaly
import tactile_context
import walking_hazard
import overhead_hazard


# 3번 상황을 분석할 지상 장애물·단차 클래스다.
# 클래스 번호는 모델마다 달라질 수 있으므로 이름으로 비교한다.
WALKING_HAZARD_CLASSES = {
    "stairs",
    "curb",
    "bollard",
    "pole",
    "tree_trunk",
    "bicycle",
    "movable_signage",
    "vehicle",
    "person",
    "facility",
}


def select_situations(objects: List[Detection]) -> List[str]:
    """탐지된 클래스에 따라 실행할 분석 종류를 고른다. 위험 확정은 아니다."""

    # 같은 클래스가 여러 번 탐지돼도 한 번만 확인한다.
    class_names = {obj.class_name for obj in objects}
    situations = []

    # 2번: 점형 블록이 있으면 주변 환경 분석을 요청한다.
    # 주변 계단·횡단보도 등과의 관계는 해당 모듈에서 판단한다.
    if "tactile_dot" in class_names:
        situations.append("TACTILE_CONTEXT")

    # 3번: 대상 클래스가 하나라도 있으면 일반 보행 위험 분석을 요청한다.
    # 실제 진행 경로 침범이나 거리 기준은 여기서 판단하지 않는다.
    if class_names & WALKING_HAZARD_CLASSES:
        situations.append("WALKING_HAZARD")

    # 4번: 돌출물이 있으면 머리 높이 장애물 분석을 요청한다.
    # 탐지만으로 실제 높이나 충돌 위험이 확정되는 것은 아니다.
    if "overhang" in class_names:
        situations.append("OVERHEAD_HAZARD")

    # 1번 점자블록 이상 판단은 자동 선택하지 않는다.
    # 순서는 항상 2 → 3 → 4이며 여러 상황을 동시에 선택할 수 있다.
    return situations


def build_frame(
    frame_id: int,
    objects: Optional[List[Detection]] = None,
    situations: Optional[List[str]] = None,
    model_results: Optional[List[Detection]] = None,
    *,
    image_width: Optional[int] = None,
    image_height: Optional[int] = None,
) -> Dict[str, Any]:
    """
    특정 frame_id에 해당하는 AI 검출 객체 목록(List[Detection])을 받아 공통 frame_data를 생성한다.
    - objects 또는 model_results 인자로 전달된 Detection 리스트를 frame_data['objects']에 배치한다.
    - situations를 생략하면 클래스 이름으로 2·3·4 상황을 자동 선택한다.
    - 직접 지정한 목록은 테스트용으로 그대로 사용한다. 빈 목록은 분석 선택을 끈다.
    """
    # 1. 전달받은 전체 객체를 유지한다. objects가 있으면 우선 사용한다.
    # model_results는 기존 호출과의 호환을 위해 유지하는 인자다.
    if objects is not None:
        target_objects = objects
    elif model_results is not None:
        target_objects = model_results
    else:
        target_objects = []

    # 2. 호출자가 상황을 직접 지정하지 않은 경우에만 자동으로 선택한다.
    if situations is None:
        target_situations = select_situations(target_objects)
    else:
        target_situations = situations

    # 3. 같은 프레임의 식별자·전체 객체·분석 목록을 묶어서 반환한다.
    # 여기서는 모듈을 실행하지 않는다. 실행은 아래 analyze()의 역할이다.
    frame_data = {
        "frame_id": frame_id,
        "objects": target_objects,
        "situations": target_situations,
    }

    # bbox·contour와 같은 좌표계의 영상 크기다. 모델 텐서 크기가 아니다.
    # 기존 호출 형식은 유지하고, 크기를 제공한 호출에만 필드를 추가한다.
    if image_width is not None and image_height is not None:
        frame_data["image_width"] = image_width
        frame_data["image_height"] = image_height

    return frame_data


def analyze(frame_data: Dict[str, Any]) -> List[Any]:
    # 지정된 상황 모듈만 호출하고 결과를 합친다. 세부 판단은 각 모듈이 담당한다.
    results = []
    situations = frame_data.get("situations", [])

    # 기존 수동 테스트 호출은 보존한다. 자동 분류에서는 1번을 선택하지 않는다.
    if "TACTILE_ANOMALY" in situations:
        results.extend(tactile_anomaly.analyze(frame_data))

    # 각 모듈에 전체 frame_data를 전달해 주변 객체도 함께 볼 수 있게 한다.
    if "TACTILE_CONTEXT" in situations:
        results.extend(tactile_context.analyze(frame_data))

    if "WALKING_HAZARD" in situations:
        results.extend(walking_hazard.analyze(frame_data))

    if "OVERHEAD_HAZARD" in situations:
        results.extend(overhead_hazard.analyze(frame_data))

    # 판단 결과만 합친다. 음성·진동 실행은 이 인터페이스에서 하지 않는다.
    return results


def run_test(situation: str) -> List[Any]:
    # 버튼 연결 확인 전용: 실제 판단 대신 버튼이 지정한 상황으로 빈 함수를 호출한다.
    frame_data = build_frame(0, situations=[situation])
    return analyze(frame_data)
