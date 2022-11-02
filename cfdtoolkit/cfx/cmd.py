import logging

import subprocess

logger = logging.getLogger(__package__)


def call_cmd(cmd):
    subprocess.run(cmd, shell=True)
