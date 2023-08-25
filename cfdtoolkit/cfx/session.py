import logging
import os
import pathlib
import shutil
import subprocess
import tempfile
from typing import Union, Dict

import dotenv

from .utils import change_suffix
from .installation import ansys_version_from_inst_dir
from .. import CFX_DOTENV_FILENAME
from .. import SESSIONS_DIR
from ..typing import PATHLIKE

dotenv.load_dotenv(CFX_DOTENV_FILENAME)

logger = logging.getLogger('cfdtoolkit')
logger.setLevel(logging.DEBUG)

CFX5PRE = pathlib.Path(os.environ.get("cfx5pre"))
ANSYSVERSION = ansys_version_from_inst_dir(CFX5PRE)


def importccl(cfx_filename: PATHLIKE, ccl_filename: Union[PATHLIKE, None] = None,
              ansys_version: str = ANSYSVERSION) -> pathlib.Path:
    """imports a .ccl file into a .cfx file"""
    if ccl_filename is None:
        ccl_filename = change_suffix(cfx_filename, '.ccl')
    cfx_filename = pathlib.Path(cfx_filename)
    if not cfx_filename.exists():
        raise FileExistsError(f'CFX case file (.cfx) not found: {cfx_filename}')
    if not ccl_filename.exists():
        raise FileExistsError(f'CCL file (.ccl) not found: {cfx_filename}')

    logger.debug(f'Importing ccl file into case file: "{ccl_filename} --> {cfx_filename}')

    mtime_before = cfx_filename.stat().st_mtime

    run_session_file(SESSIONS_DIR / 'importccl.pre',
                     {'__cfxfilename__': str(cfx_filename.absolute()),
                      '__cclfilename__': str(ccl_filename.absolute()),
                      '__version__': ansys_version})
    os.utime(cfx_filename.absolute())

    # now check if .cfx file modification time has changed
    if cfx_filename.stat().st_mtime <= mtime_before:
        raise ValueError('It seems that the cfx file has not been touched which was expected. '
                         'Therefore failed importing ccl file')
    return cfx_filename


def cfx2def(cfx_filename: PATHLIKE, def_filename: Union[PATHLIKE, None] = None,
            ansys_version: str = ANSYSVERSION) -> pathlib.Path:
    """Write solver file from cfx case file"""
    cfx_filename = pathlib.Path(cfx_filename)

    if def_filename is None:
        def_filename = cfx_filename.parent.joinpath(f'{cfx_filename.stem}.def')
    else:
        def_filename = pathlib.Path(def_filename)

    logger.debug(f'Running session file cfx2def.pre to create def-file {def_filename} from cfx-file {cfx_filename}.')
    completed_process = run_session_file(SESSIONS_DIR / 'cfx2def.pre',
                                         {'__cfxfilename__': str(cfx_filename.absolute()),
                                          '__deffilename__': str(def_filename.absolute()),
                                          '__version__': ansys_version})
    if not def_filename.exists():
        raise RuntimeError(f'Something went wrong. The def file was not created. Process info: {completed_process}')
    return def_filename


def change_timestep_and_write_def(cfx_filename: PATHLIKE, def_filename: PATHLIKE, timestep: float,
                                  ansys_version: str = ANSYSVERSION):
    """changes timestep in *.cfx fil and writes solver file *.def"""
    run_session_file(SESSIONS_DIR / 'cfx2def.pre',
                     {'__cfxfilename__': str(cfx_filename.absolute()),
                      '__timestep__': str(timestep),
                      '__deffilename__': str(def_filename.absolute()),
                      '__version__': ansys_version})


def change_timestep(cfx_filename: PATHLIKE, timestep: float,
                    ansys_version: str = ANSYSVERSION):
    """changes timestep in *.cfx file. DOES NOT WRITE THE *.DEF FILE!"""
    run_session_file(SESSIONS_DIR / 'change_timestep.pre',
                     {'__cfxfilename__': str(cfx_filename.absolute()),
                      '__timestep__': str(timestep),
                      '__version__': ansys_version})


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
            raise KeyError('"{keyword}" not found in {filename}.'.format(**locals()))

    with open(filename, 'w') as f:
        logger.debug('Changing "{keyword}" to "{new_string}" in {filename}'.format(**locals()))
        s = s.replace(keyword, new_string)
        f.write(s)


def play_session(session_file: PATHLIKE,
                 cfx5pre: Union[PATHLIKE, None] = None) -> subprocess.CompletedProcess:
    """
    Runs cfx5pre session file

    Parameters
    ----------
    cfx5pre : Union[str, bytes, os.PathLike, pathlib.Path], optional
        path to cfx5pre exe.
        Default takes from config file
    """
    if cfx5pre is None:
        _cfx5path = CFX5PRE
    else:
        _cfx5path = pathlib.Path(cfx5pre)

    if not _cfx5path.exists():
        raise FileExistsError(f'Could not find cfx5pre exe here: {_cfx5path}')

    session_file = pathlib.Path(session_file)

    cmd = f'"{_cfx5path}" -batch "{session_file}"'

    completed_process = subprocess.run(cmd, shell=True, capture_output=True)
    logger.debug(f'subprocess info: {completed_process}')
    if completed_process.returncode != 0:
        if 'not connect to any license server' in completed_process.stdout:
            raise ConnectionError(f'I seems that you are not connected to a license server: {completed_process}')
        else:  # unknown error
            raise RuntimeError(f'Subprocess was not successful: {completed_process}')
    return completed_process


def run_session_file(session_filename: Union[str, pathlib.Path],
                     param_keywords: Dict) -> subprocess.CompletedProcess:
    """calls the session file and replaces the key words in param_keywords"""
    if not pathlib.Path(session_filename).exists():
        # try finding it in SESSIONS_DIR:
        session_filename = (SESSIONS_DIR / session_filename).resolve().absolute()
    tmp_session_file = copy_session_file_to_tmp(session_filename)
    for k, v in param_keywords.items():
        replace_in_file(tmp_session_file, k, v)
    return play_session(tmp_session_file)
