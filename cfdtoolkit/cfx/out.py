import pandas as pd


def extract_out_data(ansys_cfx_out_file: str) -> pd.DataFrame:
    """tries to extract data from an *.out file"""

    # from a rotor simulation gets rotor positions

    with open(ansys_cfx_out_file, "r") as f:
        lines = f.readlines()

    iteration = list()
    timestep = list()
    simulation_time = list()
    cpu_seconds = list()
    rotation_per_timestep = list()
    rotated_deg_up_to_now = list()
    rotated_pitches_up_to_now = list()
    courant_number_rms = list()
    courant_number_max = list()
    for (iline, line) in enumerate(lines):
        if 'TIME STEP =' in line:
            _, split1, split2, split3 = line.split('=')
            iteration.append(int(split1.split('SIMULATION')[0].strip()))
            simulation_time.append(float(split2.split('CPU')[0].strip()))
            cpu_seconds.append(float(split3.strip()))
        elif 'Rotated in this time step [degrees]' in line:
            rotation_per_timestep.append(float(line.split('=')[1].strip()))
        elif 'Rotated up to now [degrees]' in line:
            rotated_deg_up_to_now.append(float(line.split('=')[1].strip()))
        elif 'Rotated number of pitches up to now' in line:
            rotated_pitches_up_to_now.append(float(line.split('=')[1].strip()))
        elif 'Timestepping Information' in line:
            if 'Acoustic' in lines[iline + 2]:
                # print('this is an acoustic computation!!!')
                dt, _courant_number_rms_max, _acoustic_courant_number_rms_max = lines[iline + 6].split('|')[1:4]
                # print(f'dt={dt}, _courant_number_rms_max={_courant_number_rms_max},'
                #       f' _acoustic_courant_number_rms_max={_acoustic_courant_number_rms_max}')
                timestep.append(float(dt.strip()))
                _splitted = _courant_number_rms_max.strip()[0].split(' ')
                _courant_number_rms, _courant_number_max = _splitted[0], _splitted[-1]
                courant_number_rms.append(float(_courant_number_rms.strip()))
                courant_number_max.append(float(_courant_number_max.strip()))
            else:
                dt, _courant_number_rms, _courant_number_max = lines[iline + 4].split('|')[1:4]
                timestep.append(float(dt.strip()))
                courant_number_rms.append(float(_courant_number_rms.strip()))
                courant_number_max.append(float(_courant_number_max.strip()))

    return pd.DataFrame({'timestep': timestep,
                         'iteration': iteration,
                         'simulation_time': simulation_time,
                         'cpu_seconds': cpu_seconds,
                         'rotation_per_timestep': rotation_per_timestep,
                         'rotated_deg_up_to_now': rotated_deg_up_to_now,
                         'rotated_pitches_up_to_now': rotated_pitches_up_to_now,
                         'courant_number_rms': courant_number_rms,
                         'courant_number_max': courant_number_max}
                        )


def mesh_info_from_file(ansys_cfx_out_file) -> pd.DataFrame:
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

        if " Domain Name :" in line:
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
    return pd.DataFrame(mesh_dict)
