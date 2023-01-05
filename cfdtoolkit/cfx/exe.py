"""Core CFX exe interface class"""
import os
import pathlib
import psutil
from dataclasses import dataclass

from .installation import ansys_version_from_inst_dir

NPROC_MAX = psutil.cpu_count(logical=False)


@dataclass
class CFXExe:
    """Core CFX exe interface class"""
    filename: pathlib.Path
    exe_filename: pathlib.Path = None

    def __post_init__(self):
        self.filename = pathlib.Path(self.filename)
        if self.exe_filename:
            self.exe_filename = pathlib.Path(self.exe_filename)

    @property
    def version(self) -> str:
        """Return ansys version"""
        return ansys_version_from_inst_dir(self.exe_filename.parent)

    def get_exe(self, exename) -> pathlib.Path:
        """Return path to exe"""
        if self.exe_filename is None:
            exe = pathlib.Path(os.environ.get(exename))
            if exe is None:
                raise FileNotFoundError(f'{exename} exe not found or set')
            self.exe_filename = pathlib.Path(exe)

        if not self.exe_filename.exists():
            raise FileNotFoundError(f'{exename} exe not found {self.exe_filename.resolve().absolute()}')
        return self.exe_filename
