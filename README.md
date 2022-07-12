# pyCFDtoolkit

A toolkit mainly to post-process CFD results. At the current development stage,
it mainly provides tools to control ANSYS-CFX simulations.


## Note
This repository is very alpha (!) and under heavy current development. Please 
help me by contributing code and writing issues.
It is developed under LINUX. It should run under windows but is currently not checked. Once a stable version for linux 
exists, windows will be supported, too.

## Installation
Clone the repo and install it using `pip`
```
    git clone https://github.com/MatthiasProbst/pyCFDtoolbox.git
    pip install (-e) pyCFDtoolbox
```
Toolbox mainly to post-process CFD results. At the current development stage, it mainly provides tools to controll
ANSYS-cfx simulations.

## Modules
### ANSYS-cfx control
Allows you to control and manipulate ANSYS-cfx cases. You can manage them 
and create queues which may include some conditional code, e.g. check convergence of 
a steady state case before starting a transient one. This is made easy as you can access and 
control Ansys (data) via python. All you need is an instance of the class `CFXCase`.

## Versions

### v0.2.1
  - added requirements
### v0.2.0
  - Package got renamed from `cfdtoolbox` to `cfdtoolkit`
  - bugfixes
  - class `DefFile` no longer needed. def filename is built from the case filename
### v0.1.0-rc
  - Ansys-CFX module (`cfx`) exists with limited functionality (notebook example code exists):
    - starting, resuming and stopping cases.
    - changing single parameters in the CCL file
    - changing a full inlet and outlet condition
    - changing the timestep of a transient case
    - changing the number of max iterations per run
    
---
 
## Troubleshooting
1. <ins>Cannot install netCDF4</ins><br>Installation in anaconda environment (known issue under windows, anaconda 
version 4.12.0): Installation of netCDF4 may fail. Manually install it via conda install -c `conda-forge netcdf4`