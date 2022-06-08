import os
import pathlib
from dataclasses import dataclass
from enum import Enum
from typing import Union
from warnings import warn

from .ccl import CCLFile
from .ccl import generate as generate_ccl

AUXDIR = '.pycfdtoolbox'


class AnalysisType(Enum):
    STEADYSTATE = 1
    TRANSIENT = 2


@dataclass
class CFXFile:
    """Base wrapper class around a generic Ansys CFX file"""
    filename: Union[str, bytes, os.PathLike, pathlib.Path]

    @property
    def name(self):
        return self.filename.name

    @property
    def stem(self):
        return self.filename.stem

    @property
    def parent(self):
        return self.filename.parent

    def __post_init__(self):
        self.filename = pathlib.Path(self.filename)


@dataclass
class CFXResFile(CFXFile):
    """Class wrapped around the *.res case file"""
    pass


@dataclass
class CFXCaseFile(CFXFile):
    """Class wrapped around the *.cfx case file"""

    def write_ccl_file(self, ccl_filename=None, overwrite=False):
        """writes a ccl file from a *.cfx file"""
        if ccl_filename is None:
            ccl_filename = self.parent.joinpath(f'{self.stem}.ccl')
        return CCLFile(generate_ccl(self.filename, ccl_filename, overwrite))


@dataclass
class CFXDefFile(CFXFile):
    """Class wrapped around the *.def case file"""

    ccl: CCLFile = None

    def write_ccl_file(self, ccl_filename=None, overwrite=False) -> pathlib.Path:
        """writes a ccl file from a *.cfx file"""
        if ccl_filename is None:
            ccl_filename = self.parent.joinpath(f'{self.stem}.ccl')
        self.ccl = CCLFile(generate_ccl(self.filename, ccl_filename, overwrite))
        return self.ccl.filename


@dataclass
class CFXCase:
    working_dir: Union[str, bytes, os.PathLike, pathlib.Path] = '.'
    pattern: Union[str, bytes, os.PathLike, pathlib.Path] = '*'

    @property
    def analysis_type(self) -> AnalysisType:
        """returns the analysis type"""
        _target_grp = self.def_file.ccl.root_group.sub_groups['FLOW: Flow Analysis 1'].sub_groups['ANALYSIS TYPE']
        if 'Steady State' in _target_grp.get_lines()[0]:
            return AnalysisType.STEADYSTATE
        return AnalysisType.TRANSIENT

    def __post_init__(self):
        """
        pattern can be sub string of filename or complete pattern. Avoids error when multiple cfx files are available in
        one folder, e.g. *._frz, *_trn.cfx
        """
        self.working_dir = pathlib.Path(self.working_dir)

        if self.pattern is None or self.pattern == '':
            self.pattern = '*'

        if not self.working_dir.exists():
            raise NotADirectoryError('The working directory does not exist. Can only work with existing cases!')
        self._scan_for_files()
        self._make_aux_dir()

    def _make_aux_dir(self):
        self._aux_dir = self.working_dir.joinpath(AUXDIR)
        if not self._aux_dir.exists():
            self._aux_dir.mkdir()

    def _scan_for_files(self):
        """scans for cfx files (.cfx and .def, and .ccl)"""
        cfx_files = list(self.working_dir.glob(f'{self.pattern}.cfx'))
        if len(cfx_files) == 0:
            raise ValueError(f'No CFX case file ({self.pattern}.cfx) was found but one is required')
        if len(cfx_files) > 1:
            raise ValueError(f'The case has multiple ({len(cfx_files)}) *.cfx files. Only one is expected and allowed')
        self.case_file = CFXCaseFile(cfx_files[0])

        def_files = list(self.working_dir.glob(f'{self.pattern}.def'))
        if len(def_files) > 1:
            raise ValueError(f'The case has multiple ({len(cfx_files)}) *.def files. Only one is expected and allowed')
        if len(def_files) == 1:
            self.def_file = CFXDefFile(def_files[0])
            if self.def_file.stem != self.case_file.stem:
                warn('The name of the case file and the definition file are different. This is unusual: '
                     f'{self.case_file.name} vs. {self.def_file.name}')
        else:
            self.def_file = CFXDefFile(self.guess_definition_filename())

            self.working_dir.glob(f'{self.pattern}.def')
            self.working_dir.glob(f'{self.pattern}.ccl')

    def guess_definition_filename(self):
        return self.working_dir.joinpath(f'{self.case_file.filename.stem}.def')

    def write_ccl_file(self):
        self.def_file.write_ccl_file(self._aux_dir.joinpath(f'{self.case_file.stem}.ccl'))


class SteadyStateCFX(CFXCase):
    def __init__(self, working_dir='.'):
        super().__init__(working_dir)
        self.result_directory = self.working_dir.joinpath('steady_state')
        if not self.result_directory.exists():
            self.result_directory.mkdir()


class TransientCFX(CFXCase):
    pass
