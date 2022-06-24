import logging
import os
import platform
import shlex
import subprocess

logger = logging.getLogger(__package__)


def call_cmd(cmd, wait=True):
    logger.debug(cmd)
    if platform.system().lower() == 'windows' and wait:
        logger.debug('Under windows wait has no effect.'
                     ' The system will always wait until the batch command has finished')
    cmd_split = shlex.split(cmd)
    if wait:
        # waits for the command to complete
        try:
            process = subprocess.run(cmd_split,
                                     stdout=subprocess.PIPE,
                                     universal_newlines=True)
        except RuntimeError as e:
            raise RuntimeError(f'Exception raised for command line string: "{cmd_split}": {e}')
    else:
        # TODO: the following should be solved properly:
        cmd += ' &'
        logger.debug(f'Calling command str: {cmd}')
        os.system(f'"{cmd}"')
        # os.spawnlp(os.P_NOWAIT, '.cfx5solve', *cmd_split)
        # process = subprocess.call(cmd_split,
        #                          universal_newlines=True)
        # # process.communicate()
    # return process
