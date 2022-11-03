import shutil

from cfdtoolkit import set_loglevel
from cfdtoolkit.cfx import CFXInstallation
from cfdtoolkit.cfx.case import CFXCase

set_loglevel('INFO')

cfx = CFXInstallation('cfx.env')
cfx.check()

cfx_filename = shutil.copy2('../../testdata/cylinderflow/steady_state/cyl_steadystate_laminar.cfx',
                            'cyl_steadystate_laminar.cfx')

case = CFXCase(cfx_filename)

case.info()

print(case.res_files[-1].outfile.get_mesh_info())

print(case.res_files[-1].outfile.data)
