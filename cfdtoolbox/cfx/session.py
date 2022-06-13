import logging
import os
import pathlib
import shutil
import tempfile
from typing import Union

import dotenv

from .. import CFX_DOTENV_FILENAME
from .. import SESSIONS_DIR
from .cmd import call_cmd
from ..typing import PATHLIKE
dotenv.load_dotenv(CFX_DOTENV_FILENAME)

logger = logging.getLogger('cfdtoolbox')

CFX5PRE = os.environ.get("cfx5pre")


def cfx2def(cfx_filename: PATHLIKE, def_filename: Union[PATHLIKE, None]=None):
    if def_filename is None:
        def_filename = cfx_filename.parent.joinpath(f'{cfx_filename.stem}.def')

    _orig_session_filename = SESSIONS_DIR.joinpath('cfx2def.pre')
    _tmp_session_filename = copy_session_file_to_tmp(_orig_session_filename)
    replace_in_file(_tmp_session_filename, '__cfxfilename__', str(cfx_filename))
    replace_in_file(_tmp_session_filename, '__deffilename__', str(def_filename))
    play_session(_tmp_session_filename)

def change_timestep_and_write_def(cfx_filename: PATHLIKE, def_filename: PATHLIKE, timestep: float):
    """changes timestep in *.cfx fil and writes solver file *.def"""
    _orig_session_filename = SESSIONS_DIR.joinpath('change_timestep_and_write_def.pre')
    _tmp_session_filename = copy_session_file_to_tmp(_orig_session_filename)
    replace_in_file(_tmp_session_filename, '__cfxfilename__', str(cfx_filename))
    replace_in_file(_tmp_session_filename, '__timestep__', str(timestep))
    replace_in_file(_tmp_session_filename, '__deffilename__', str(def_filename))
    play_session(_tmp_session_filename)

def change_timestep(cfx_filename: PATHLIKE, timestep: float):
    """changes timestep in *.cfx file. DOES NOT WRITE THE *.DEF FILE!"""
    _orig_session_filename = SESSIONS_DIR.joinpath('change_timestep.pre')
    _tmp_session_filename = copy_session_file_to_tmp(_orig_session_filename)
    replace_in_file(_tmp_session_filename, '__cfxfilename__', str(cfx_filename))
    replace_in_file(_tmp_session_filename, '__timestep__', str(timestep))
    play_session(_tmp_session_filename)


def random_tmp_filename(ext=''):
    """Generates a random file path in directory strudaset/.tmp with filename tmp****.hdf where **** are random
    numbers. The file path is returned but the file itself is not created until used.

    Returns
    --------
    random_fpath: `string`
        random file path
    """

    if not ext == '':
        if "." not in ext:
            ext = f'.{ext}'

    tmpdir = pathlib.Path(tempfile.TemporaryDirectory().name)
    if not tmpdir.exists():
        tmpdir.mkdir()
    random_fpath = tmpdir.joinpath(f"tmp{ext}")
    while os.path.isfile(random_fpath):
        random_fpath = tmpdir.joinpath(f"tmp{ext}")

    return random_fpath


def copy_session_file_to_tmp(session_filename: PATHLIKE) -> PATHLIKE:
    """copies `session_filename` to user temp directory where
    it is stored under a random filename"""
    random_fpath = random_tmp_filename(".pre")
    src = session_filename
    dest = random_fpath
    logger.debug(f'Copying {src} to {dest}')
    shutil.copy2(src, dest)
    return random_fpath


def replace_in_file(filename, keyword, new_string):
    """replaces keyword with 'new_string'. If keyword appears
    multiple times, it is replaced multiple times."""
    new_string = str(new_string)

    with open(filename) as f:
        s = f.read()
        if keyword not in s:
            logger.debug('"{keyword}" not found in {filename}.'.format(**locals()))
            return

    with open(filename, 'w') as f:
        logger.debug('Changing "{keyword}" to "{new_string}" in {filename}'.format(**locals()))
        s = s.replace(keyword, new_string)
        f.write(s)


def play_session(session_file: Union[str, bytes, os.PathLike, pathlib.Path],
                 cfx5pre: Union[str, bytes, os.PathLike, pathlib.Path] = None) -> None:
    """
    Runs cfx5pre session file

    Parameters
    ----------
    cfx5pre : Union[str, bytes, os.PathLike, pathlib.Path], optional
        path to cfx5pre exe.
        Default takes from config file
    """
    if cfx5pre is None:
        _cfx5path = pathlib.Path(CFX5PRE)
    else:
        _cfx5path = CFX5PRE

    if not _cfx5path.exists():
        raise FileExistsError(f'Could not find cfx5pre exe here: {_cfx5path}')

    session_file = pathlib.Path(session_file)

    cmd = f"{_cfx5path} -batch {session_file}"
    call_cmd(cmd)
    return cmd
