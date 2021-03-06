import logging
import os
import pathlib
import shutil
import time
from typing import Union

import dotenv

from . import session
from . import solve
from .ccl import CCLFile
from .cmd import call_cmd
from .core import AnalysisType
from .core import CFXFile
from .result import CFXResFile, CFXResFiles, _predict_new_res_filename
from .utils import change_suffix
from .utils import touch_stp
from .. import CFX_DOTENV_FILENAME
from ..typing import PATHLIKE

logger = logging.getLogger(__package__)
dotenv.load_dotenv(CFX_DOTENV_FILENAME)

CFX5SOLVE = os.environ.get("cfx5solve")


# def update_cfx_case(func):
#     def update_cfx_case_wrapper(*args, **kwargs):
#         args[0].update()
#         return func(*args, **kwargs)
#
#     return update_cfx_case_wrapper


class CFXCase(CFXFile):
    """Class wrapped around the *.cfx case file.

    Case assumtions:
    ----------------
    The case file (.cfx) and the definition file ('.def') have the same stem, e.g.:
    `mycase.cfx` and `mycase.def`.
    The result files (.res) will look like `mycase_001.res` and `maycase_002.res` and so on.
    """

    def __init__(self, filename):
        """
        Avoids error when multiple cfx files are available in
        one folder, e.g. *._frz, *_trn.cfx
        """
        super().__init__(filename)
        if not self.filename.exists():
            raise FileExistsError(f'CFX file does not exist: {self.filename}')
        self.update()

    @property
    def name(self):
        return self.filename.stem

    def __repr__(self):
        self.refresh_results()
        _outstr = f"Working dir: {self.filename.parent}"
        if len(self.res_files) == 0:
            _outstr += '\nNo result files yet'
        else:
            for i, res_file in enumerate(self.res_files):
                _outstr += f"\n\t#{i:3d}: {res_file.filename.name}"
        return _outstr

    def refresh_results(self):
        res_filename_list = list(self.working_dir.glob(f'{self.filename.stem}*.res'))
        def_filename = change_suffix(self.filename, '.def')
        self.res_files = CFXResFiles(filenames=res_filename_list, def_filename=def_filename)

    def __str__(self):
        return self.__repr__()

    def __getitem__(self, item):
        self.update()
        return self.res_files[item]

    def copy(self, new_name: Union[str, PATHLIKE]):
        """copies this case .cfx file to a new location with a new name.
        If a string is provided, the new file will be created at the same working directory.
        A new instance of CFXCase is returned."""
        if isinstance(new_name, str):
            if not new_name.endswith('.cfx'):
                new_name += '.cfx'
            new_filename = self.working_dir.joinpath(new_name)
        else:
            new_filename = new_name
        if not new_filename.parent.exists():
            new_filename.parent.mkdir(parents=True)
        if not new_filename.suffix == '.cfx':
            raise ValueError(f'The new filename has a wrong suffix. Expected .cfx: {new_filename}')
        return CFXCase(shutil.copy(self.filename, new_filename))

    def rename(self, new_name: str) -> None:
        """renames all files of this case to the new name if still available (no conflict with existing files
        in the working direcotry.
        If succesful, it returns a new instance"""
        if new_name.endswith('.cfx'):
            new_name = new_name.rsplit('.cfx')[0]
        new_filename = self.working_dir.joinpath(f'{new_name}.cfx').resolve()
        if not new_filename.parent.exists():
            new_filename.parent.mkdir(parents=True)

        if new_filename == self.filename:
            return

        all_files = list(self.working_dir.glob(f'{self.stem}*'))

        def change_stem(fname, new_stem):
            stem = fname.stem
            name = fname.name
            _new_name = name.replace(stem, new_stem)
            return pathlib.Path(fname.parent.joinpath(_new_name))

        all_new_files = [change_stem(fname, new_name) for fname in all_files]

        for new_fname in all_new_files:
            if new_fname.exists():
                raise FileExistsError(f'Cannot rename because found already such file: {new_fname}')

        for s, t in zip(all_files, all_new_files):
            s.rename(t)

        self.filename = new_filename
        self.update()

    def update(self):
        """Mainly scans for all relevant case files and updates content if needed"""
        if not self.filename.suffix == '.cfx':
            raise ValueError(f'Expected suffix .cfx and not {self.filename.suffix}')

        self.working_dir = self.filename.parent

        if not self.working_dir.exists():
            raise NotADirectoryError('The working directory does not exist. Can only work with existing cases!')

        def_filename = change_suffix(self.filename, '.def')
        if not def_filename.exists():
            def_filename = session.cfx2def(self.filename)
            if not def_filename.exists():
                raise RuntimeError(f'Seems that solver file was not written from {self.filename}')

        res_filename_list = list(self.working_dir.glob(f'{self.filename.stem}*.res'))
        self.res_files = CFXResFiles(filenames=res_filename_list, def_filename=def_filename)

        self.ccl = CCLFile(self.filename, aux_dir=self.aux_dir)

        # # generate the .ccl file from the .def file if exists and younger than .cfx file
        # # otherwise built from .cfx file
        # if self.def_file.filename.exists():
        #     if self.def_file.filename.stat().st_mtime > self.filename.stat().st_mtime:
        #         self.ccl = self.def_file.generate_ccl()
        #     else:
        #         logger.info('The definition file is older than the cfx file. Writig new .def file and .ccl file')
        #         self.def_file.update()
        #         self.ccl = CCLFile(self.filename)
        # else:
        #     self.ccl = CCLFile(self.filename)

    # @property
    # def timestep(self):
    #     """returns the time step of the registered def file thus calls timestep property of CFXDefFile instance"""
    #     return self.def_file.timestep
    #
    # @timestep.setter
    # def timestep(self, timestep):
    #     """returns the time step of the registered def file thus calls timestep property of CFXDefFile instance"""
    #     return self.def_file.set_timestep(timestep)

    @property
    def result_files(self):
        """alias for self.res_files"""
        return self.res_files

    @property
    def latest(self):
        """Returns the latest .cfx file"""
        self.refresh_results()
        return self.res_files.latest

    @property
    def analysis_type(self) -> AnalysisType:
        """returns the analysis type"""
        _target_grp = self.ccl.root_group.sub_groups['FLOW: Flow Analysis 1'].sub_groups['ANALYSIS TYPE']
        if 'Steady State' in _target_grp.get_lines()[0]:
            return AnalysisType.STEADYSTATE
        return AnalysisType.TRANSIENT

    def stop(self, wait: bool = True, timeout: int = 600) -> bool:
        """touches a stp-file in the working directory. Returns True if file was detected, False if not"""
        list_of_dir_names = list(self.working_dir.glob('*.dir'))
        for d in list_of_dir_names:
            if self.filename.stem == d.stem[:-4]:
                touch_stp(d)

        if len(list_of_dir_names) == 0:
            print('Nothing to stop.')
            return

        if wait:
            new_filename = _predict_new_res_filename(self.filename)
            print(f'waiting for {new_filename}')
            for i in range(timeout):
                time.sleep(1)  # 1s
            if new_filename.exists():
                print(f'... file has been detected')
            print(f'Waited {timeout} seconds but did not find {new_filename} during in the meantime.')
            return False
        return True

    def start(self, initial_result_file: Union[None, CFXResFile, str, bytes, os.PathLike, pathlib.Path],
              nproc: int, timeout: int = None, wait: bool = False) -> str:
        """starts from a given initial solution of any result file provided or, if None, starts from
        initial flow field"""
        self.update_from_ccl()
        def_filename = change_suffix(self.filename, '.def')
        if initial_result_file is None:
            # if len(self.res_files) == 0:
            cmd = solve.build_cmd(def_filename=def_filename, nproc=nproc,
                                  ini_filename=None, timeout=timeout)
            call_cmd(cmd, wait=wait)
            return cmd

        if isinstance(initial_result_file, CFXResFile):
            _initial_result_file = initial_result_file.filename
            _init = CFXResFile(filename=_initial_result_file, def_filename=def_filename)
        else:  # path is given
            _init = CFXResFile(filename=initial_result_file, def_filename=def_filename)
        return _init.resume(nproc, timeout, wait=wait)


    def resume(self, *args, **kwargs):
        """updates cfx file and def file from ccl file and resumes on latest"""
        logger.info(f'Updateing cfx from ccl file')
        self.update_from_ccl()
        session.cfx2def(self.filename)
        self.latest.resume(*args, **kwargs)

    def update_from_ccl(self):
        """Imports a .ccl file into a .cfx file and saves the .cfx file"""
        ccl_filename = self.ccl.to_ccl(change_suffix(self.ccl.filename, '.ccl'))
        _ = session.importccl(self.filename, ccl_filename)
        self.update()

    # def _scan_res_files(self):
    #     res_filename_list = list(self.working_dir.glob(f'{self.filename.stem}*.res'))
    #     self.res_files = CFXResFiles(res_filename_list, def_filename)

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

    # @property
    # def expression(self):
    #     return "expression"
    #
    # @expression.setter
    # def expression(self, expr_dict: dict):
    #     if not isinstance(expr_dict, dict):
    #         raise TypeError(f'Expression value must type dict not {type(expr_dict)}')
    #     expr = self.ccl.expressions

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
