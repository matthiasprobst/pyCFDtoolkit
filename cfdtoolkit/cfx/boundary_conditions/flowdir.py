from dataclasses import dataclass

from .axis import AxisDefinition


@dataclass
class FlowDirection:

    def __str__(self):
        return self.option


@dataclass
class NormalToBoundary(FlowDirection):
    option: str = 'Normal to Boundary Condition'


@dataclass
class CartesianComponents(FlowDirection):
    xcomp: float
    ycomp: float
    zcomp: float
    option: str = 'Cartesian Components'


@dataclass
class CylindricalComponents(FlowDirection):
    axial_comp: float
    radial_comp: float
    theta_comp: float
    axis_definition: AxisDefinition
    option: str = 'Cylidrical Components'
