import os
from time import perf_counter_ns

import h5py
import pkg_resources
from numpy import ndarray

IGNORE_ATTRS = ('units', 'DIMENSION_LIST', 'REFERENCE_LIST', 'NAME', 'CLASS', 'COORDINATES')
CSS_STR = pkg_resources.resource_string('cfdtoolkit', 'style.css').decode("utf8")

"""
disclaimer:

dropdown _html representation realized with "h5file_html_repr"
is inspired and mostly taken from:
https://jsfiddle.net/tay08cn9/4/ (xarray package)

"""


def _attribute_repr_html(name, value, max_attr_length):
    if isinstance(value, ndarray):
        _value = value.copy()
        for i, v in enumerate(value):
            if isinstance(v, str):
                if len(v) > max_attr_length:
                    _value[i] = f'{v[0:max_attr_length]}...'
    else:
        _value_str = f'{value}'
        if len(_value_str) > max_attr_length:
            _value = f'{_value_str[0:max_attr_length]}...'
        else:
            _value = value

    if name in ('DIMENSION_LIST', 'REFERENCE_LIST'):
        _value = _value.__str__().replace('<', '&#60;')
        _value = _value.replace('>', '&#62;')

    if isinstance(_value, ndarray):
        _value_str = _value.__str__().replace("' '", "', '")
    else:
        _value_str = _value

    if name == 'standard_name':
        # TODO give standard name a dropdown which shows description and canonical_units
        return f"""<li style="list-style-type: none; font-style:
         italic">{name} : {_value_str}</li>"""

        # _id_int = perf_counter_ns().__str__()
        # return f"""<ul id="ds-sn-{_id_int}" class="standard-name">
        #         <input id="sn-{_id_int}" class="standard-name" type="checkbox">
        #         <label class='standard-name'; font-style: italic;
        #                for="sn-{_id_int}">{name}: {_value_str}</label>
        #         <ul class="standard-name">
        #             <li style="list-style-type: none; font-style: italic">
        #             description: {standard_names_dict[_value_str]['description']}</li>
        #             <li style="list-style-type: none; font-style: italic">
        #             canonical units: {standard_names_dict[_value_str]['canonical_units']}</li>
        #         </ul>
        #
        #     </ul>"""
    else:
        return f'<li style="list-style-type: none; font-style: italic">{name} : {_value_str}</li>'


def _group_repr_html(h5group, max_attr_length, collapsed):
    nkeys = len(h5group.keys())
    _id = f'ds-{h5group.name}-{perf_counter_ns().__str__()}'
    _groupname = os.path.basename(h5group.name)
    checkbox_state = 'checked'
    if _groupname == '':
        _groupname = '/'  # recover root name
    else:
        if collapsed:
            checkbox_state = ''

    _html = f"""\n
          <ul style="list-style-type: none;" class="h5tb-sections">
                <li>
                    <input id="group-{_id}" type="checkbox" {checkbox_state}>
                    <label style="font-weight: bold" for="group-{_id}">
                    {_groupname}<span>({nkeys})</span></label>
              """

    _html += f"""\n
                <ul class="h5tb-attr-list">"""
    # write attributes:
    for k, v in h5group.attrs.items():
        _html += _attribute_repr_html(k, v, max_attr_length)
    # close attribute section
    _html += f"""
                </ul>"""

    datasets = [(k, v) for k, v in h5group.items() if isinstance(v, h5py.Dataset) or isinstance(v, h5py.Dataset)]
    groups = [(k, v) for k, v in h5group.items() if isinstance(v, h5py.Group) or isinstance(v, h5py.Group)]

    for k, v in datasets:
        _html += _html_repr_dataset(v, max_attr_length)

    for k, v in groups:
        _html += _group_repr_html(v, max_attr_length, collapsed)
    _html += '\n</li>'
    _html += '\n</ul>'
    return _html


def _html_repr_dataset(h5dataset, max_attr_length,
                       _ignore_attrs=IGNORE_ATTRS):
    if 'units' in h5dataset.attrs:
        _unit = h5dataset.attrs['units']
        if _unit in ('', ' '):
            _unit = '-'
    else:
        _unit = 'N.A.'

    ds_name = os.path.basename(h5dataset.name)
    if h5dataset.ndim == 0:
        _shape = ''
    else:
        _shape = h5dataset.shape

    _id1 = f'ds-1-{h5dataset.name}-{perf_counter_ns().__str__()}'
    _id2 = f'ds-2-{h5dataset.name}-{perf_counter_ns().__str__()}'
    _html_pre = f"""\n
                <ul id="{_id1}" class="h5tb-var-list">
                <input id="{_id2}" class="h5tb-varname-in" type="checkbox">
                <label class='h5tb-varname' 
                    for="{_id2}">{ds_name}</label>
                <span class="h5tb-dims">{_shape}</span>
                <span class="h5tb-units">[{_unit}]</span>"""
    # now all attributes of the dataset:
    # open attribute section:
    _html_ds_attrs = f"""\n<ul class="h5tb-attr-list">"""
    # write attributes:
    for k, v in h5dataset.attrs.items():
        if k not in _ignore_attrs:
            _html_ds_attrs += _attribute_repr_html(k, v, max_attr_length)
    # close attribute section
    _html_ds_attrs += f"""\n
                </ul>"""

    # close dataset section
    _html_post = f"""\n
             </ul>
             """
    _html_ds = _html_pre + _html_ds_attrs + _html_post
    return _html_ds


def h5file_html_repr(h5, max_attr_length, preamble=None,
                     build_debug_html_page: bool = False,
                     collapsed: bool = True):
    """

    Parameters
    ----------
    collapsed: bool, optional=True
        If True, all groups are shown collapsed.
    """
    if not h5.id:
        raise ValueError(f'Can only explore opened HDF files!')

    if isinstance(h5, h5py.Group) or isinstance(h5, h5py.Group):
        h5group = h5
    else:
        h5group = h5['/']

    _id = h5group.name + perf_counter_ns().__str__()

    _html = f'<head><style>{CSS_STR}</style></head>'
    if preamble:
        _html += f'\n{preamble}'
    _html += "\n<div class='h5tb-warp'>"
    _html += _group_repr_html(h5group, max_attr_length=max_attr_length, collapsed=collapsed)
    _html += "\n</div>"

    if build_debug_html_page:
        with open('debug_html_page._html', 'w', encoding='utf-8') as f:
            f.write(_html)
    return _html
