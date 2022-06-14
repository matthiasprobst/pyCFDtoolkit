import os
import pathlib
import shlex
import shutil
import time
from dataclasses import dataclass
from typing import Union
from warnings import warn

import dotenv

from . import solve
from .ccl import CCLTextFile, CCLHDFGroup
from .ccl import generate as generate_ccl
from .core import AnalysisType, CFXResFile, CFXResFiles, touch_stp, _predict_new_res_filename, CFXDefFile
from .core import CFXFile
from .. import CFX_DOTENV_FILENAME
from .cmd import call_cmd
dotenv.load_dotenv(CFX_DOTENV_FILENAME)
AUXDIRNAME = '.pycfdtoolbox'

CFX5SOLVE = os.environ.get("cfx5solve")


def update_cfx_case(func):
    def update_cfx_case_wrapper(*args, **kwargs):
        args[0]._scan_res_files()
        return func(*args, **kwargs)

    return update_cfx_case_wrapper


@dataclass
class CFXCase(CFXFile):
    """Class wrapped around the *.cfx case file"""

    @update_cfx_case
    def __repr__(self):
        _outstr = f"Working dir: {self.filename.parent}"
        if len(self.res_files) == 0:
            _outstr += '\nNo result files yet'
        else:
            for i, res_file in enumerate(self.res_files):
                _outstr += f"\n\t#{i:3d}: {res_file.filename.name}"
        return _outstr

    @update_cfx_case
    def __str__(self):
        print(self.__repr__())

    @update_cfx_case
    def __getitem__(self, item):
        return self.res_files[item]

    def __post_init__(self):
        """
        Avoids error when multiple cfx files are available in
        one folder, e.g. *._frz, *_trn.cfx
        """
        super().__post_init__()
        if not self.filename.suffix == '.cfx':
            raise ValueError(f'Expected suffix .cfx and not {self.filename.suffix}')
        self.working_dir = self.filename.parent

        if not self.working_dir.exists():
            raise NotADirectoryError('The working directory does not exist. Can only work with existing cases!')
        self._scan_for_files()

    @property
    def timestep(self):
        """returns the time step of the registered def file thus calls timestep property of CFXDefFile instance"""
        return self.def_file.timestep

    @timestep.setter
    def timestep(self, timestep):
        """returns the time step of the registered def file thus calls timestep property of CFXDefFile instance"""
        return self.def_file.set_timestep(timestep)

    @property
    def result_files(self):
        """alias for self.res_files"""
        return self.res_files

    @property
    @update_cfx_case
    def latest(self):
        if len(self.res_files) > 0:
            return self.res_files[-1]
        else:
            raise ValueError('No result files registered!')

    @update_cfx_case
    def is_latest(self):
        """returns whether this CFXFile is the latest in the list."""
        return self == self.res_files[-1]

    @property
    def latest_res_file(self):
        return self.res_files[-1]

    @property
    def analysis_type(self) -> AnalysisType:
        """returns the analysis type"""
        _target_grp = self.def_file.ccl.root_group.sub_groups['FLOW: Flow Analysis 1'].sub_groups['ANALYSIS TYPE']
        if 'Steady State' in _target_grp.get_lines()[0]:
            return AnalysisType.STEADYSTATE
        return AnalysisType.TRANSIENT

    # def write_ccl_file(self, ccl_filename=None, overwrite=True):
    #     """writes a ccl file from a *.cfx file"""
    #     if ccl_filename is None:
    #         ccl_filename = self.aux_dir.joinpath(f'{self.filename.stem}.ccl')
    #     return CCLFile(generate_ccl(input_file=self.def_file.filename, ccl_filename=ccl_filename,
    #                                 cfx5pre=None, overwrite=overwrite))

    def stop(self, wait: bool = True, timeout: int = 600):
        """touches a stp-file in the working directory"""
        list_of_dir_names = list(self.working_dir.glob('*.dir'))
        for d in list_of_dir_names:
            if self.def_file.stem == d.stem[:-4]:
                touch_stp(d)

        if len(list_of_dir_names) == 0:
            print('No *.dir names found.')
            return

        if wait:
            new_filename = _predict_new_res_filename(self.filename)
            print(f'waiting for {new_filename}')
            time_count = 0
            _break = False
            while not new_filename.exists():
                time.sleep(1)  # 1s
                time_count += 1
                if time_count > timeout:
                    _break = True
                    break
            if _break:
                print(f'Waited {timeout} seconds but did not find {new_filename} during in the meantime.')
            else:
                print(f'... file has been detected')

    def start(self, initial_result_file: Union[None, CFXResFile, str, bytes, os.PathLike, pathlib.Path],
              nproc: int, timeout: int = None, wait: bool = False) -> str:
        """starts from a given initial solution of any result file provided or, if None, starts from
        initial flow field"""
        if initial_result_file is None:
            # if len(self.res_files) == 0:
            cmd = solve.build_cmd(def_filename=self.def_file.filename, nproc=nproc,
                                  ini_filename=None, timeout=timeout)
            call_cmd(cmd, wait=wait)
            return cmd

        if isinstance(initial_result_file, CFXResFile):
            _initial_result_file = initial_result_file.filename
            _init = CFXResFile(filename=_initial_result_file, def_file=self.def_file)
        else:  # path is given
            _init = CFXResFile(filename=initial_result_file, def_file=self.def_file)
        return _init.resume(nproc, timeout, wait=wait)

    def _scan_for_files(self):
        """scans for cfx files (.cfx and .res and .def, and .ccl)"""
        def_filename_list = list(self.working_dir.glob(f'{self.filename.stem}.def'))
        if len(def_filename_list) > 1:
            raise ValueError(
                f'The case has multiple ({len(def_filename_list)}) *.def files. Only one is expected and allowed')
        if len(def_filename_list) == 1:
            self.def_file = CFXDefFile(def_filename_list[0])
            if self.def_file.stem != self.filename.stem:
                warn('The name of the case file and the definition file are different. This is unusual: '
                     f'{self.filename.name} vs. {self.def_file.name}')
        else:  # == 0
            self.def_file = CFXDefFile(self.guess_definition_filename())
        self._scan_res_files()

    def _scan_res_files(self):
        res_filename_list = list(self.working_dir.glob(f'{self.filename.stem}*.res'))
        self.res_files = CFXResFiles(res_filename_list, self.def_file)

    def guess_definition_filename(self):
        return self.working_dir.joinpath(f'{self.filename.stem}.def')

    def _predict_new_res_filename(self):
        return _predict_new_res_filename(self.filename)

    def reset(self, force=True):
        """Resets the case, so deletes .out and .res files"""
        if not force:
            answer = input('Are you sure? This will delete the following file patterns: '
                           f'{self.filename.stem}*.out and {self.filename.stem}*.res [y/N]')
        else:
            answer = 'y'
        if answer == 'y':
            _list_of_files = self.working_dir.glob(f'{self.filename.stem}*.out')
            _ = [f.unlink() for f in _list_of_files]
            _list_of_files = self.working_dir.glob(f'{self.filename.stem}*.res')
            _ = [f.unlink() for f in _list_of_files]
            _list_of_files = self.working_dir.glob(f'{self.filename.stem}*[0-9]')
            _ = [shutil.rmtree(f) for f in _list_of_files]
            _list_of_files = self.aux_dir.glob(f'{self.filename.stem}*.monitor')
            _ = [f.unlink() for f in _list_of_files]

#
# class SteadyStateCFX(CFXCase):
#     def __init__(self, working_dir='.'):
#         super().__init__(working_dir)
#         self.result_directory = self.working_dir.joinpath('steady_state')
#         if not self.result_directory.exists():
#             self.result_directory.mkdir()
#
#
# class TransientCFX(CFXCase):
#     pass
