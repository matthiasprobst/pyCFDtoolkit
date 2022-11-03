import matplotlib.pyplot as plt
import shutil

from cfdtoolkit import set_loglevel
from cfdtoolkit.cfx import CFXInstallation
from cfdtoolkit.cfx.case import CFXCase
from cfdtoolkit.cfx.ccl import CCLFile

set_loglevel('INFO')

cfx = CFXInstallation('cfx.env')
cfx.check()

cfx_filename = shutil.copy2('../../testdata/cylinderflow/steady_state/cyl_steadystate_laminar.cfx',
                            'cyl_steadystate_laminar.cfx')

case = CFXCase(cfx_filename)
case.info()
case.reset()
case.info()
case.pre.write_def()
case.solve.run(nproc=4)
case.info()

# change max terations:
cclfilename = case.solve.write_ccl()
ccl = CCLFile(cclfilename)
ccl.flow[0]['SOLVER CONTROL/CONVERGENCE CONTROL'].options['Maximum Number of Iterations'] = '2'
case.pre.from_h5ccl(ccl.filename)
case.pre.write_def()

# continue:
case.solve.run(nproc=4, ini_filename=case.res[-1])
plt.figure()
for r in case.res:
    r.outfile.data.cpu_seconds.plot()
plt.show()
case.info()
case.reset()
