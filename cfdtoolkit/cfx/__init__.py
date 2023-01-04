import pathlib
import platform
import re
import warnings
from os import environ
from pathlib import Path

from .case import CFXCase
from .ccl import CCLFile
from .result import CFXResFile


def ansys_version_from_inst_dir(installation_directory: pathlib.Path) -> str:
    """Get version from installation directory"""
    installation_directory = pathlib.Path(installation_directory)
    p = re.compile('v[0-9][0-9][0-9]')

    for part in installation_directory.parts:
        if p.match(part) is not None:
            return f'{part[1:3]}.{part[-1]}'


class CFXInstallation:
    """CFX Installation class"""

    def __init__(self, installation_directory: pathlib.Path = None,
                 paths=None):

        self.paths = paths
        if self.paths is None:
            self.paths = dict(cfx5pre=environ.get("cfx5pre"),
                              cfx5solve=environ.get("cfx5solve"),
                              cfx5post=environ.get("cfx5post"),
                              cfx5cmds=environ.get("cfx5cmds"))

        if installation_directory is None:
            if pathlib.Path(self.paths['cfx5pre']).exists():
                self.installation_directory = pathlib.Path(self.paths['cfx5pre']).parent
        else:
            self.installation_directory = pathlib.Path(installation_directory)

        if 'win' in platform.system().lower():
            self.paths = dict(cfx5pre=self.installation_directory / "cfx5pre.exe",
                              cfx5solve=self.installation_directory / "cfx5solve.exe",
                              cfx5post=self.installation_directory / "cfx5post.exe",
                              cfx5cmds=self.installation_directory / "cfx5cmds.exe")
        else:
            self.paths = dict(cfx5pre=self.installation_directory / "cfx5pre",
                              cfx5solve=self.installation_directory / "cfx5solve",
                              cfx5post=self.installation_directory / "cfx5post",
                              cfx5cmds=self.installation_directory / "cfx5cmds")

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
        return pathlib.Path(self.paths["cfx5pre"])

    @property
    def solve(self) -> pathlib.Path:
        """Path to cfx5solve exe"""
        return pathlib.Path(self.paths["cfx5solve"])

    @property
    def post(self) -> pathlib.Path:
        """Path to cfx5post exe"""
        return pathlib.Path(self.paths["cfx5post"])

    @property
    def cmds(self) -> pathlib.Path:
        """Path to cfx5cmds exe"""
        return pathlib.Path(self.paths["cfx5cmds"])

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
