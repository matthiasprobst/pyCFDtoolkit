import logging
import pathlib

from . import ccl
from . import session
from .core import CFXFile

logger = logging.getLogger(__package__)


class CFXDefFile(CFXFile):
    """Class wrapped around the *.def case file"""

    def __init__(self, filename):
        super().__init__(filename)
        if not self.filename.exists():
            logger.info('No .def file exists for the case. Creating one...')
            self.filename = session.cfx2def(self.get_cfx_filename(), self.filename)

        # check again
        if not self.filename.exists():
            raise RuntimeError(f'Apparently there is still no definition file. cfx2def must have failed...'
                               f'Is your license available? Or the cfx file may be corrupted.')

        # now, the def file exists for sure. but is it up-to-date?
        if self.filename.stat().st_mtime < self.get_cfx_filename().stat().st_mtime:
            logger.info(f'The .def file is out of date ({self.filename.stat().st_mtime} < '
                        f'{self.get_cfx_filename().stat().st_mtime}. Creating a new one...')
            self.filename = session.cfx2def(self.get_cfx_filename(), self.filename)

    def get_cfx_filename(self):
        """Generates the .cfx filename from the .def filename"""
        guessed_filename = self.working_dir.joinpath(f'{self.filename.stem}.cfx')
        if not guessed_filename.exists():
            raise FileNotFoundError(f'Predicted a .cfx filename from the .def filename but such a '
                                    f'.cfx fileame does not exist: {guessed_filename}. Make sure that '
                                    f'all ansys-cfx file are in the same working directory')
        return guessed_filename

    def _generate_ccl_filename(self):
        return self.aux_dir.joinpath(f'{self.stem}.ccl')

    def generate_ccl(self, ccl_filename=None, overwrite: bool = True) -> pathlib.Path:
        """writes a ccl file from a *.def file"""
        if ccl_filename is None:
            ccl_filename = self._generate_ccl_filename()
        if not self.filename.exists():
            # generate the ccl file from the cfx file:
            ccl_filename = ccl.generate(self.get_cfx_filename(), ccl_filename, None, overwrite=overwrite)
        else:
            # generate the ccl file from the def file:
            ccl_filename = ccl.generate(self.filename, ccl_filename, None, overwrite=overwrite)

        ccltext = ccl.CCLTextFile(ccl_filename)
        ccl_hdf_filename = ccltext.to_hdf()
        return ccl.CCLFile(ccl_hdf_filename, self.aux_dir)

    # def update(self):
    #     """write .def from .cfx"""
    #     self.filename = session.cfx2def(self.get_cfx_filename(), self.filename)
