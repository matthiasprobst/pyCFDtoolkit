import pathlib
from dataclasses import dataclass
from typing import Dict

import h5py

from . import CFXBoundaryCondition
from . import axis, flowdir
from ...typing import PATHLIKE


class InletBoundaryCondition(CFXBoundaryCondition):
    boundary_type: str = 'INLET'
    content_dict: Dict = {}

    def write(self, hdf_filename: PATHLIKE, bdry_h5_path: str) -> None:
        h5path_pathlib = pathlib.Path(bdry_h5_path)
        group_name = h5path_pathlib.stem
        boundary_ccl_name, boundary_user_name = group_name.split(':', 1)
        assert boundary_ccl_name == 'BOUNDARY'

        with h5py.File(hdf_filename, 'r+') as h5:
            h5[bdry_h5_path].attrs['BOUNDARY TYPE'] = self.boundary_type

            print(f'deleting {bdry_h5_path}/BOUNDARY CONDITIONS')
            del h5[f'{bdry_h5_path}/BOUNDARY CONDITIONS']

            bdry_cond_grp = h5[bdry_h5_path].create_group('BOUNDARY CONDITIONS')
            print(f'create grp: {bdry_cond_grp.name}')

            def _write_group(_grp, _dict):
                for k, v in _dict.items():
                    if isinstance(v, dict):
                        subgrp = _grp.create_group(k)
                        print(f'creating group {subgrp.name}')
                        print(str(v))
                        _write_group(subgrp, v)
                    else:
                        _grp.attrs[k] = v
                        print(f'creating attrs [{_grp.name}] {k}: {v}')

            _write_group(bdry_cond_grp, self.content_dict)

            # for k, v in self.content_dict.items():
            #     grp = bdry_cond_grp.create_group(k)
            #     for ak, av in v.items():
            #         grp.attrs[ak] = av


@dataclass
class MassFlowInlet(InletBoundaryCondition):
    flow_regime: str
    mass_flow_rate: float
    flow_direction: flowdir.FlowDirection
    mass_flow_rate_area: str = 'As Specified'  # "As Specified" or  "Total for All Sectors"
    boundary_type: str = 'INLET'
    content_dict = {}

    def __post_init__(self):
        if self.mass_flow_rate_area not in ('As Specified', 'Total for All Sectors'):
            raise ValueError(f'Mass flow rate area must be one of those two: '
                             f'"As Specified", "Total for All Sectors"')
        self.content_dict = {'FLOW REGIME': {'Option': self.flow_regime.capitalize()},
                             'MASS AND MOMENTUM': {'Mass Flow rate': f'{self.mass_flow_rate} [kg s^-1]',
                                                   'Mass Flow rate Area': self.mass_flow_rate_area},
                             'FLOW DIRECTION': {'Option': self.flow_direction.option}
                             }
        if isinstance(self.flow_direction, flowdir.NormalToBoundary):
            pass
        elif isinstance(self.flow_direction, flowdir.CartesianComponents):
            self.content_dict['FLOW DIRECTION'] = {'X Componen': self.flow_direction.xcomp,
                                                   'Y Componen': self.flow_direction.ycomp,
                                                   'Z Componen': self.flow_direction.zcomp}
        elif isinstance(self.flow_direction, flowdir.CylindricalComponents):
            self.content_dict['FLOW DIRECTION'] = {'Axial Component': self.flow_direction.axial_comp,
                                                   'Radial Component': self.flow_direction.radial_comp,
                                                   'Theta Component': self.flow_direction.theta_comp,
                                                   'Axis Defnition': {'Option': self.flow_direction.option}}
            if isinstance(self.flow_direction.axis_definition, axis.CoordinateAxis):
                self.content_dict['FLOW DIRECTION'] = {
                    'Axis Defnition': {'Rotation Axis': self.flow_direction.axis_definition.rotation_axis}
                }
            elif isinstance(self.flow_direction.axis_definition, axis.CylindricalComponents):
                from_str = '{}[m],{}[m],{}[m]'.format(*self.flow_direction.axis_definition.rotation_axis_from)
                to_str = '{}[m],{}[m],{}[m]'.format(*self.flow_direction.axis_definition.rotation_axis_to)
                self.content_dict['FLOW DIRECTION'] = {
                    'Axis Defnition': {'Rotation Axis From': from_str,
                                       'Rotation Axis To': to_str}
                }
            else:
                raise TypeError(f'Unknown Axis Definition: {type(self.flow_direction)}. '
                                f'Must be CoordinateAxis or CylindricalComponents')


@dataclass
class NormalSpeed(InletBoundaryCondition):
    """Normal Speed inlet condition. Note, if turbulent, turbulence must be set"""
    normal_speed: float
    flow_regime: str = 'Subsonic'
    boundary_type: str = 'INLET'

    def __post_init__(self):
        self.content_dict = {'FLOW REGIME': {'Option': self.flow_regime.capitalize()},
                             'MASS AND MOMENTUM': {'Normal Speed': f'{self.normal_speed} [m s^-1]',
                                                   'Option': 'Normal Speed'}}

    def __repr__(self):
        return f'NormalSpeed (Inlet Boundary Condition)\n  normalspeed={self.normal_speed}' \
               f'\n  flow regime={self.flow_regime}'
