import dotenv
import pandas as pd
import pathlib
import xarray as xr
from enum import Enum
from numpy.typing import ArrayLike
from typing import Dict
from typing import Union

from . import mon
from .out import extract_out_data, mesh_info_from_file
from .. import AUXDIRNAME
from .. import CFX_DOTENV_FILENAME
from ..typing import PATHLIKE

dotenv.load_dotenv(CFX_DOTENV_FILENAME)


class AnalysisType(Enum):
    STEADYSTATE = 1
    TRANSIENT = 2


class CFXFile:
    """Base wrapper class around a generic Ansys CFX file"""

    def __init__(self, filename: PATHLIKE):
        self.filename = pathlib.Path(filename).resolve()
        self.working_dir = self.filename.parent.resolve()

        if self.filename.suffix == '.res':
            self.aux_dir = self.working_dir.joinpath(AUXDIRNAME)
        else:
            self.aux_dir = self.working_dir.joinpath(AUXDIRNAME)
        if not self.aux_dir.exists():
            self.aux_dir.mkdir(parents=True)


class CFXDir(CFXFile):
    """The .dir directory when a case is running"""

    @property
    def is_crashed(self):
        raise NotImplementedError()
        return False


class MonitorObject:

    def __init__(self, expression_value: str, coord_frame: str = 'Coord 0'):
        """
        TODO: expression and coord frame could also be objects
        """
        self.coord_frame = coord_frame
        self.expression_value = expression_value


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
    print(f'Unable to process {input_str}')


class MonitorDataFrame(pd.DataFrame):

    @property
    def user_points(self) -> Dict:
        user_point_list = [_str_to_UserPoint(n, self[n]) for n in self.columns if n.find('USER POINT') == 0]
        return {up.attrs['name']: up for up in user_point_list if up is not None}


class MonitorData(CFXFile):

    def __init__(self, filename):
        super(MonitorData, self).__init__(filename)
        _data = pd.DataFrame()
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
        return self.data.user_points


class OutFile:
    """.out-file interface class"""

    def __init__(self, filename):
        self.filename = filename

    def __repr__(self):
        return f'<OutFile {self.filename}>'

    @property
    def name(self):
        """Filename stem"""
        return self.filename.stem

    @property
    def data(self) -> pd.DataFrame:
        """Return data as data frame"""
        if not self.filename.exists():
            raise FileNotFoundError(f'File not found: {self.filename}')
        return extract_out_data(self.filename)

    def get_mesh_info(self) -> pd.DataFrame:
        """Return mesh info as pd.DataFrame"""
        if not self.filename.exists():
            raise FileNotFoundError(f'File not found: {self.filename}')
        return mesh_info_from_file(self.filename)
