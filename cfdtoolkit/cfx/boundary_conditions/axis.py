from dataclasses import dataclass
from typing import List

@dataclass
class AxisDefinition:
    pass

@dataclass
class CoordinateAxis(AxisDefinition):
    rotation_axis: str  # 'Global X', 'Global Y', 'Global Z'


@dataclass
class TwoPointAxisDefinition(AxisDefinition):
    rotation_axis_from: List[float]  # x, y, z coordinaes
    rotation_axis_to: List[float]  # x, y, z coordinate
