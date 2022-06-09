import pathlib

from ._logger import logger, _file_handler, _stream_handler

USER_CONFIG_DIR = pathlib.Path.home() / ".config" / __package__
CFX_DOTENV_FILENAME = USER_CONFIG_DIR.joinpath('cfx.env')
SESSIONS_DIR = USER_CONFIG_DIR.joinpath('sessions')


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


def _write_dot_env_file(overwrite=False):
    """creates the .env file for cfx environment variables"""
    if not overwrite and CFX_DOTENV_FILENAME.exists():
        raise FileExistsError('cfx.env file already exists in user directory')

    with open(CFX_DOTENV_FILENAME, 'w') as f:
        f.write('cfx5pre = /opt/dist/ansys_inc/v202/CFX/bin/cfx5pre\n')
        f.write('cfx5solve = /opt/dist/ansys_inc/v202/CFX/bin/cfx5solve\n')
        f.write('cfx5stop = /opt/dist/ansys_inc/v202/CFX/bin/cfx5stop\n')
        f.write('cfx5cmds = /opt/dist/ansys_inc/v202/CFX/bin/cfx5cmds\n')
        f.write('cfx5mondata = /opt/dist/ansys_inc/v202/CFX/bin/cfx5mondata')
