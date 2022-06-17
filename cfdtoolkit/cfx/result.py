import logging
import os
import pathlib
import time
from dataclasses import dataclass
from typing import Union, List

import dotenv

from . import solve
from .cmd import call_cmd
from .core import CFXFile
from .core import OutFile, MonitorData
from .definition import CFXDefFile
from .utils import touch_stp
from .. import CFX_DOTENV_FILENAME

dotenv.load_dotenv(CFX_DOTENV_FILENAME)
AUXDIRNAME = '.pycfdtoolbox'

CFX5SOLVE = os.environ.get("cfx5solve")

logger = logging.getLogger(__package__)


def _predict_new_res_filename(current_filename: Union[str, bytes, os.PathLike]):
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


@dataclass
class CFXResFile(CFXFile):
    """Class wrapped around the *.res case file"""

    def_file: CFXDefFile

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

    def resume(self, nproc: int, timeout: str = None, wait: bool = False) -> str:
        """resumes the computation from this result file

        Parameters
        ----------
        nproc: int
            Number of processors to use
        timeout: int
            Maximal time in seconds after which run is stopped independent of solver settings
        wait: bool=False
            If True, waits until command line call is finished. If False, python codes continues
            immediately (Effectively, if False, '&' is added to the command line string)

        Returns
        -------
        cmd: str
            The generated command line string to resume the computation.
        """
        if self.def_file is None:
            raise ValueError('Definition file is unknown')
        cmd = solve.build_cmd(def_filename=self.def_file.filename, nproc=nproc,
                              ini_filename=self.filename, timeout=timeout)
        p = call_cmd(cmd, wait)
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


# @dataclass
# class FutureCFXResFile:
#     """dummy class if no CFXResFile is stored in CFXResFiles class"""
#     def_file: CFXDefFile
#
#     def _predict_new_res_filename(self):
#         current_number = 0
#         return self.filename.parent.joinpath(f'{str(self.filename.stem)[:-3]}{current_number + 1:03d}.res')

@dataclass
class CFXResFiles:
    filenames: List[Union[str, bytes, os.PathLike, pathlib.Path]]
    def_file: CFXDefFile
    sort: bool = True

    def __post_init__(self):
        if self.sort:
            self.cfx_res_files = [CFXResFile(filename, self.def_file) for filename in sorted(self.filenames)]
        else:
            self.cfx_res_files = [CFXResFile(filename, self.def_file) for filename in self.filenames]

    def __len__(self):
        return len(self.cfx_res_files)

    def __getitem__(self, item):
        return self.cfx_res_files[item]

    @property
    def latest(self):
        if len(self) > 0:
            return self[-1]
        else:
            return None
