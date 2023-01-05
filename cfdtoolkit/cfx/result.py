import logging
import os
import pathlib
import subprocess
import time
from typing import Union, List

import dotenv

from .installation import CFXInstallation
from . import solve
from .core import OutFile, MonitorData
from .session import run_session_file
from .utils import change_suffix, touch_stp
from .. import CFX_DOTENV_FILENAME
from ..typing import PATHLIKE

cfxinst = CFXInstallation()

dotenv.load_dotenv(CFX_DOTENV_FILENAME)

CFX5SOLVE = os.environ.get("cfx5solve")

logger = logging.getLogger(__package__)


def _predict_new_res_filename(current_filename: PATHLIKE):
    current_filename = pathlib.Path(current_filename)
    if current_filename.suffix in ('.cfx', '.def'):
        list_of_res_files = sorted(list(current_filename.parent.glob(f'{current_filename.stem}*.res')))
        if len(list_of_res_files) == 0:
            latest_res_file = None
            name_prefix = current_filename.stem
            new_number = 1
        else:
            latest_res_file = list_of_res_files[-1]

    elif current_filename.suffix == '.res':
        latest_res_file = current_filename
    else:
        raise ValueError(f'Unknown file suffix: {current_filename.suffix}. Must be ".cfx", ".def" or ".res"')

    if latest_res_file is not None:
        name_prefix, name_suffix = latest_res_file.stem.rsplit('_', 1)
        new_number = int(name_suffix) + 1
    return current_filename.parent.joinpath(f'{name_prefix}_{new_number:03d}.res')


def res2cfx(res_filename):
    _res_filename = pathlib.Path(res_filename)
    if not _res_filename.exists():
        raise FileNotFoundError(f'Result file "{res_filename}" not found.')
    case_parent = _res_filename.parent
    case_name = _res_filename.stem.rsplit('_', 1)[0]
    cfx_filename = case_parent / f'{case_name}.cfx'
    run_session_file('res2cfx.pre', {'__version__': cfxinst.version,
                                     '__resfilename__': str(res_filename),
                                     '__cfxfilename__': str(cfx_filename)})
    return cfx_filename


class CFXResFile:
    """Class wrapped around the *.res case file"""

    def __init__(self, filename):
        self.filename = pathlib.Path(filename)
        self.outfile = OutFile(change_suffix(self.filename, '.out'))

    def __repr__(self):
        return f'<CFXResFile name={self.name}>'

    def write_cfx_file(self):
        """create the cfx file corresponding to this res file"""
        return res2cfx(self.filename)

    def unlink(self):
        """delete the .res and .out file"""
        self.filename.unlink()
        self.outfile.filename.unlink()

    @property
    def name(self) -> str:
        return self.filename.stem

    @property
    def monitor(self):
        return MonitorData(self.filename)

    @property
    def out_data(self):
        return OutFile(self.filename)

    @property
    def is_running(self):
        if self.filename.exists():
            return False
        else:
            print('Probably running, but not checked if it might have crashed!')
            return True

    def is_crashed(self):
        if self.filename.exists():
            return False
        print('Honestly, dont know! Check to be written')  # TODO check if crashed!4
        return True

    def resume(self, nproc: int, def_filename: Union[PATHLIKE, None] = None,
               timeout: str = None) -> str:
        """resumes the computation from this result file

        Parameters
        ----------
        nproc: int
            Number of processors to use
        def_filename: PATHLIKE or None, optional=None
            Definition file. If None, the filename will be assumed based on the result filename stem
        timeout: int
            Maximal time in seconds after which run is stopped independent of solver settings

        Returns
        -------
        cmd: str
            The generated command line string to resume the computation.
        """
        if def_filename is None:
            def_filename = self.def_filename
            logger.debug(f'Resuming on def file: {def_filename}')

        if def_filename.exists():
            cmd = solve.build_cmd(def_filename=self.def_filename, nproc=nproc,
                                  ini_filename=self.filename, timeout=timeout)
        else:
            raise FileNotFoundError(f'Could not find definition file: {def_filename}')
        p = subprocess.run(cmd, shell=True)
        return cmd

    @property
    def number(self):
        """returns the number in the filename e.g. 5 for mycase_005.res"""
        name = self.filename.stem
        return int(name.rsplit('_', 1)[1])

    def _predict_new_res_filename(self):
        return _predict_new_res_filename(self.filename)

    def _predict_new_dir_dirname(self):
        """predicts the *.dir directory for the next run"""
        current_number = self.number
        return self.filename.parent.joinpath(f'{str(self.filename.stem)[:-3]}{current_number + 1:03d}.dir')

    def stop(self, wait: bool = True, timeout: int = 600) -> bool:
        """stops a current run. If wait is True, the method will wait until the *.res file exists.
        Timeout is set to 600 seconds. If in this time no file res file is written, there might
        have been an error..."""
        dirname = self._predict_new_dir_dirname()
        new_filename = pathlib.Path(dirname)
        new_filename.suffix = '.res'
        # new_filename = self._predict_new_res_filename()
        if dirname.exists():
            touch_stp(dirname)
        else:
            raise NotADirectoryError(f'Failed touching a stp-file: {dirname}')
        if wait:
            print(f'waiting for {new_filename}')
            for i in range(timeout):
                time.sleep(1)  # 1s
            if new_filename.exists():
                print(f'... file has been detected')
                return True
            print(f'Waited {timeout} seconds but did not find {new_filename} during in the meantime.')
            return False
        return True

    @property
    def is_latest(self):
        """returns whether this CFXFile is the latest in the list."""
        filenames = sorted(list(self.working_dir.glob(f'{self.case_stem}*.res')))
        return self.filename == filenames[-1]


# @dataclass
# class FutureCFXResFile:
#     """dummy class if no CFXResFile is stored in CFXResFiles class"""
#     def_file: CFXDefFile
#
#     def _predict_new_res_filename(self):
#         current_number = 0
#         return self.filename.parent.joinpath(f'{str(self.filename.stem)[:-3]}{current_number + 1:03d}.res')

class CFXResFiles:

    def __init__(self, filenames: List[PATHLIKE], def_filename: PATHLIKE, sort: bool = True):
        self.filenames = filenames
        self.def_filename = def_filename
        self.sort = sort
        self.update()

    def update(self):
        if self.sort:
            self.cfx_res_files = [CFXResFile(filename, self.def_filename) for filename in sorted(self.filenames)]
        else:
            self.cfx_res_files = [CFXResFile(filename, self.def_filename) for filename in self.filenames]

    def __len__(self):
        return len(self.cfx_res_files)

    def __getitem__(self, item):
        return self.cfx_res_files[item]

    @property
    def latest(self):
        self.update()
        if len(self) > 0:
            return self[-1]
        else:
            return None
