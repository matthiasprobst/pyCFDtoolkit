import logging
import os
import pathlib
import shutil
from dataclasses import dataclass
from typing import Union, List

import dotenv
import h5py
import numpy as np

from . import session
from .boundary_conditions.inlet import InletBoundaryCondition
from .cmd import call_cmd
from .. import CFX_DOTENV_FILENAME, SESSIONS_DIR
from ..typing import PATHLIKE

dotenv.load_dotenv(CFX_DOTENV_FILENAME)

logger = logging.getLogger('cfdtoolbox')

CFX5PRE = os.environ.get("cfx5pre")
CFX5CMDS = os.environ.get("cfx5cmds")


@dataclass
class CCLDataField:
    filename: PATHLIKE
    line: int
    name: str
    value: str

    def set(self, new_value) -> None:
        """updates the value in the CCL file"""
        if not self.value == new_value:
            self.value = new_value
            bak_filename = shutil.copy(self.filename, f'{self.filename}.bak')
            shutil.copy(self.filename, bak_filename)
            with open(self.filename, 'r') as f:
                lines = f.readlines()
                target_line = lines[self.line]
            intendation_count = target_line.split(self.name)[0]
            lines[self.line] = f'{intendation_count}{self.name} = {new_value}\n'
            with open(self.filename, 'w') as f:
                f.writelines(lines)


class CCLGroup:

    def __init__(self, filename, grp_line, end_line, indentation_length,
                 intendation_step, all_lines,
                 all_indentation, name=None, verbose=False):
        self.filename = filename

        self.all_lines = all_lines
        self.all_indentation = all_indentation

        self.grp_line = grp_line
        if end_line == -1:
            self.end_line = len(self.all_lines)
        else:
            self.end_line = end_line

        self.group_type = None
        if name is None:
            _name = self.all_lines[self.grp_line].strip()
            if _name[-1] == ':':
                self.name = _name[:-1]
            else:
                self.name = _name
            self.group_type = self.name.split(':', 1)[0]
        else:
            self.name = name

        self.indentation_length = indentation_length
        self.intendation_step = intendation_step
        self.verbose = verbose

        self.sub_groups = {}
        self.find_subgroup()

    def __repr__(self):
        return self.name

    def __getitem__(self, item):
        return self.sub_groups[item]

    def keys(self):
        return self.sub_groups.keys()

    def get_lines(self):
        grp_lines = self.all_lines[self.grp_line + 1:self.end_line]
        return grp_lines

    def _lines_to_data(self, lines):
        data = {}
        for iline, line in enumerate(lines):
            linedata = line.strip().split('=')
            if len(linedata) > 1:
                name = linedata[0].strip()
                value = linedata[1].strip()
                data[linedata[0].strip()] = CCLDataField(self.filename, self.grp_line + 1 + iline, name, value)
            else:
                break  # all options are at top of a group. once there is a line without "=" the next group begins...
        return data

    @property
    def data(self):
        return self._lines_to_data(self.get_lines())

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
                    _ccl_grp = CCLGroup(self.filename, a[0], b[0],
                                        indentation_length=self.indentation_length + self.intendation_step,
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

        for name, subg in self.sub_groups.items():
            logger.debug(name)
            subg.create_h5_group(g, overwrite=overwrite)


class SpecialCCLGroup(CCLGroup):

    def __init__(self, *args, **kwargs):
        if isinstance(args[0], CCLGroup):
            self.filename = args[0].filename
            self.all_lines = args[0].all_lines
            self.all_indentation = args[0].all_indentation

            self.grp_line = args[0].grp_line
            self.end_line = args[0].end_line

            self.name = args[0].name
            self.group_type = args[0].group_type

            self.indentation_length = args[0].indentation_length
            self.intendation_step = args[0].intendation_step
            self.verbose = args[0].verbose
            self.sub_groups = args[0].sub_groups

        else:
            super(SpecialCCLGroup, self).__init__(*args, **kwargs)


class DomainGroup(SpecialCCLGroup):

    def is_rotating(self):
        return False


class CCLBoundary(SpecialCCLGroup):
    pass


@dataclass
class CCLInletBoundary(CCLBoundary):

    def set(self, boundary: InletBoundaryCondition):
        pass

    def set_normal_speed(self, flow_regime='subsonic', normal_speed=0.2, units='m s^-1', turbulence='medium'):
        """turbulence must be ignored if laminar!"""
        _flow_regime = f'{flow_regime[0].capitalize()}{flow_regime[1:]}'
        f"""
      BOUNDARY CONDITIONS:
        FLOW REGIME:
          Option = {_flow_regime}
        END
        MASS AND MOMENTUM:
          Normal Speed = {normal_speed} [{units}]
          Option = Normal Speed
        END
      END
        """
        raise NotImplementedError()

    def set_mass_flow_rate(self):
        raise NotImplementedError()


def cclupdate(func):
    def cclupdate_wrapper(*args, **kwargs):
        current_mtime = pathlib.Path(args[0].filename).stat().st_mtime
        if current_mtime > args[0].mtime:
            _new_args = list(args)
            _new_args[0] = CCLFile(args[0].filename, args[0].intendation_step)
            return func(*tuple(_new_args), **kwargs)
        return func(*args, **kwargs)

    return cclupdate_wrapper


def hdf_to_ccl(hdf_filename: PATHLIKE, ccl_filename: Union[PATHLIKE, None] = None,
               intendation_step: int = 2) -> PATHLIKE:
    hdf_filename = pathlib.Path(hdf_filename)
    if ccl_filename is None:
        ccl_filename = hdf_filename.parent.joinpath(f'{hdf_filename.stem}.ccl')
    else:
        ccl_filename = pathlib.Path(ccl_filename)

    class H5Writer():
        def __init__(self, writer):
            self.writer = writer
        def __call__(self, name, h5obj):
            ret_string = ''
            if isinstance(h5obj, h5py.Group):
                nlevel = len(h5obj.name.split('/'))-2
                _spaces = ''.join([' '] * nlevel)
                ret_string += _spaces + h5obj.name[1:] + '\n'
                for k, v in h5obj.attrs.items():
                    ret_string += _spaces + f' {k} = {v}\n'
                self.writer.write(ret_string)

    def _write_to_file(writer, h5obj):
        ret_string = ''
        nlevel = len(h5obj.name.split('/')) - 2
        _spaces = ''.join([' '] * nlevel)
        name_stem = pathlib.Path(h5obj.name).stem
        if ':' in name_stem:
            ret_string += _spaces + name_stem + '\n'
        else:
            ret_string += _spaces + name_stem + ':\n'

        for k, v in h5obj.attrs.items():
            ret_string += _spaces + f' {k} = {v}\n'

        writer.write(ret_string)

        for k, v in h5obj.items():
            _write_to_file(writer, v)

        ret_string = _spaces + 'END\n'
        writer.write(ret_string)

    with open(ccl_filename, 'w') as f:
        h5w = H5Writer(f)
        level = 0
        with h5py.File(hdf_filename) as h5:
            # _write_to_file(f, h5['/'])
            for k, v in h5.items():
                _write_to_file(f, v)
            # print(h5.visititems(h5w))


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

    def __init__(self, filename: PATHLIKE, intendation_step: int = 2, verbose=False):
        self.filename = pathlib.Path(filename)
        self.lines = self._remove_linebreaks()
        self.indentation = self._get_indentation()
        self.intendation_step = intendation_step
        self.root_group = CCLGroup(self.filename, 0, -1, indentation_length=self.indentation[0][1],
                                   intendation_step=intendation_step,
                                   all_lines=self.lines,
                                   all_indentation=self.indentation, name='root', verbose=verbose)
        self.mtime = self.filename.stat().st_mtime

    @cclupdate
    def get_domain_groups(self):
        flow_group = self.get_flow_group()
        _found = []
        for grp in flow_group.sub_groups.values():
            if grp.group_type == 'DOMAIN':
                _found.append(DomainGroup(grp))
        return _found

    @cclupdate
    def get_flow_group(self):
        for grp in self.root_group.sub_groups.values():
            if grp.group_type == 'FLOW':
                return grp

    @cclupdate
    def to_hdf(self, hdf_filename: PATHLIKE, overwrite=True):
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

    @cclupdate
    def get_boundaries(self) -> List[CCLBoundary]:
        """returns all CCLGroups defining a boundary"""
        found = []
        domain_grps = self.get_domain_groups()
        for grp in domain_grps:
            for sgrp in grp.sub_groups.values():
                if sgrp.group_type == 'BOUNDARY':
                    found.append(CCLBoundary(sgrp))
        return found

    def boundary_condition(self, name):
        boundary_groups = self.get_boundaries()
        for bdry_grp in boundary_groups:
            _grpname = bdry_grp.name.lower().split(':')[1].strip()
            if _grpname == name.lower():
                return CCLInletBoundary(bdry_grp)
        return None


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


def generate_from_res_or_cfx(res_cfx_filename: Union[str, bytes, os.PathLike, pathlib.Path],
                             ccl_filename: pathlib.Path, cfx5pre: str, overwrite=True) -> pathlib.Path:
    if overwrite and ccl_filename.exists():
        ccl_filename.unlink()
    if res_cfx_filename.suffix == '.cfx':
        session_filename = os.path.join(SESSIONS_DIR, 'cfx2ccl.pre')
    elif res_cfx_filename.suffix == '.res':
        session_filename = os.path.join(SESSIONS_DIR, 'res2ccl.pre')
    else:
        raise ValueError(f'Could not determine "session_filename"')

    random_fpath = session.copy_session_file_to_tmp(session_filename)
    _capital_ext = res_cfx_filename.suffix[1:].capitalize()
    session.replace_in_file(random_fpath, f'__{_capital_ext}_FILE__', res_cfx_filename)

    logger.debug(f'Playing CFX session file: {random_fpath}')
    session.play_session(random_fpath, cfx5pre)
    os.remove(random_fpath)
    return ccl_filename


def generate_from_def(def_filename: Union[str, bytes, os.PathLike, pathlib.Path],
                      ccl_filename: Union[str, bytes, os.PathLike, pathlib.Path],
                      overwrite: bool = True) -> pathlib.Path:
    """generates a ccl file from a def file"""
    if ccl_filename.exists() and overwrite:
        ccl_filename.unlink()
    cmd = f'"{CFX5CMDS}" -read -def "{def_filename}" -text "{ccl_filename}"'
    call_cmd(cmd, wait=True)

    if not ccl_filename.exists():
        raise RuntimeError(f'Failed running bash script "{cmd}"')
    return ccl_filename
