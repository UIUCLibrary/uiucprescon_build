"""
This was taken from setuptools.monkey after they removed this code in the
following Pull Request was accepted.
https://github.com/pypa/setuptools/pull/4600
This change also shows up in setuptools version 74.0.0.

"""

# flake8: noqa
# pylint: disable-all

import platform
from importlib import import_module
import functools
from setuptools.monkey import patch_func

def patch_for_msvc_specialized_compiler():
    """
    Patch functions in distutils to use standalone Microsoft Visual C++
    compilers.
    """
    from uiucprescon.build import msvc

    if platform.system() != 'Windows':
        # Compilers only available on Microsoft Windows
        return

    def patch_params(mod_name, func_name):
        """
        Prepare the parameters for patch_func to patch indicated function.
        """
        repl_prefix = 'msvc14_'
        repl_name = repl_prefix + func_name.lstrip('_')
        repl = getattr(msvc, repl_name)
        mod = import_module(mod_name)
        if not hasattr(mod, func_name):
            raise ImportError(func_name)
        return repl, mod, func_name

    # Python 3.5+
    msvc14 = functools.partial(patch_params, 'distutils._msvccompiler')

    try:
        # Patch distutils._msvccompiler._get_vc_env
        patch_func(*msvc14('_get_vc_env'))
    except ImportError:
        pass
# patch_for_msvc_specialized_compiler()