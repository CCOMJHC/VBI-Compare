@echo off
call "%~dp0init_conda.bat"
rem First set up Python environment variables so that we can run conda enough to activate our env
set PYTHONHOME=%MINICONDA%
set PYTHONPATH=%MINICONDA%;%MINICONDA%\DLLs;%MINICONDA%\Library\bin;%MINICONDA%\Lib;%MINICONDA%\Lib\site-packages
rem Activate our env
set ENVPATH=%MINICONDA%\envs\csb
call %MINICONDA%\Scripts\activate.bat %ENVPATH%
rem Now, for some reason activating the env isn't enough when running this
rem   inside of a QGIS-aware shell, so we need to set Python environment variables for our env by hand...
set PYTHONHOME=%ENVPATH%
set PYTHONPATH=%ENVPATH%;%ENVPATH%\DLLs;%ENVPATH%\Library\bin;%ENVPATH%\Lib;%ENVPATH%\Lib\site-packages
