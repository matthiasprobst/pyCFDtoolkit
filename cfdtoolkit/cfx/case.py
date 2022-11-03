import dotenv
import logging
import os
import pathlib
from typing import List

from . import pre
from . import solve
from .core import AnalysisType
from .core import CFXFile
from .result import CFXResFile
from .utils import change_suffix
from .. import CFX_DOTENV_FILENAME

logger = logging.getLogger(__package__)
dotenv.load_dotenv(CFX_DOTENV_FILENAME)

CFX5SOLVE = os.environ.get("cfx5solve")


def update_case(func, *args, **kwargs):
    def decorator(_self):
        _self.update()
        func(_self, *args, **kwargs)
        _self.update()

    return decorator


class CFXCase(CFXFile):
    """Class wrapped around the *.cfx case file.

    Case assumtions:
    ----------------
    The case file (.cfx) and the definition file ('.def') have the same stem, e.g.:
    `mycase.cfx` and `mycase.def`.
    The result files (.res) will look like `mycase_001.res` and `maycase_002.res` and so on.
    """

    def __init__(self, filename):
        """
        Avoids error when multiple cfx files are available in
        one folder, e.g. *._frz, *_trn.cfx
        """
        super().__init__(filename)
        if not self.filename.exists():
            raise FileExistsError(f'CFX file does not exist: {self.filename}')
        self.res_files = []
        self.def_filename = None
        self.update()

    @update_case
    def reset(self):
        """Deletes all result files and the definition file, so that only the .cfx file
        remains (or if this does not exist, the def file should remain)"""
        if not self.filename.exists():
            raise FileExistsError('Cannot delete the case because no .cfx file would remain for this case.')
        for r in self.res_files:
            r.unlink()
        if self.def_filename is not None:
            if self.def_filename.exists():
                self.def_filename.unlink()

    def update(self):
        """scan files"""
        self.res_files = [CFXResFile(fname) for fname in sorted(self.working_dir.glob(f'{self.name}*.res'))]
        self.def_filename = change_suffix(self.filename, '.def')

    @property
    def pre(self) -> pre.CFXPre:
        """Return a CFXPre instance of this case file"""
        self.update()
        return pre.CFXPre(self.filename)

    @property
    def solve(self) -> solve.CFXSolve:
        """Return a CFXPre instance of this case file"""
        self.update()
        return solve.CFXSolve(self.def_filename)

    @property
    def res(self) -> List[CFXResFile]:
        """Return list of result files"""
        self.update()
        return self.res_files

    @property
    def name(self):
        """Filename stem"""
        return self.filename.stem

    def __repr__(self):
        return f'<CFXCase name: {self.name}>'

    @update_case
    def info(self) -> None:
        """Print overview of case files"""
        print(f'{"CFX Case":.^20s}')
        print(f' > name: {self.name}')
        print(f' > Working dir: {self.filename.parent}')
        nresfiles = len(self.res_files)
        if nresfiles == 0:
            print(' > No result files available')
        else:
            print(' > Result files:')
            _n = len(str(nresfiles))
            for i, resfile in enumerate(self.res_files):
                print(f'     ({i + 1:{_n}d}/{nresfiles}): {resfile.filename.name} ({resfile.outfile.filename.name})')
        print(f'{"":.^20s}')

    @update_case
    def rename(self, new_name: str) -> None:
        """renames all files of this case to the new name if still available (no conflict with existing files
        in the working direcotry.
        If succesful, it returns a new instance"""
        if new_name.endswith('.cfx'):
            new_name = new_name.rsplit('.cfx')[0]
        new_filename = self.working_dir.joinpath(f'{new_name}.cfx').resolve()
        if not new_filename.parent.exists():
            new_filename.parent.mkdir(parents=True)

        if new_filename == self.filename:
            return

        all_files = list(self.working_dir.glob(f'{self.stem}*'))

        def change_stem(fname, new_stem):
            stem = fname.stem
            name = fname.name
            _new_name = name.replace(stem, new_stem)
            return pathlib.Path(fname.parent.joinpath(_new_name))

        all_new_files = [change_stem(fname, new_name) for fname in all_files]

        for new_fname in all_new_files:
            if new_fname.exists():
                raise FileExistsError(f'Cannot rename because found already such file: {new_fname}')

        for s, t in zip(all_files, all_new_files):
            s.rename(t)

        self.filename = new_filename

    @property
    def analysis_type(self) -> AnalysisType:
        """returns the analysis type"""
        _target_grp = self.ccl.root_group.sub_groups['FLOW: Flow Analysis 1'].sub_groups['ANALYSIS TYPE']
        if 'Steady State' in _target_grp.get_lines()[0]:
            return AnalysisType.STEADYSTATE
        return AnalysisType.TRANSIENT
