import pathlib
import re
from os import utime
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


def change_suffix(filename: PATHLIKE, new_suffix: str) -> pathlib.Path:
    """Reads a filename (must not exist) and exchanges the suffix with the new given one"""
    filename = pathlib.Path(filename)
    if new_suffix[0] != '.':
        new_suffix = '.' + new_suffix
    return filename.parent.joinpath(f'{filename.stem}{new_suffix}')


def touch_stp(directory, times=None):
    with open(f'{directory}/stp', 'a'):
        utime('stp', times)


def capitalize_phrase(phrase: str) -> str:
    """Returns the phrase where every first letter of a word is capitalized"""
    return ' '.join([s.capitalize() for s in phrase.split(' ')])


def ansys_version_from_inst_dir(instdir: pathlib.Path) -> str:
    instdir = pathlib.Path(instdir)
    p = re.compile('v[0-9][0-9][0-9]')

    for part in instdir.parts:
        if p.match(part) is not None:
            return part
