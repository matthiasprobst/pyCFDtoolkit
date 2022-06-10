
import subprocess
import shlex

def call_cmd(cmd):
    cmd_split = shlex.split(cmd)
    process = subprocess.run(cmd_split,
                             stdout=subprocess.PIPE,
                             universal_newlines=True)
    return process