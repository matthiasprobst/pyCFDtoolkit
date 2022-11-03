import pathlib
from dataclasses import dataclass

from .ccl import CCLFile
from .exe import CFXExe, NPROC_MAX
from .session import cfx2def, importccl
from .utils import change_suffix


@dataclass
class CFXPre(CFXExe):
    """cfx5pre interface class"""

    def _generate_cmd(self, nproc: int, ini_filename: pathlib.Path, timeout_s: int):
        """generate the console command"""
        if not self.filename.exists():
            raise FileNotFoundError(f'Definition file not found: {self.filename.resolve().absolute()}')

        cmd = f'"{self.get_exe("cfx5pre")}" -def "{self.filename}"'

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

    def write_def(self, target_dir: pathlib.Path = None) -> pathlib.Path:
        """Write definition file"""
        if target_dir is not None:
            target_dir = pathlib.Path(target_dir)
            if not target_dir.is_dir():
                raise ValueError(f'Parameter target_dir is not a directory: {target_dir}')
            def_filename = target_dir / f'{self.filename.stem}.def'
        else:
            def_filename = None
        _ = self.get_exe('cfx5pre')  # to set self.exe_filename
        return cfx2def(self.filename, def_filename, ansys_version=self.version)

    @staticmethod
    def from_h5ccl(h5ccl_filename: pathlib.Path) -> "CFXPre":
        """Read from HDF5-ccl file"""
        h5ccl_filename = pathlib.Path(h5ccl_filename)
        if not h5ccl_filename.exists():
            raise FileNotFoundError(f'CCL file not found: {h5ccl_filename}')
        ccl = CCLFile(h5ccl_filename)
        ccl_filename = ccl.to_ccl(ccl_filename=None)
        return CFXPre.from_ccl(ccl_filename)

    @staticmethod
    def from_ccl(ccl_filename: pathlib.Path) -> "CFXPre":
        """Read from ccl file"""
        ccl_filename = pathlib.Path(ccl_filename)
        if not ccl_filename.exists():
            raise FileNotFoundError(f'CCL file not found: {ccl_filename}')
        cfx_filename = importccl(change_suffix(ccl_filename, '.cfx'), ccl_filename)
        return CFXPre(cfx_filename, None)
