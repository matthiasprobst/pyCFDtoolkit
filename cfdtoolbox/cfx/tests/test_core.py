import pathlib

from cfdtoolbox.cfx.core import AnalysisType
from cfdtoolbox.cfx import CFXCase


def test__scan_for_files():
    testdata_dir = pathlib.Path(__file__).parent.joinpath('../../../testdata').resolve()

    case = CFXCase(testdata_dir.joinpath('simpleRotor'), '*_frz*')
    case.write_ccl_file()
    assert case.analysis_type == AnalysisType.STEADYSTATE
    assert len(case.res_files) == len(list(case.working_dir.glob('*_frz*.res')))

    case = CFXCase(testdata_dir.joinpath('simpleRotor'), '*_trn*')
    case.write_ccl_file()
    assert case.analysis_type == AnalysisType.TRANSIENT
    assert len(case.res_files) == len(list(case.working_dir.glob('*_trn*.res')))

    case.res_files[-1].resume(2)
