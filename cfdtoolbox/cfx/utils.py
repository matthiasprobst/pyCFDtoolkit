import pathlib
from typing import Tuple

from ..typing import PATHLIKE


def _generate_mtime_filename(filename, target_dir) -> pathlib.Path:
    return pathlib.Path(target_dir).joinpath(f'{pathlib.Path(filename).stem}.st_mtime')


def write_mtime(filename, target_dir) -> Tuple[PATHLIKE, float]:
    fname = pathlib.Path(filename)
    target_filename = _generate_mtime_filename(filename, target_dir)
    with open(target_filename, 'w') as f:
        st_mtime = fname.stat().st_mtime
        f.write(f'{st_mtime}')
    return target_filename, st_mtime
