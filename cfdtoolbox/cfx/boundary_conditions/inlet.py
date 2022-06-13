from dataclasses import dataclass
from . import CCLBoundaryCondition

class InletBoundaryCondition(CCLBoundaryCondition):
    pass

@dataclass
class MassFlowInlet(InletBoundaryCondition):
    pass


@dataclass
class NormalSpeed:
    """Normal Speed inlet condition. Note, if turbulent, turbulence must be set"""
    flow_regime: str
    normal_spped: float

    def generate_string(self):
        """generates the string to be placed in the CCL file"""
        _flow_regime = f'{self.flow_regime[0].capitalize()}{self.flow_regime[1:].lower()}'
        units = 'm s^-1'  # use default units from SOLUTION UNITS
        f"""BOUNDARY CONDITIONS:
  FLOW REGIME:
    Option = {_flow_regime}
  END
  MASS AND MOMENTUM:
    Normal Speed = {self.normal_speed} [{units}]
    Option = Normal Speed
  END
END"""
