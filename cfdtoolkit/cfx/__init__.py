import pathlib
import platform
import re
import warnings
from dataclasses import dataclass
from os import environ
from pathlib import Path

from .case import CFXCase


def ansys_version_from_inst_dir(instdir: pathlib.Path) -> str:
    """Get version from installation directory"""
    instdir = pathlib.Path(instdir)
    p = re.compile('v[0-9][0-9][0-9]')

    for part in instdir.parts:
        if p.match(part) is not None:
            return f'{part[1:3]}.{part[-1]}'


@dataclass
class CFXInstallation:
    """CFX Installation class"""

    inst_dir: pathlib.Path = None
    paths = dict(cfx5pre=environ.get("cfx5pre"),
                 cfx5solve=environ.get("cfx5solve"),
                 cfx5post=environ.get("cfx5post"),
                 cfx5cmds=environ.get("cfx5cmds"))

    def __post_init__(self):
        if self.inst_dir is not None:
            inst_dir = pathlib.Path(self.inst_dir)
            if 'win' in platform.system().lower():
                self.paths = dict(cfx5pre=inst_dir / "cfx5pre.exe",
                                  cfx5solve=inst_dir / "cfx5solve.exe",
                                  cfx5post=inst_dir / "cfx5post.exe",
                                  cfx5cmds=inst_dir / "cfx5cmds.exe")
            else:
                self.paths = dict(cfx5pre=inst_dir / "cfx5pre",
                                  cfx5solve=inst_dir / "cfx5solve",
                                  cfx5post=inst_dir / "cfx5post",
                                  cfx5cmds=inst_dir / "cfx5cmds")

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} "{self.directory}">'

    @property
    def directory(self) -> pathlib.Path:
        """Installation dir"""
        return self.pre.parent

    @property
    def version(self) -> str:
        """Ansys version"""
        ansys_version_from_inst_dir(self.directory)

    @property
    def pre(self) -> pathlib.Path:
        """Path to cfx5pre exe"""
        return self.paths["cfx5pre"]

    @property
    def solve(self) -> pathlib.Path:
        """Path to cfx5solve exe"""
        return self.paths["cfx5solve"]

    @property
    def post(self) -> pathlib.Path:
        """Path to cfx5post exe"""
        return self.paths["cfx5post"]

    @property
    def cmds(self) -> pathlib.Path:
        """Path to cfx5cmds exe"""
        return self.paths["cfx5cmds"]

    def is_valid(self) -> bool:
        """Check if exe exist"""
        for exe_name, exe_path in (('cfx5solve', self.solve),
                                   ('cfx5pre', self.pre),
                                   ('cfx5post', self.post),
                                   ('cfx5cmds', self.cmds)):
            if exe_path is None:
                warnings.warn(f'{exe_name} not found in environment variables!')
                return False
            else:
                if not Path(exe_path).exists():
                    warnings.warn(f'cfx5solve not found: "{Path(exe_path).resolve()}"')
                    return False
        return True
