import pathlib

from cfdtoolbox.cfx.core import CFXCase, AnalysisType


def test__scan_for_files():
    testdata_dir = pathlib.Path(__file__).parent.joinpath('../../../testdata').resolve()

    case = CFXCase(testdata_dir.joinpath('simpleRotor'), '*_frz*')
    assert case.case_file.filename.name == case.case_file.name
    case.write_ccl_file()
    assert case.analysis_type == AnalysisType.STEADYSTATE
    case = CFXCase(testdata_dir.joinpath('simpleRotor'), '*_trn*')
    assert case.case_file.filename.name == case.case_file.name
    case.write_ccl_file()
    assert case.analysis_type == AnalysisType.TRANSIENT
