# 4번 모듈은 overhang 탐지 자체를 돌출물 존재 안내로 전달한다.
# 실제 머리 높이나 충돌 임박을 판단하는 모듈은 아니다.
#
# 1. 전체 객체 목록을 받는다.
# frame_interface가 overhang을 발견하면 OVERHEAD_HAZARD를 선택하지만,
# 모듈에는 다른 클래스도 포함된 전체 objects가 전달된다.
#
# 2. overhang 객체만 선택한다.
# 위치 영역·거리·영상 크기로 추가 필터링하지 않는다.
# 임의의 화면 영역으로 돌출물을 제외하지 않는 대신,
# 화면 옆에 있는 돌출물도 안내될 수 있다.
#
# 3. 객체마다 공통 형식의 결과 하나를 만든다.
# - situation: OVERHEAD_HAZARD
# - object_id: 해당 객체 ID
# - message: 돌출물 주의
# - priority: CAUTION
# 현재 클래스는 overhang 하나이므로 간판·나뭇가지 등의
# 상세 종류를 추측해서 안내하지 않는다.
#
# 4. 결과 목록을 반환한다.
# overhang이 없으면 []를 반환한다.
# 정렬·반복 안내 제한·TTS·진동은 이 모듈에서 하지 않는다.
# 같은 객체의 프레임 간 반복 안내는 추후 공통 안내 처리에서 담당한다.


def analyze(frame_data):
    """overhang 객체마다 짧은 돌출물 주의 안내를 반환한다."""
    results = []

    # 전체 객체 중 4번 모듈의 대상 클래스만 읽는다.
    for obj in frame_data.get("objects", []):
        if obj.class_name != "overhang":
            continue

        # 거리와 위치에 관계없이 존재를 안내한다. 입력 데이터는 수정하지 않는다.
        results.append({
            "situation": "OVERHEAD_HAZARD",
            "object_id": obj.id,
            "message": "돌출물 주의",
            "priority": "CAUTION",
        })

    return results
