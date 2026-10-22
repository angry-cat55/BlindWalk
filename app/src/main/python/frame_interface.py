from typing import List, Optional, Dict, Any
from detection import Detection
import tactile_anomaly
import tactile_context
import walking_hazard
import overhead_hazard


def build_frame(
    frame_id: int,
    objects: Optional[List[Detection]] = None,
    situations: Optional[List[str]] = None,
    model_results: Optional[List[Detection]] = None,
) -> Dict[str, Any]:
    """
    특정 frame_id에 해당하는 AI 검출 객체 목록(List[Detection])을 받아 공통 frame_data를 생성한다.
    - objects 또는 model_results 인자로 전달된 Detection 리스트를 frame_data['objects']에 배치한다.
    - situations는 실행할 상황 분석 목록이다. (미정인 경우 기본 빈 리스트)
    """
    target_objects = objects if objects is not None else (model_results if model_results is not None else [])
    target_situations = situations if situations is not None else []
    return {
        "frame_id": frame_id,
        "objects": target_objects,
        "situations": target_situations,
    }


def analyze(frame_data: Dict[str, Any]) -> List[Any]:
    # 지정된 상황 모듈만 호출하고 결과를 합친다. 세부 판단은 각 모듈이 담당한다.
    results = []
    situations = frame_data.get("situations", [])
    if "TACTILE_ANOMALY" in situations:
        results.extend(tactile_anomaly.analyze(frame_data))
    if "TACTILE_CONTEXT" in situations:
        results.extend(tactile_context.analyze(frame_data))
    if "WALKING_HAZARD" in situations:
        results.extend(walking_hazard.analyze(frame_data))
    if "OVERHEAD_HAZARD" in situations:
        results.extend(overhead_hazard.analyze(frame_data))
    return results


def run_test(situation: str) -> List[Any]:
    # 버튼 연결 확인 전용: 실제 판단 대신 버튼이 지정한 상황으로 빈 함수를 호출한다.
    frame_data = build_frame(0, situations=[situation])
    return analyze(frame_data)
