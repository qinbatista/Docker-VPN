"""Quiet host command execution without a dependency on installed AI tools."""
import shutil
import subprocess
import sys


def hidden_options():
    if sys.platform == 'win32':
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        return {'startupinfo': startup, 'creationflags': subprocess.CREATE_NO_WINDOW}
    if sys.platform == 'darwin' or sys.platform.startswith('linux'):
        return {}
    raise RuntimeError('Unsupported host platform')


def run(arguments, timeout=60, **options):
    executable = shutil.which(str(arguments[0]))
    if not executable:
        raise RuntimeError('Required executable unavailable: ' + str(arguments[0]))
    return subprocess.run([executable, *arguments[1:]], capture_output=True, timeout=timeout, check=True, **hidden_options(), **options)
