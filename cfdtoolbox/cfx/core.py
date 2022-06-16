import os
import pathlib
from dataclasses import dataclass
from enum import Enum
from typing import Union

import dotenv
import pandas as pd
import xarray as xr
from numpy.typing import ArrayLike

from . import mon
from .out import extract_out_data, mesh_info_from_file
from .. import CFX_DOTENV_FILENAME

dotenv.load_dotenv(CFX_DOTENV_FILENAME)


class AnalysisType(Enum):
    STEADYSTATE = 1
    TRANSIENT = 2


@dataclass
class CFXFile:
    """Base wrapper class around a generic Ansys CFX file"""
    filename: Union[str, bytes, os.PathLike, pathlib.Path]

    @property
    def stem(self):
        return self.filename.stem

    @property
    def parent(self):
        return self.filename.parent

    def __post_init__(self):
        self.filename = pathlib.Path(self.filename).resolve()
        self.working_dir = self.filename.parent.resolve()

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
