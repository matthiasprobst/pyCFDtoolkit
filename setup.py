import codecs
import os

import setuptools


# version reading from: https://packaging.python.org/en/latest/guides/single-sourcing-package-version/
def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), 'r') as fp:
        return fp.read()


def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


__version__ = get_version('cfdtoolkit/_version.py')
name = 'pyCFDtoolkit'
__author__ = 'Matthias Probst'

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name=f"{name}",
    version=__version__,
    author="Matthias Probst",
    author_email="matthias.probst@kit.edu",
    description="Toolkit to manag and post-process CFD runs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MatthiasProbst/pyCFDtoolkit",
    packages=setuptools.find_packages(),
    package_data={},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
    install_requires=[
        'appdirs',
        'h5py',
        'python-dotenv',
        'jupyterlab',
        'h5py',
        'pandas',
        'xarray'
    ],
    cmdclass={},
)
