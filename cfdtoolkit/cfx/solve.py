import pathlib
import subprocess
import warnings
from dataclasses import dataclass
from typing import Union

from . import result as res
from .ccl import _generate_from_def, CCLFile
from .exe import CFXExe, NPROC_MAX
from .utils import change_suffix


@dataclass
class CFXSolve(CFXExe):
    """cfx5solve interface class"""

    def _generate_cmd(self, nproc: int, ini_filename: pathlib.Path, timeout_s: int,
                      discard_run_history: bool, max_nproc_check: bool=True):
        """generate the console command"""
        if not self.filename.exists():
            raise FileNotFoundError(f'Definition file not found: {self.filename.resolve().absolute()}')

        exe = self.get_exe("cfx5solve")
        cmd = f'"{exe}" -def "{self.filename}"'

        if ini_filename is not None:
            if discard_run_history:
                cmd += f' -ini-file "{ini_filename}"'
            else:
                cmd += f' -ini "{ini_filename}"'

        cmd += f' -chdir "{self.filename.parent}"'

        if nproc > 1:
            if nproc > NPROC_MAX and max_nproc_check:
                warnings.warn(f'The selected number of processors ({nproc}) must '
                              f'not exceed the number of physical cores ({NPROC_MAX}). '
                              f'It is adjusted to {NPROC_MAX}',
                              UserWarning)
                nproc = NPROC_MAX
            cmd += f' -par-local -partition {int(nproc)} -batch'

        if timeout_s is not None:
            if timeout_s <= 0:
                raise ValueError(f'Invalid value for timeout: {timeout_s}')
            cmd += f' -maxet \"{int(timeout_s)} [s]\"'  # e.g. maxet='10 [min]'
        return cmd

    def run(self, nproc: Union[int, str],
            ini_filename: Union[pathlib.Path, res.CFXResFile] = None,
            timeout_s: int = None,
            discard_run_history: bool = False,
            **kwargs):
        """Run the solver"""
        max_nproc_check = kwargs.pop('max_nproc_check', True)
        if isinstance(nproc, str):
            if nproc == 'max':
                nproc = NPROC_MAX
            else:
                raise ValueError(f'Cannot interpret string value of "nproc": {nproc}')
        if ini_filename is None:
            existing_res_files = list(self.filename.parent.glob(f'{self.filename.stem}*.res'))
            if len(existing_res_files) > 0:
                raise ValueError('There are result files for this case but you decided to '
                                 'run without an initial solution. '
                                 'Consider resetting the case by deleting all res files of '
                                 'the case. You may pass the parameter.')
        if isinstance(ini_filename, res.CFXResFile):
            ini_filename = ini_filename.filename

        cmd = self._generate_cmd(nproc, ini_filename,
                                 timeout_s=timeout_s,
                                 discard_run_history=discard_run_history,
                                 max_nproc_check=max_nproc_check)
        if kwargs.get('verbose', False):
            print(cmd)
        return subprocess.run(cmd, shell=True)

    def write_ccl(self,
                  target_dir: pathlib.Path = None,
                  overwrite: bool = True) -> CCLFile:
        """write ccl file from .def-file"""
        if not self.filename.exists():
            raise FileNotFoundError(f'Definition file not found: "{self.filename}".')

        if target_dir is not None:
            target_dir = pathlib.Path(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
            if not target_dir.is_dir():
                raise ValueError(f'Parameter target_dir is not a directory: {target_dir}')
            ccl_filename = target_dir / f'{self.filename.stem}.ccl'
        else:
            ccl_filename = change_suffix(self.filename, '.ccl')
        return CCLFile(_generate_from_def(def_filename=self.filename,
                                          ccl_filename=ccl_filename,
                                          overwrite=overwrite))
