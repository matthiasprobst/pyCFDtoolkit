import logging
import os
import pathlib
import shutil
from dataclasses import dataclass
from typing import Union, List

import dotenv
import h5py
import numpy as np
from IPython.display import display, HTML
from h5wrapperpy._html.html_repr import h5file_html_repr

from . import session
from .boundary_conditions import CFXBoundaryCondition
from .cmd import call_cmd
from .session import cfx2def
from .utils import change_suffix, capitalize_phrase
from .. import CFX_DOTENV_FILENAME, SESSIONS_DIR
from ..typing import PATHLIKE

dotenv.load_dotenv(CFX_DOTENV_FILENAME)

logger = logging.getLogger('cfdtoolkit')

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
            if _name.endswith(':'):
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
                # all options are at top of a group. once there is a line without "=" the next group begins...
                return data
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
            # logger.debug(f'Creating group with name {self.name} at level: {h5grp.name}')
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
            # logger.debug(name)
            subg.create_h5_group(g, overwrite=overwrite)


# def cclupdate(func):
#     def cclupdate_wrapper(*args, **kwargs):
#         current_mtime = pathlib.Path(args[0].filename).stat().st_mtime
#         if current_mtime > args[0].mtime:
#             _new_args = list(args)
#             _new_args[0] = CCLTextFile(args[0].filename, args[0].intendation_step)
#             return func(*tuple(_new_args), **kwargs)
#         return func(*args, **kwargs)
#
#     return cclupdate_wrapper


def hdf_to_ccl(hdf_filename: PATHLIKE, ccl_filename: Union[PATHLIKE, None] = None,
               intendation_step: int = 2) -> pathlib.Path:
    """converts a HDF file with CCL content into a CCL text file"""
    hdf_filename = pathlib.Path(hdf_filename)
    if ccl_filename is None:
        ccl_filename = hdf_filename.parent.joinpath(f'{hdf_filename.stem}.ccl')
    else:
        ccl_filename = pathlib.Path(ccl_filename)

    def _write_to_file(writer, h5obj):
        ret_string = ''
        nlevel = len(h5obj.name.split('/')) - 2
        _spaces = ''.join([' '] * nlevel * intendation_step)
        name_stem = pathlib.Path(h5obj.name).stem
        if ':' in name_stem:
            ret_string += f'{_spaces}{name_stem.upper()}\n'
        else:
            ret_string += f'{_spaces}{name_stem.upper()}:\n'

        for _k, _v in h5obj.attrs.items():
            ret_string += _spaces.join([' '] * intendation_step) + f' {_k.capitalize()} = {capitalize_phrase(_v)}\n'

        writer.write(ret_string)

        for _v in h5obj.values():
            _write_to_file(writer, _v)

        ret_string = f'{_spaces}END\n'
        writer.write(ret_string)

    with open(ccl_filename, 'w') as f:
        with h5py.File(hdf_filename) as h5:
            for k, v in h5.items():
                _write_to_file(f, v)

    return ccl_filename


INTENDATION_STEP = 2


class CCLTextFile:
    """
    Reads in a ANSYS CFX *.ccl file (plain text)

    Example
    -------
    c = CCL_File(ccl_filename)
    c.write_to_hdf('ccltest.hdf', overwrite=True)
    """

    def __init__(self, filename: PATHLIKE, verbose: bool = False):
        self.filename = pathlib.Path(filename)
        self.lines = self._remove_linebreaks()
        self.indentation = self._get_indentation()
        self.intendation_step = INTENDATION_STEP
        self.root_group = CCLGroup(self.filename, 0, -1, indentation_length=self.indentation[0][1],
                                   intendation_step=self.intendation_step,
                                   all_lines=self.lines,
                                   all_indentation=self.indentation, name='root', verbose=verbose)
        self.mtime = self.filename.stat().st_mtime

    def get_flow_group(self):
        for grp in self.root_group.sub_groups.values():
            if grp.group_type == 'FLOW':
                return grp

    def to_hdf(self, hdf_filename: Union[PATHLIKE, None] = None, overwrite=True):
        if hdf_filename is None:
            hdf_filename = change_suffix(self.filename, '.hdf')
        else:
            hdf_filename = pathlib.Path(hdf_filename)

        if hdf_filename.is_file() and not overwrite:
            raise FileExistsError(f'Target HDF file exists and overwrite is set to False!')

        with h5py.File(hdf_filename, 'w') as h5:
            self.root_group.create_h5_group(h5['/'], root_group=True, overwrite=True)

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
        return indentation


def _list_of_instances_by_keyword_substring(filename, root_group, substring, class_):
    instances = []
    with h5py.File(filename) as h5:
        for k in h5[root_group].keys():
            if substring in k:
                if root_group == '/':
                    instances.append(class_(k, filename))
                else:
                    instances.append(class_(f'{root_group}/{k}', filename))
    return instances


@dataclass
class CCLHDFAttributWrapper:
    filename: PATHLIKE
    path: PATHLIKE
    values: dict

    def __setitem__(self, key, value):
        _ = self.values[key]  # let python raise the error if key not in self.values
        with h5py.File(self.filename, 'r+') as h5:
            h5[self.path].attrs[key] = value

    def __getitem__(self, item):
        return self.values[item]

    def __repr__(self):
        return str(self.values)


class CCLHDFGroup:

    def __init__(self, path: str, filename: PATHLIKE):
        self.path = path
        self.filename = filename

    @property
    def options(self):
        with h5py.File(self.filename) as h5:
            attr_dict = dict(h5[self.path].attrs.items())
        return CCLHDFAttributWrapper(self.filename, self.path, attr_dict)

    def __repr__(self):
        return f'CCLHDFGroup {self.path} of file {self.filename}'

    def __str__(self):
        return self.__repr__()

    def _repr_html_(self):
        with h5py.File(self.filename) as h5:
            return h5file_html_repr(h5[self.path], 50, collapsed=False)

    def dump(self):
        with h5py.File(self.filename) as h5:
            display(HTML((h5file_html_repr(h5[self.path], 50))))

    def __getattr__(self, item):
        _item = item.replace('_', ' ')
        with h5py.File(self.filename) as h5:
            if _item in h5[self.path]:
                return CCLHDFGroup(f'{self.path}/{_item.upper()}', self.filename)
            else:
                if _item.upper() in h5[self.path]:
                    return CCLHDFGroup(f'{self.path}/{_item.upper()}', self.filename)
        raise KeyError(f'{item} not found in {self.path}')

    def __getitem__(self, item):
        with h5py.File(self.filename) as h5:
            if item in h5[self.path]:
                return CCLHDFGroup(f'{self.path}/{item}', self.filename)
            else:
                raise KeyError(f'{item} not found in {self.path}')

    @property
    def parent(self):
        if self.path == '/':
            return CCLHDFGroup('/', self.filename)
        else:
            parent_path = self.path.rsplit('/', 1)[0]
            return CCLHDFGroup(parent_path, self.filename)

    def get_parent_path(self):
        if self.path == '/':
            return '/'
        return self.path.rsplit('/', 1)[0]

    def rename(self, new_name: str):
        """renames hdf group. call h5py.move()"""
        if self.path == '/':
            raise KeyError(f'Cannot rename roote group!')
        with h5py.File(self.filename, 'r+') as h5:
            parent_path = self.get_parent_path()
            if new_name[0] == '/':
                new_name = new_name[1:]
            _new_path = f'{parent_path}/{new_name}'
            h5.move(self.path, _new_path)
            return self.__class__(_new_path, self.filename)


class CCLHDFBoundaryCondition(CCLHDFGroup):
    pass


class CCLHDFBoundary(CCLHDFGroup):

    def __repr__(self):
        return f'Boundary "{self.name}"\n> type: {self.type}'

    @property
    def name(self):
        """Returns boundary name defined by user"""
        return pathlib.Path(self.path).stem.split(':', 1)[1]

    @property
    def type(self):
        """Returns boundary type, e.g. INLET"""
        with h5py.File(self.filename) as h5:
            return h5[self.path].attrs['Boundary Type']

    @property
    def condition(self):
        """Returns the boundary condition group of the boundary"""
        return _list_of_instances_by_keyword_substring(self.filename, self.path, 'BOUNDARY CONDITIONS',
                                                       CCLHDFBoundaryCondition)[0]

    @condition.setter
    def condition(self, bdry):
        """Writes a new boundary condition to the HDF file"""
        if not isinstance(bdry, CFXBoundaryCondition):
            raise TypeError(f'Must provide a instance of type {CFXBoundaryCondition}, not {type(bdry)}')
        bdry.write(self.filename, self.path)


class CCLHDFDomainGroup(CCLHDFGroup):

    @property
    def name(self):
        return pathlib.Path(self.path).stem.split(':', 1)[1]

    @property
    def boundaries(self):
        """returns domain groups"""
        return _list_of_instances_by_keyword_substring(self.filename, self.path, 'BOUNDARY: ', CCLHDFBoundary)

    def boundary(self, name):
        return self.boundaries[name]

    def get_boundary_type(self, bdry_type: str, squeeze: bool = True) -> Union[CCLHDFBoundary, List[CCLHDFBoundary]]:
        """Filters for a specific boundary type

        Parameters
        ---------
        bdry_type: str
            Name of the boundary type, e.g. 'inlet'
        squeeze: bool, optional=True
            Whether to return a CCLHDFBoundary instance if only one boundary was found instead of
            returnig a list of only one item.

        Returns
        -------
        Depends on parameter squeeze. Generally a list of found boundaries is returned. If squeeze and
        only one boundary was found, the instance is returned instead of a list of a single item.
        """
        found = []
        for bry in self.boundaries:
            if bry.type.lower() == bdry_type.lower():
                found.append(bry)
        if len(found) == 1 and squeeze:
            return found[0]
        return found

    def parent(self):
        if self.path == '/':
            return CCLHDFGroup('/', self.filename)
        else:
            parent_path = self.get_parent_path()
            if 'DOMAIN: ' in parent_path:
                return CCLHDFDomainGroup(parent_path, self.filename)
            return CCLHDFGroup(parent_path, self.filename)


class CCLHDFFlowGroup(CCLHDFGroup):

    @property
    def domains(self):
        """returns domain groups"""
        return _list_of_instances_by_keyword_substring(self.filename, self.path, 'DOMAIN: ', CCLHDFDomainGroup)

    def get_boundary_type(self, bdry_type: str, squeeze: bool = True) -> Union[CCLHDFBoundary, List[CCLHDFBoundary]]:
        """Filters for a specific boundary type. Walks thorugh all domains

        Parameters
        ---------
        bdry_type: str
            Name of the boundary type, e.g. 'inlet'
        squeeze: bool, optional=True
            Whether to return a CCLHDFBoundary instance if only one boundary was found instead of
            returnig a list of only one item.

        Returns
        -------
        Depends on parameter squeeze. Generally a list of found boundaries is returned. If squeeze and
        only one boundary was found, the instance is returned instead of a list of a single item.
        """
        found = []
        for domain in self.domains:
            for bry in self.boundaries:
                if bry.type.lower() == bdry_type.lower():
                    found.append(bry)
        if len(found) == 1 and squeeze:
            return found[0]
        return found

    # @property
    # def solver_control(self):
    #     return CCLHDFSolverControlGroup(self.path, self.filename)
    # @property
    # def output_control(self):
    #     return CCLHDFOutputControlGroup(self.path, self.filename)


class CCLFile:
    """Interface class to the HDF file containing CCL data"""

    def __init__(self, filename: PATHLIKE):
        """
        Note: if the cfx file is younger than the ccl file, the ccl file will be rewritten
        from the cfx file! All data in the existing ccl hdf file will be overwritten.
        """
        # logger.debug('reading ccl')
        filename = pathlib.Path(filename)
        if filename.suffix == '.hdf':
            self.filename = filename
            cfx_filename = change_suffix(filename, '.cfx')
            if self.filename.stat().st_mtime < cfx_filename.stat().st_mtime:
                # logger.debug('CCL HDF file exists but out of date. generating new one from the cfx file')
                _ = CCLTextFile(generate(cfx_filename)).to_hdf(self.filename)

        elif filename.suffix == '.ccl':
            self.filename = CCLTextFile(filename).to_hdf(change_suffix(filename, '.hdf'))

        elif filename.suffix in ('.res', '.def', '.cfx'):
            self.filename = CCLTextFile(generate(filename)).to_hdf(change_suffix(filename, '.hdf'))

        else:
            raise ValueError(f'Unexpected suffix: {filename.suffix}. Must be .hdf, .ccl, .def or .cfx!')

    def __getitem__(self, item):
        with h5py.File(self.filename) as h5:
            if item not in h5:
                return KeyError(f'Key not found in {h5.name}')
        return CCLHDFGroup(item, self.filename)

    def __repr__(self):
        return f'CCLFile {self.filename}'

    def __str__(self):
        return f'CCLFile {self.filename}'

    def dump(self):
        """dumps the content in pretty html style (only in notebooks)"""
        with h5py.File(self.filename) as h5:
            display(HTML((h5file_html_repr(h5['/'], 50))))

    def _repr_html_(self):
        with h5py.File(self.filename) as h5:
            return h5file_html_repr(h5['/'], 50)

    @property
    def flow(self) -> List[CCLHDFFlowGroup]:
        """Returns a list of groups starting wiht 'FLOW: '"""
        return _list_of_instances_by_keyword_substring(self.filename, '/', 'FLOW: ', CCLHDFFlowGroup)

    def to_ccl(self, ccl_filename: Union[PATHLIKE, None]):
        if ccl_filename is None:
            ccl_filename = change_suffix(self.filename)
        hdf_to_ccl(self.filename, ccl_filename, intendation_step=INTENDATION_STEP)


def generate(input_file: PATHLIKE, ccl_filename: Union[PATHLIKE, None] = None,
             cfx5pre: pathlib.Path = None, overwrite: bool = True) -> pathlib.Path:
    """
    Converts a .res, .cfx or .def file into a ccl file.
    If no `ccl_filename` is provided the input filename is
    taken and extension is changed accordingly to *.ccl

    Parameters
    ----------
    input_file : PATHLIKE
        *.res or *.cfx file
    ccl_filename: PATHLIKE or None
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
    input_file = pathlib.Path(input_file).resolve()

    if input_file.suffix not in ('.cfx', '.res', '.def'):
        raise ValueError('Please provide a ANSYS CFX file.')

    if ccl_filename is None:
        ccl_filename = change_suffix(input_file, '.ccl')
    # logger.debug(f'*.ccl input_file: {ccl_filename}')

    if input_file.suffix in ('.cfx', '.res'):
        # build def file and then call _generate_from_def
        # this is the safe way!
        if cfx5pre is None:
            cfx5pre = CFX5PRE

        def_filename = cfx2def(input_file)
        return _generate_from_def(def_filename, ccl_filename, overwrite)
    return _generate_from_def(input_file, ccl_filename, overwrite)


def _generate_from_res_or_cfx(res_cfx_filename: PATHLIKE,
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
    _upper_ext = res_cfx_filename.suffix[1:].upper()
    session.replace_in_file(random_fpath, f'__{_upper_ext}_FILE__', res_cfx_filename)
    session.replace_in_file(random_fpath, '__CCL_FILE__', ccl_filename)

    logger.debug(f'Playing CFX session file: {random_fpath}')
    session.play_session(random_fpath, cfx5pre)
    os.remove(random_fpath)
    return ccl_filename


def _generate_from_def(def_filename: PATHLIKE,
                       ccl_filename: PATHLIKE,
                       overwrite: bool = True) -> pathlib.Path:
    """generates a ccl file from a def file"""
    if ccl_filename.exists() and overwrite:
        ccl_filename.unlink()
    cmd = f'"{CFX5CMDS}" -read -def "{def_filename}" -text "{ccl_filename}"'
    call_cmd(cmd, wait=True)

    if not ccl_filename.exists():
        raise RuntimeError(f'Failed running bash script "{cmd}"')
    return ccl_filename
