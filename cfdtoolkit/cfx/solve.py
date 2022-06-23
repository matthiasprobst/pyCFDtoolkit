import os
import pathlib

import dotenv

from .. import CFX_DOTENV_FILENAME

dotenv.load_dotenv(CFX_DOTENV_FILENAME)
CFX5SOLVE = os.environ.get("cfx5solve")


def build_cmd(def_filename, nproc, ini_filename, timeout):
    def_filename = pathlib.Path(def_filename)
    cmd = f'"{CFX5SOLVE}"  -def "{def_filename}"'

    if ini_filename is not None:
        cmd += f' -ini "{ini_filename}"'

    cmd += f' -chdir "{def_filename.parent}"'

    if nproc > 1:
        cmd += f' -par-local -partition {int(nproc)} -batch'

    if timeout is not None:
        if timeout <= 0:
            raise ValueError(f'Invalid value for timeout: {timeout}')
        cmd += f' -maxet "{int(timeout)} [s]"'  # e.g. maxet='10 [min]'
    return cmd
