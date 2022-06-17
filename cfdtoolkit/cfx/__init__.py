import warnings
from os import environ
from pathlib import Path

from .case import CFXCase


def check_installation():
    """checks if exe are findable"""

    CFX5SOLVE = environ.get("cfx5solve")
    CFX5PRE = environ.get("cfx5pre")
    CFX5CMDS = environ.get("cfx5cmds")

    for exe_name, exe_path in (('cfx5solve', CFX5SOLVE), ('cfx5pre', CFX5PRE),
                               ('cfx5cmds', CFX5CMDS)):
        if exe_path is None:
            warnings.warn(f'{exe_name} not found in environment variables!')
        else:
            if not Path(exe_path).exists():
                warnings.warn(f'cfx5solve not found: "{Path(exe_path).resolve()}"')


check_installation()
