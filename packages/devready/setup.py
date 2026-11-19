"""
setup.py exists solely to install the startup hook into site-packages.
All other metadata lives in pyproject.toml.
"""
import os
import shutil
import sysconfig

from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.install import install


def _purelib():
    return sysconfig.get_paths()["purelib"]


def _copy_pth(target_dir):
    try:
        src = os.path.join(os.path.dirname(__file__), "devready-hook.pth")
        if not os.path.exists(src):
            return
        shutil.copy2(src, os.path.join(target_dir, "devready-hook.pth"))
    except Exception:
        pass


class PostInstall(install):
    def run(self):
        install.run(self)
        _copy_pth(self.install_lib or _purelib())


class PostDevelop(develop):
    def run(self):
        develop.run(self)
        _copy_pth(_purelib())


setup(
    cmdclass={
        "install": PostInstall,
        "develop": PostDevelop,
    },
)
