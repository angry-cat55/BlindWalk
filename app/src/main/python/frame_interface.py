import tactile_anomaly
import tactile_context
import walking_hazard
import overhead_hazard


def build_frame(frame_id, model_results=None):
    # TODO: 하나 이상의 AI 예측을 공통 objects로 정리하고 situations를 결정한다.
    # 모델이 미정이므로 현재는 입력 예측을 분석하지 않고 빈 데이터만 반환한다.
    return {"frame_id": frame_id, "objects": [], "situations": []}


def analyze(frame_data):
    # 지정된 상황 모듈만 호출하고 결과를 합친다. 세부 판단은 각 모듈이 담당한다.
    results = []
    if "TACTILE_ANOMALY" in frame_data["situations"]:
        results.extend(tactile_anomaly.analyze(frame_data))
    if "TACTILE_CONTEXT" in frame_data["situations"]:
        results.extend(tactile_context.analyze(frame_data))
    if "WALKING_HAZARD" in frame_data["situations"]:
        results.extend(walking_hazard.analyze(frame_data))
    if "OVERHEAD_HAZARD" in frame_data["situations"]:
        results.extend(overhead_hazard.analyze(frame_data))
    return results


def run_test(situation):
    # 버튼 연결 확인 전용: 실제 판단 대신 버튼이 지정한 상황으로 빈 함수를 호출한다.
    frame_data = build_frame(0)
    frame_data["situations"] = [situation]
    return analyze(frame_data)
