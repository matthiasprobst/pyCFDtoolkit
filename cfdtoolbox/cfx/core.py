import os
import pathlib
import time
from dataclasses import dataclass
from enum import Enum
from typing import Union, Tuple, List

import dotenv
import pandas as pd
import xarray as xr
from numpy.typing import ArrayLike

from . import mon
from . import solve
from .ccl import CCLFile
from .ccl import generate as generate_ccl
from .out_utils import extract_out_data, mesh_info_from_file
from .. import CFX_DOTENV_FILENAME

dotenv.load_dotenv(CFX_DOTENV_FILENAME)
AUXDIRNAME = '.pycfdtoolbox'

CFX5SOLVE = os.environ.get("cfx5solve")


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


def touch_stp(directory):
    with open(pathlib.Path(directory).joinpath('stp'), 'w') as _:
        pass


class AnalysisType(Enum):
    STEADYSTATE = 1
    TRANSIENT = 2


def _generate_mtime_filename(filename, target_dir) -> pathlib.Path:
    return pathlib.Path(target_dir).joinpath(f'{pathlib.Path(filename).stem}.st_mtime')


def write_mtime(filename, target_dir) -> Tuple[pathlib.Path, float]:
    fname = pathlib.Path(filename)
    target_filename = _generate_mtime_filename(filename, target_dir)
    with open(target_filename, 'w') as f:
        st_mtime = fname.stat().st_mtime
        f.write(f'{st_mtime}')
    return target_filename, st_mtime


def read_mtime(filename):
    with open(filename, 'r') as f:
        return int(f.readlines()[0])


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
        self.working_dir = self.filename.parent
        # self.aux_dir = self.working_dir.joinpath(AUXDIRNAME)
        if self.filename.suffix == '.res':
            self.aux_dir = self.working_dir.joinpath(f'.{self.filename.stem.rsplit("_", 1)[0]}.cfdtoolbox')
        else:
            self.aux_dir = self.working_dir.joinpath(f'.{self.filename.stem}.cfdtoolbox')
        if not self.aux_dir.exists():
            self.aux_dir.mkdir()


class CFXDir(CFXFile):
    """The .dir directory when a case is running"""

    @property
    def is_crasehd(self):
        return False


class MonitorUserPoint(xr.DataArray):
    __slots__ = ()


class MonitorUserExpression(xr.DataArray):
    __slots__ = ()


def _str_to_UserPoint(input_str: str, data: ArrayLike) -> Union[MonitorUserPoint, MonitorUserExpression]:
    """extracts info from a user point string and returns a MonitorUserPoint class"""
    _split = input_str.split(',')
    if len(_split) == 2:
        name, _units = _split[1].split(' [')
        return MonitorUserExpression(data=data,
                                     dims=('iteration',),
                                     attrs={'name': name.split(' [')[0], 'long_name': name})
    if len(_split) == 7:
        name = _split[1]
        domain = _split[2]
        try:
            x = float(_split[3].split('=')[1].strip('"'))
            y = float(_split[4].split('=')[1].strip('"'))
            z = float(_split[5].split('=')[1].strip('"'))
        except Exception as e:
            print(f'Error during user point coordinate extraction of {input_str}: {e}')
        variable_name = _split[6]
        return MonitorUserPoint(data=data,
                                dims=('iteration',),
                                attrs=dict(name=name, domain=domain, long_name=variable_name,
                                           ),
                                coords={'x': x, 'y': y, 'z': z})


class MonitorDataFrame(pd.DataFrame):

    def user_points(self):
        user_point_list = [_str_to_UserPoint(n, self[n]) for n in self.columns if n.find('USER POINT') == 0]
        return {up.attrs['name']: up for up in user_point_list}


@dataclass
class MonitorData(CFXFile):
    _data: pd.DataFrame = pd.DataFrame()

    def __post_init__(self):
        super(MonitorData, self).__post_init__()
        _out_filename = f'{self.filename.stem}.monitor'
        self._out_filename = self.aux_dir.joinpath(_out_filename)
        self._data = pd.DataFrame()

    def __getitem__(self, item):
        return self._data[item]

    @property
    def is_out_of_date(self):
        if self._out_filename.exists():
            return self._out_filename.stat().st_mtime < self.filename.stat().st_mtime
        return True

    @property
    def names(self):
        return self.data.columns

    def _write_file(self) -> None:
        self._out_filename = mon.get_monitor_data_by_category(self.filename, out=self._out_filename)

    def _read_data(self) -> None:
        if not self._out_filename.exists() or self.is_out_of_date:
            self._write_file()
        self._data = pd.read_csv(self._out_filename)

    @property
    def data(self) -> MonitorDataFrame:
        if not self._out_filename.exists():
            self._write_file()
            self._data = pd.read_csv(self._out_filename)
            return MonitorDataFrame(self._data)
        else:
            if self._data.size == 0:
                self._read_data()
            return MonitorDataFrame(self._data)

    @property
    def user_points(self):
        return self.data.user_points()


@dataclass
class OutFile(MonitorData):

    def __post_init__(self):
        super().__post_init__()
        _out_filename = f'{self.filename.stem}.outdata'
        self._out_filename = self.aux_dir.joinpath(_out_filename)

    def _estimate_out_filename(self):
        return self.filename.parent.joinpath(f'{self.filename.stem}.out')

    def _write_file(self) -> None:
        if not self._estimate_out_filename().exists():
            raise FileExistsError(f'*.out file note found. Guessed it here: "{self._estimate_out_filename()}"')
        self._data = extract_out_data(self._estimate_out_filename())
        self._data.to_csv(self._out_filename)

    def get_mesh_info(self) -> pd.DataFrame:
        if self._out_filename.exist():
            return mesh_info_from_file(self.filename)
        return pd.DataFrame()


@dataclass
class CFXDefFile(CFXFile):
    """Class wrapped around the *.def case file"""

    ccl: CCLFile = None

    def __post_init__(self):
        super().__post_init__()
        self.write_ccl_file(overwrite=True)

    def _generate_ccl_filename(self):
        return self.aux_dir.joinpath(f'{self.stem}.ccl')

    def write_ccl_file(self, ccl_filename=None, overwrite:bool=True) -> pathlib.Path:
        """writes a ccl file from a *.cfx file"""
        if ccl_filename is None:
            ccl_filename = self._generate_ccl_filename()
        self.ccl = CCLFile(generate_ccl(self.filename, ccl_filename, None, overwrite=overwrite))
        return self.ccl.filename


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
                              ini_filename=self.filename, timeout=timeout, wait=wait)
        os.system(cmd)
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

    def stop(self, wait=True, timeout=600):
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
            # return FutureCFXResFile(self.def_file)
