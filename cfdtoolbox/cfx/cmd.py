
import subprocess
import shlex
import os
def call_cmd(cmd, wait=True):
    cmd_split = shlex.split(cmd)
    if wait:
        # waits for the command to complete
        process = subprocess.run(cmd_split,
                                 stdout=subprocess.PIPE,
                                 universal_newlines=True)
    else:
        # TODO: the following should be solved properly:
        cmd += ' &'
        os.system(cmd)
        # os.spawnlp(os.P_NOWAIT, '.cfx5solve', *cmd_split)
        # process = subprocess.call(cmd_split,
        #                          universal_newlines=True)
        # # process.communicate()
    # return process