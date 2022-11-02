from os import environ

import dotenv
import pathlib
import re
import warnings
from pathlib import Path

from .case import CFXCase


def ansys_version_from_inst_dir(instdir: pathlib.Path) -> str:
    """Get version from installation directory"""
    instdir = pathlib.Path(instdir)
    p = re.compile('v[0-9][0-9][0-9]')

    for part in instdir.parts:
        if p.match(part) is not None:
            return f'{part[1:3]}.{part[-1]}'


class CFXInstallation:

    def __init__(self, env_filename: pathlib.Path = None):
        if env_filename:
            dotenv.load_dotenv(env_filename)

    @property
    def version(self) -> str:
        ansys_version_from_inst_dir(self.pre.stem)

    @property
    def pre(self) -> pathlib.Path:
        return pathlib.Path(environ.get("cfx5pre"))

    @property
    def solve(self) -> pathlib.Path:
        return pathlib.Path(environ.get("cfx5solve"))

    @property
    def cmds(self) -> pathlib.Path:
        return pathlib.Path(environ.get("cfx5cmds"))

    def check(self) -> None:
        """Check if exe exist"""
        for exe_name, exe_path in (('cfx5solve', self.solve),
                                   ('cfx5pre', self.pre),
                                   ('cfx5cmds', self.cmds)):
            if exe_path is None:
                warnings.warn(f'{exe_name} not found in environment variables!')
            else:
                if not Path(exe_path).exists():
                    warnings.warn(f'cfx5solve not found: "{Path(exe_path).resolve()}"')
