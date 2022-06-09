import logging
import os
import pathlib
import shutil
from typing import Union

import dotenv
import h5py
import numpy as np
from x2hdf.utils import random_tmp_filename

from .. import CFX_DOTENV_FILENAME, SESSIONS_DIR

dotenv.load_dotenv(CFX_DOTENV_FILENAME)

logger = logging.getLogger('cfdtoolbox')

CFX5PRE = os.environ.get("cfx5pre")
CFX5CMDS = os.environ.get("cfx5cmds")


class CCLFile:
    """
    Reads in a ANSYS CFX *.ccl file
    and can write it to *.hdf

    Example
    ------
    c = CCL_File(ccl_filename)
    c.write_to_hdf('ccltest.hdf', overwrite=True)

    or
    hdf_filepath = CCL_File(ccl_filename).write_to_hdf('ccltest.hdf', overwrite=True)
    """

    def __init__(self, filename: pathlib.Path, intendation_step: int = 2):
        self.filename = filename
        self.lines = self._remove_linebreaks()
        self.indentation = self._get_indentation()
        self.root_group = CCLGroup(0, -1, indentation_length=self.indentation[0][1],
                                   intendation_step=intendation_step,
                                   all_lines=self.lines,
                                   all_indentation=self.indentation, name='root', verbose=False)

    def write_to_hdf(self, hdf_filename, overwrite=True):
        if os.path.isfile(hdf_filename):
            mode = 'r+'
        else:
            mode = 'w'
        with h5py.File(hdf_filename, mode) as h5:
            self.root_group.create_h5_group(h5['/'], root_group=True, overwrite=overwrite)

        return hdf_filename

    def _remove_linebreaks(self):
        with open(self.filename, 'r') as f:
            lines = f.readlines()
        single_lines = []

        append_line = False
        for line in lines:
            _line = line.strip('\n')
            if _line != '':
                if _line[0] != '#':
                    if append_line:
                        if _line[-1] == '\\':
                            single_lines[-1] += _line[:-1]
                        else:
                            append_line = False
                            single_lines[-1] += _line
                    else:
                        if _line[-1] == '\\':
                            if append_line:
                                single_lines[-1] += _line[:-1]
                            else:
                                single_lines.append(_line[:-1])
                            append_line = True
                        else:
                            append_line = False
                            single_lines.append(_line)
        return single_lines

    def _get_indentation(self):
        indentation = []
        for i, line in enumerate(self.lines):
            l0 = len(line)
            l1 = len(line.strip(' '))
            indentation.append((i, l0 - l1))
        # indentation_n = np.asarray([i[1] for i in indentation])
        # indentation_n
        # unique_indentation = np.unique(indentation_n)
        return indentation


class CCLGroup:

    def __init__(self, grp_line, end_line, indentation_length,
                 intendation_step, all_lines,
                 all_indentation, name=None, verbose=False):

        self.all_lines = all_lines
        self.all_indentation = all_indentation

        self.grp_line = grp_line
        if end_line == -1:
            self.end_line = len(self.all_lines)
        else:
            self.end_line = end_line

        if name is None:
            _name = self.all_lines[self.grp_line].strip()
            if _name[-1] == ':':
                self.name = _name[:-1]
            else:
                self.name = _name
        else:
            self.name = name

        self.indentation_length = indentation_length
        self.intendation_step = intendation_step
        self.verbose = verbose

        self.sub_groups = {}
        self.find_subgroup()

    def __repr__(self):
        return self.name

    def get_lines(self):
        grp_lines = self.all_lines[self.grp_line + 1:self.end_line]
        return grp_lines

    def find_subgroup(self):
        if self.verbose:
            logger.debug(f'searching at indentation level '
                         f'{self.indentation_length} within '
                         f'{self.grp_line + 1} and {self.end_line}')

        found = []
        for i in self.all_indentation:
            if self.grp_line <= i[0] < self.end_line:
                if i[1] == self.indentation_length:
                    # append line number indent and
                    found.append((i[0], i[1] - 1))
                    # print(i)

        afound = np.asarray([f[0] for f in found])
        if len(afound) > 1:
            for (a, b) in zip(found[0:], found[1:]):
                if a[0] + 1 != b[0]:  # it's a group!
                    _ccl_grp = CCLGroup(a[0], b[0], indentation_length=self.indentation_length + self.intendation_step,
                                        intendation_step=2, all_lines=self.all_lines,
                                        all_indentation=self.all_indentation)
                    self.sub_groups[_ccl_grp.name] = _ccl_grp

    def create_h5_group(self, h5grp, root_group=False, overwrite=False):
        # if skip_root=True the root group is written '/' rather
        # than to what the group name is

        if root_group:
            g = h5grp
        else:
            if self.name in h5grp:
                if overwrite:
                    del h5grp[self.name]
                else:
                    raise ValueError('Group already exists and overwrite is set to False!')
            logger.debug(f'Creating group with name {self.name} at level: {h5grp.name}')
            g = h5grp.create_group(self.name)

        grp_lines = self.get_lines()

        grp_ind_spaces = ' ' * self.indentation_length

        # is set to false if first line in group is not an attribute of this group (no line with "=")
        grp_values_flag = True
        for line in grp_lines:
            if line[0:self.indentation_length] == grp_ind_spaces:
                if grp_values_flag:
                    try:
                        name, value = line.split('=')
                        g.attrs[name.strip()] = value.strip()
                    except:
                        grp_values_flag = False

        for subg in self.sub_groups:
            logger.debug(subg.name)
            subg.create_h5_group(g, overwrite=overwrite)


def generate(input_file: Union[str, bytes, os.PathLike, pathlib.Path], ccl_filename: pathlib.Path = None,
             cfx5pre: pathlib.Path = None, overwrite: bool = True):
    """
    Converts a cfx or def file into a ccl file.
    If no `ccl_filename` is provided the input filename is
    taken and extension is changed accordingly to *.ccl

    Parameters
    ----------
    input_file : `Path`
        *.res or *.cfx file
    ccl_filename: `Path`
        Where to write ccl file. Default changes extension of input to "ccl"
    cfx5pre: `Path`
        Path to exe. Default takes path from config
    overwrite: bool
        Whether to overwrite an existing ccl file

    Returns
    -------
    ccl_filename : `Path`
        Path to generated ccl file
    """
    if not isinstance(input_file, pathlib.Path):
        input_file = pathlib.Path(input_file)

    if input_file.suffix not in ('.cfx', '.res', '.def'):
        raise ValueError('Please provide a ANSYS CFX file.')

    if ccl_filename is None:
        ccl_filename = pathlib.Path.joinpath(input_file.parent, f'{input_file.stem}.ccl')
    logger.debug(f'*.ccl input_file: {ccl_filename}')

    if input_file in ('cfx', '.res'):
        if cfx5pre is None:
            cfx5pre = CFX5PRE
        return generate_from_res_or_cfx(input_file, ccl_filename,
                                        cfx5pre=cfx5pre)
    return generate_from_def(input_file, ccl_filename, overwrite)


def _copy_session_file_to_tmp(session_filename: Union[str, bytes, os.PathLike, pathlib.Path]) -> str:
    """copies `session_filename` to user temp directory where
    it is stored under a random filename"""
    random_fpath = random_tmp_filename(".pre")
    src = session_filename
    dest = random_fpath
    logger.debug(f'Copying {src} to {dest}')
    shutil.copy(src, dest)
    return random_fpath


def generate_from_res_or_cfx(res_cfx_filename: Union[str, bytes, os.PathLike, pathlib.Path],
                             ccl_filename: pathlib.Path, cfx5pre:str, overwrite=True) -> pathlib.Path:
    if overwrite and ccl_filename.exists():
        ccl_filename.unlink()
    if res_cfx_filename.suffix == '.cfx':
        session_filename = os.path.join(SESSIONS_DIR, 'cfx2ccl.pre')
    elif res_cfx_filename.suffix == '.res':
        session_filename = os.path.join(SESSIONS_DIR, 'res2ccl.pre')
    else:
        raise ValueError(f'Could not determine "session_filename"')

    random_fpath = _copy_session_file_to_tmp(session_filename)
    _capital_ext = res_cfx_filename.suffix[1:].capitalize()
    _replace_in_file(random_fpath, f'__{_capital_ext}_FILE__', res_cfx_filename)

    logger.debug(f'Playing CFX session file: {random_fpath}')
    _play_session(random_fpath, cfx5pre)
    os.remove(random_fpath)
    return ccl_filename


def _replace_in_file(filename, keyword, new_string):
    """replaces keyword with 'new_string'. If keyword appears
    multiple times, it is replaced multiple times."""
    new_string = str(new_string)

    with open(filename) as f:
        s = f.read()
        if keyword not in s:
            logger.debug('"{keyword}" not found in {filename}.'.format(**locals()))
            return

    with open(filename, 'w') as f:
        logger.debug('Changing "{keyword}" to "{new_string}" in {filename}'.format(**locals()))
        s = s.replace(keyword, new_string)
        f.write(s)


def generate_from_def(def_filename: Union[str, bytes, os.PathLike, pathlib.Path],
                      ccl_filename: Union[str, bytes, os.PathLike, pathlib.Path],
                      overwrite: bool = True) -> pathlib.Path:
    """generates a ccl file from a def file"""
    if ccl_filename.exists() and overwrite:
        ccl_filename.unlink()
    print(ccl_filename.exists())
    cmd = f'{CFX5CMDS} -read -def "{def_filename}" -text "{ccl_filename}"'
    os.system(cmd)
    if not ccl_filename.exists():
        raise RuntimeError(f'Failed running bash script "{cmd}"')
    return ccl_filename


def _play_session(session_file: Union[str, bytes, os.PathLike, pathlib.Path],
                  cfx5pre: Union[str, bytes, os.PathLike, pathlib.Path] = None) -> None:
    """
    Runs cfx5pre

    Parameters
    ----------
    cfx5pre : Union[str, bytes, os.PathLike, pathlib.Path], optional
        path to cfx5pre exe.
        Default takes from config file
    """
    if cfx5pre is None:
        _cfx5path = pathlib.Path(CFX5PRE)
    else:
        _cfx5path = CFX5PRE

    if not _cfx5path.exists():
        raise FileExistsError(f'Could not find cfx5pre exe here: {_cfx5path}')

    session_file = pathlib.Path(session_file)

    os.system(f"{_cfx5path} -batch {session_file}")
