import datetime
import numpy as np
import xarray as xr
from typing import Dict

DATETIME_FMT = '%Y-%m-%dT%H:%M:%S'


def extract_out_data(ansys_cfx_out_file: str) -> xr.Dataset:
    """tries to extract data from an *.out file"""

    # from a rotor simulation gets rotor positions
    ansys_cfx_out_file = str(ansys_cfx_out_file)
    with open(ansys_cfx_out_file, "r") as f:
        lines = f.readlines()

    data = dict(
        iteration=[],
        timestep=[],
        simulation_time=[],
        cpu_seconds=[],
        rotation_per_timestep=[],
        rotated_deg_up_to_now=[],
        rotated_pitches_up_to_now=[],
        courant_number_rms=[],
        courant_number_max=[])
    attrs = {}
    for (iline, line) in enumerate(lines):
        if iline == 0:
            dtstr = line.split('at', 1)[1].strip()
            attrs['solver_start_datetime'] = datetime.datetime.strptime(
                dtstr, '%H:%M:%S on %d %b %Y'
            ).strftime(DATETIME_FMT)

        if 'TIME STEP =' in line:
            # if transient
            _, split1, split2, split3 = line.split('=')
            data['iteration'].append(int(split1.split('SIMULATION')[0].strip()))
            data['simulation_time'].append(float(split2.split('CPU')[0].strip()))
            data['cpu_seconds'].append(float(split3.strip()))
        elif 'OUTER LOOP ITERATION = ' in line:
            # steady state
            # if it is a restarted file, then there are brackets in that line!
            if '(' in line:
                data['iteration'].append(int(line.split('=')[1].split('(', 1)[0].strip()))
                data['cpu_seconds'].append(float(line.split('=')[-1].split('(', 1)[0].strip()))
            else:
                data['iteration'].append(int(line.split('=')[1].split('CPU SECONDS')[0].strip()))
                data['cpu_seconds'].append(float(line.rsplit('=', 1)[-1].strip()))
        elif 'Rotated in this time step [degrees]' in line:
            data['rotation_per_timestep'].append(float(line.split('=')[1].strip()))
        elif 'Rotated up to now [degrees]' in line:
            data['rotated_deg_up_to_now'].append(float(line.split('=')[1].strip()))
        elif 'Rotated number of pitches up to now' in line:
            data['rotated_pitches_up_to_now'].append(float(line.split('=')[1].strip()))
        elif 'Timestepping Information' in line:
            if 'Acoustic' in lines[iline + 2]:
                # print('this is an acoustic computation!!!')
                dt, _courant_number_rms_max, _acoustic_courant_number_rms_max = lines[iline + 6].split('|')[1:4]
                # print(f'dt={dt}, _courant_number_rms_max={_courant_number_rms_max},'
                #       f' _acoustic_courant_number_rms_max={_acoustic_courant_number_rms_max}')
                data['timestep'].append(float(dt.strip()))
                _splitted = _courant_number_rms_max.strip()[0].split(' ')
                _courant_number_rms, _courant_number_max = _splitted[0], _splitted[-1]
                data['courant_number_rms'].append(float(_courant_number_rms.strip()))
                data['courant_number_max'].append(float(_courant_number_max.strip()))
            else:
                dt, _courant_number_rms, _courant_number_max = lines[iline + 4].split('|')[1:4]
                data['timestep'].append(float(dt.strip()))
                data['courant_number_rms'].append(float(_courant_number_rms.strip()))
                data['courant_number_max'].append(float(_courant_number_max.strip()))
        elif 'Job finished:' in line:
            dtimestr = line.split(':', 1)[1].strip()
            attrs['job_finished_datetime'] = datetime.datetime.strptime(
                dtimestr, '%a %b  %d %H:%M:%S %Y'
            ).strftime(DATETIME_FMT)
    scale_ds_names = ('iteration', 'timestep', 'simulation_time')
    return_data = {k: np.asarray(v) for k, v in data.items() if len(v) > 0 and k not in scale_ds_names}
    iteration = data.get('iteration')

    ds = xr.Dataset(data_vars={k: (['iteration'], v) for k, v in return_data.items()},
                    coords={'iteration': np.asarray(iteration)},
                    attrs=attrs)
    ds['iteration'].attrs['units'] = ' '
    if 'cpu_seconds' in ds:
        ds['cpu_seconds'].attrs['units'] = 's'
    return ds


def mesh_info_from_file(ansys_cfx_out_file) -> Dict:
    """get mesh info from an .out-file"""
    with open(ansys_cfx_out_file, "r") as f:
        lines = f.readlines()

    nfound1 = 0
    nfound2 = 0
    iend = -1
    for (iline, line) in enumerate(lines):
        if "Mesh Statistics" in line and nfound1 < 1:
            nfound1 += 1
            istart = iline

        if "+--------------------------------------------------------------------+" in line and nfound1 == 1 and nfound2 < 2:
            iend = iline
            nfound2 += 1

    # find domain line numbers:
    domain_name = []
    domain_name_iline = []
    domain_mesh = []
    for iline in range(iend - istart):
        line = lines[istart + iline].strip()

        if "Domain Name :" in line:
            domain_name.append(line.split(":")[1].strip())
            domain_name_iline.append(iline)

    for dni in domain_name_iline:
        for i in range(5):
            line = lines[istart + dni + i]
            if "Total Number of Nodes" in line:
                domain_mesh.append(line.split("=")[1].strip())
                break
    mesh_dict = {}
    for (name, mesh) in zip(domain_name, domain_mesh):
        mesh_dict[name] = int(mesh)
    return mesh_dict
