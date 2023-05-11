@echo off
call "%~dp0init_conda.bat"


rem Get absolute path where csb-python repo was checked out to
set REL_CSB_ROOT=%~dp0\..\..\
set CSB_ROOT=
pushd %REL_CSB_ROOT%
set CSB_ROOT=%CD%
popd

rem Activate the base environment so that we can make the virtual environment
call %MINICONDA%\Scripts\activate.bat %MINICONDA%
echo Creating environment defined in %CSB_ROOT%\conda-env.yml...
%MINICONDA%\Scripts\conda update -y -q conda
%MINICONDA%\Scripts\conda config -q --add channels conda-forge
%MINICONDA%\Scripts\conda env create --file %CSB_ROOT%\conda-env.yml
