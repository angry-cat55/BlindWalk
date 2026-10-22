from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class Detection:
    """
    단일 검출 객체의 표준 표현 데이터클래스.
    - 점자블록 및 일반 물체 모두 bbox와 contour를 지원한다.
    - distance_m은 Depth 추정 모델을 통해 산출된 미터 단위 추정 거리이다.
    """
    id: int                                   # 프레임 내 객체 식별자 (1, 2, 3...)
    class_name: str                           # 모델에서 동적으로 인식된 클래스명
    confidence: float                         # 검출 신뢰도 (0.0 ~ 1.0)
    distance_m: float                         # 카메라로부터의 추정 거리 (미터 단위)
    bbox: List[int]                           # 경계상자 [x1, y1, x2, y2] (정수 픽셀 좌표)
    contour: Optional[List[List[int]]] = None # 외곽선 다각형 [[x, y], [x, y], ...] (정수 픽셀 좌표)

    def to_dict(self) -> Dict[str, Any]:
        """JSON 또는 브릿지 통신을 위한 딕셔너리 변환"""
        return {
            "id": self.id,
            "class_name": self.class_name,
            "confidence": round(float(self.confidence), 4),
            "distance_m": round(float(self.distance_m), 2),
            "bbox": self.bbox,
            "contour": self.contour,
        }

