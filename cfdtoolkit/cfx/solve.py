import pathlib
import subprocess
from dataclasses import dataclass

from .ccl import _generate_from_def
from .exe import CFXExe, NPROC_MAX
from .utils import change_suffix


@dataclass
class CFXSolve(CFXExe):
    """cfx5solve interface class"""

    def _generate_cmd(self, nproc: int, ini_filename: pathlib.Path, timeout_s: int):
        """generate the console command"""
        if not self.filename.exists():
            raise FileNotFoundError(f'Definition file not found: {self.filename.resolve().absolute()}')

        exe = self.get_exe("cfx5solve")
        cmd = f'"{exe}" -def "{self.filename}"'

        if ini_filename is not None:
            cmd += f' -ini "{ini_filename}"'

        cmd += f' -chdir "{self.filename.parent}"'

        if nproc > 1:
            if nproc > NPROC_MAX:
                raise ValueError(f'The selected number of processors ({nproc}) must '
                                 f'not exceed the number of physical cores ({NPROC_MAX}).')
            cmd += f' -par-local -partition {int(nproc)} -batch'

        if timeout_s is not None:
            if timeout_s <= 0:
                raise ValueError(f'Invalid value for timeout: {timeout_s}')
            cmd += f' -maxet \"{int(timeout_s)} [s]\"'  # e.g. maxet='10 [min]'
        return cmd

    def run(self, nproc: int, ini_filename: pathlib.Path = None, timeout_s: int = None, **kwargs):
        """Run the solver"""
        cmd = self._generate_cmd(nproc, ini_filename, timeout_s=timeout_s)
        if kwargs.get('verbose', False):
            print(cmd)
        return subprocess.run(cmd, shell=True)

    def write_ccl(self, target_dir: pathlib.Path = None,
                  overwrite: bool = True) -> pathlib.Path:
        """write ccl file from .def-file"""
        if not self.filename.exists():
            raise FileNotFoundError(f'Definition file not found: "{self.filename}".')

        if target_dir is not None:
            target_dir = pathlib.Path(target_dir)
            if not target_dir.is_dir():
                raise ValueError(f'Parameter target_dir is not a directory: {target_dir}')
            ccl_filename = target_dir / f'{self.filename.stem}.ccl'
        else:
            ccl_filename = change_suffix(self.filename, '.ccl')
        return _generate_from_def(def_filename=self.filename,
                                  ccl_filename=ccl_filename,
                                  overwrite=overwrite)
