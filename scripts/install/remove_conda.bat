@echo off
rem Get absolute path where csb-python repo was checked out to
set REL_CSB_ROOT=%~dp0\..\..\
set CSB_ROOT=
pushd %REL_CSB_ROOT%
set CSB_ROOT=%CD%
popd

echo Script path: %CD%
echo CSB root: %CSB_ROOT%

rem Remove miniconda from %CSB_ROOT%

set MINICONDAPATH=%CSB_ROOT%\Miniconda3
start /wait /min "Removing Miniconda3..." %MINICONDAPATH%\Uninstall-Miniconda3.exe /S
rem If we don't run the next line, CMD.exe will fail to load after installation
C:\Windows\System32\reg.exe DELETE "HKCU\Software\Microsoft\Command Processor" /v AutoRun /f

rem Remove init_conda.bat
del "%~dp0\init_conda.bat"
