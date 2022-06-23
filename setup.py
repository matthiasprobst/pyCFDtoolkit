import setuptools

from cfdtoolkit._version import __version__

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
    ],
    cmdclass={},
)
