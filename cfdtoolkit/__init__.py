import pathlib
import platform

from ._logger import logger, _file_handler, _stream_handler

AUXDIRNAME = '.cfdtoolkit'


USER_CONFIG_DIR = pathlib.Path.home() / ".config" / __package__

if platform.system() == 'Windows':
    CFX_DOTENV_FILENAME = USER_CONFIG_DIR.joinpath('cfx_win.env')
else:
    CFX_DOTENV_FILENAME = USER_CONFIG_DIR.joinpath('cfx_linux.env')
SESSIONS_DIR = pathlib.Path(__file__).parent.joinpath('cfx/session_files')

if not SESSIONS_DIR.exists():
    raise NotADirectoryError(f'Ansys CFX session folder not found: {SESSIONS_DIR}')


def set_loglevel(level):
    """sets the logging level"""
    logger.setLevel(level.upper())
    _file_handler.setLevel(level.upper())
    _stream_handler.setLevel(level.upper())


def _make_user_config_dir():
    """creates the tmp directory for cfx session files"""
    if not USER_CONFIG_DIR.exists():
        USER_CONFIG_DIR.mkdir()


def _make_sessions_dir():
    """creates the tmp directory for cfx session files"""
    if not SESSIONS_DIR.exists():
        SESSIONS_DIR.mkdir()


def _write_dot_env_file(inst_dir, overwrite=False):
    """creates the .env file for cfx environment variables"""
    if not overwrite and CFX_DOTENV_FILENAME.exists():
        raise FileExistsError('cfx.env file already exists in user directory')

    with open(CFX_DOTENV_FILENAME, 'w') as f:
        f.write(f'cfx5instdir = {inst_dir}\n')  # C:\Program Files\ANSYS Inc\v202\CFX\bin
        f.write(f'cfx5pre = {inst_dir}/bincfx5pre\n')
        f.write(f'cfx5solve = {inst_dir}/bincfx5solve\n')
        f.write(f'cfx5stop = {inst_dir}/bincfx5stop\n')
        f.write(f'cfx5cmds = {inst_dir}/bincfx5cmds\n')
        f.write(f'cfx5mondata = {inst_dir}/bincfx5mondata')
