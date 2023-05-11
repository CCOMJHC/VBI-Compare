# Copyright 2023 Center for Coastal and Ocean Mapping & NOAA-UNH Joint
# Hydrographic Center, University of New Hampshire.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
# OR OTHER DEALINGS IN THE SOFTWARE.

from pathlib import Path
from datetime import datetime
from random import randrange
import os
import subprocess

file_path = os.path.realpath(__file__)
p = Path(file_path)
CSB_HOME = p.parent.parent
ENV_FILE = Path(CSB_HOME / 'scripts' / 'install' / 'activate_env.bat')
TIDE_FILE = Path(CSB_HOME / 'docs' / 'tides' / 'waterlevels-8414888.txt') # TODO will need to update to proper locality per calc
VESEL_FILE = Path(CSB_HOME / 'tests' / 'fixtures' / 'test_platforms.json') # TODO will eventually require a different platforms .json
                                                                        # TODO will need to update this file with more ships


class BatchBuilder:
    """Creates a bach file which executes the reputation calculation programs based on inputs from the
     nbs_dcdb_downloader.
     output: batch file saved in a user specified location, files created during the batch run,
      and plots from the reputation calculation output."""

    def __init__(self, status_update_signal, calc_proc_total_sig, calc_curr_proc_sig):
        self.data_storage: [str] = None
        self.nbs_data: [str] = None
        self.dcdb_data: [str] = None
        self.date_time: [datetime] = None
        self.rdm_num: [str] = None
        self.db_file: [str] = None
        self.obs_rep_file: [str] = None
        self.plot_file: [str] = None
        self.batch_storage: [str] = None
        self.run: [bool] = None
        self.processes_complete = 0
        self.total_processes = 0
        self.status_update_signal = status_update_signal
        self.calc_proc_total_sig = calc_proc_total_sig
        self.calc_curr_proc_sig = calc_curr_proc_sig

    def batch_path(self):
        """Builds folder structure to store the batch file and the outputs of the reputation program the batch runs.
        Unique folders will be made for each run. Contents of the folders will be unique to that run."""

        self.date_time = datetime.now().strftime("%m_%d_%Y_%H%M")
        self.rdm_num = f"{randrange(20000, 99999):5}"
        self.db_file = f"rep_calc_{self.rdm_num}.sqlite"
        self.obs_rep_file = f"reputation_data_{self.rdm_num}.msgpack.bz2"
        self.plot_file = f"rep_plot_{self.rdm_num}.png"
        directory = f"{self.data_storage}/reputation_calcs/rep_calc_{self.date_time}_{self.rdm_num}"
        self.batch_storage = Path(directory)
        is_exists = self.batch_storage.exists()
        if not is_exists:
            Path.mkdir(self.batch_storage, parents=True)

        self.status_update_signal.emit(
            '<p style="color:#000000">%s</p>' % f"Reputation data path: {directory}")
        self.processes_complete += 1
        self.calc_curr_proc_sig.emit(self.processes_complete)

    def build_batch(self):
        """Creates the batch file required to execute a reputation calculation. If the user wants to run the batch,
        initiates the batch execution.
        Output: batch file in the folder created in the batch_path function. """

        if not self.run:
            self.total_processes = 2
            self.calc_proc_total_sig.emit(self.total_processes)
        elif self.run:
            self.total_processes = 3
            self.calc_proc_total_sig.emit(self.total_processes)

        # Create file path for bat file and associated calc files.
        self.batch_path()
        self.status_update_signal.emit(
            '<p style="color:#000000">%s</p>' % f"Building reputation calculation batch file.")

        # Construct batch file
        bat_file = f"CSB_reputation_calc_{self.date_time}_{self.rdm_num}.bat"
        complete_batch_name = f"{self.batch_storage}/{bat_file}"
        exe_file = open(complete_batch_name, "w")
        exe_file.write("%s\n" % "@echo off")
        exe_file.write("%s\n" % f"set AWS_NO_SIGN_REQUEST=YES")
        exe_file.write("%s\n" % f"set DB_Name={self.db_file}")
        exe_file.write("%s\n" % f"call {ENV_FILE}")
        exe_file.write("%s\n" % f"echo Creating sqlite database.")
        exe_file.write("%s\n" % f"call csb createdb -d %DB_Name%")
        exe_file.write("%s\n" % f"if %ERRORLEVEL% == 0 goto :next")
        exe_file.write("%s\n" % f"echo Errors encountered during database creation.  Exited with status: %errorlevel%")
        exe_file.write("%s\n" % f"goto :endofscript")
        exe_file.write("%s\n" % f":next")
        exe_file.write("%s\n" % f"echo Adding vessel data to database")
        exe_file.write("%s\n" % f"call csb loadplatf -d %DB_Name% -f {VESEL_FILE}")
        exe_file.write("%s\n" % f"if %ERRORLEVEL% == 0 goto :next")
        exe_file.write("%s\n" % f"echo Errors encountered while adding vessel data to database.  "
                                f"Exited with status: %errorlevel%")
        exe_file.write("%s\n" % f"goto :endofscript")
        exe_file.write("%s\n" % f":next")
        exe_file.write("%s\n" % f"echo Adding CSB data to database.")
        exe_file.write("%s\n" % f"call csb loadobscsv -d %DB_Name% -r {self.dcdb_data}")
        exe_file.write("%s\n" % f"if %ERRORLEVEL% == 0 goto :next")
        exe_file.write("%s\n" % f"echo Errors encountered during while adding CSB data to database.  "
                                f"Exited with status: %errorlevel%")
        exe_file.write("%s\n" % f"goto :endofscript")
        exe_file.write("%s\n" % f":next")
        exe_file.write("%s\n" % f"echo Adding authoritative data to database.")
        exe_file.write("%s\n" % f"call csb loadrefs -d %DB_Name% -r {self.nbs_data}")
        exe_file.write("%s\n" % f"if %ERRORLEVEL% == 0 goto :next")
        exe_file.write("%s\n" % f"echo Errors encountered while adding Authoritative data to database."
                                f"  Exited with status: %errorlevel%")
        exe_file.write("%s\n" % f"goto :endofscript")
        exe_file.write("%s\n" % f":next")
        exe_file.write("%s\n" % f"echo Matching CSB to Authoritative data.")
        exe_file.write("%s\n" % f"call csb matchrefs -d %DB_Name%")
        exe_file.write("%s\n" % f"if %ERRORLEVEL% == 0 goto :next")
        exe_file.write("%s\n" % f"echo Errors encountered during matchrefs.  Exited with status: %errorlevel%")
        exe_file.write("%s\n" % f"goto :endofscript")
        exe_file.write("%s\n" % f":next")
        exe_file.write("%s\n" % f"call csb matchobs -d %DB_Name% -f matched_obs_{self.rdm_num}.parquet")
        exe_file.write("%s\n" % f"if %ERRORLEVEL% == 0 goto :next")
        exe_file.write("%s\n" % f"echo Errors encountered during matchobs.  Exited with status: %errorlevel%")
        exe_file.write("%s\n" % f"goto :endofscript")
        exe_file.write("%s\n" % f":next")
        exe_file.write("%s\n" % f"echo Calculating CSB biases.")
        exe_file.write("%s\n" % f"call csb detbiases -m matched_obs_{self.rdm_num}.parquet "
                                f"-p {VESEL_FILE} "
                                f"-w {TIDE_FILE} "
                                f"-o biases_{self.rdm_num}.msgpack.bz2 "
                                f"--required_depth_range 1.0")  # TODO 1.0 used due to depth of water. May not be correct for all situations. More study necessary.
        exe_file.write("%s\n" % f"if %ERRORLEVEL% == 0 goto :next")
        exe_file.write("%s\n" % f"echo Errors encountered while calculating biases.  Exited with status: %errorlevel%")
        exe_file.write("%s\n" % f"goto :endofscript")
        exe_file.write("%s\n" % f":next")
        exe_file.write("%s\n" % f"echo Calculating uncertainties.")
        exe_file.write("%s\n" % f"call csb detuncrt -d biases_{self.rdm_num}.msgpack.bz2 "
                                f"-o uncertainties_{self.rdm_num}.msgpack.bz2")
        exe_file.write("%s\n" % f"if %ERRORLEVEL% == 0 goto :next")
        exe_file.write("%s\n" % f"echo Errors encountered while calculating uncertainties."
                                f"  Exited with status: %errorlevel%")
        exe_file.write("%s\n" % f"goto :endofscript")
        exe_file.write("%s\n" % f":next")
        exe_file.write("%s\n" % f"echo Calculating reputation.")
        exe_file.write("%s\n" % f"call csb detrep -d biases_{self.rdm_num}.msgpack.bz2 "
                                f"-u uncertainties_{self.rdm_num}.msgpack.bz2"
                                f" -o {self.obs_rep_file}")
        exe_file.write("%s\n" % f"if %ERRORLEVEL% == 0 goto :next")
        exe_file.write("%s\n" % f"echo Errors encountered while calculating biases.  Exited with status: %errorlevel%")
        exe_file.write("%s\n" % f"goto :endofscript")
        exe_file.write("%s\n" % f":next")
        exe_file.write("%s\n" % f"echo Creating Data Plots.")
        # Due to conflict between QGIS Python used to run VBI Compare and the Conda Python used to run the reputation
        # calculation, creation of the reputation plot using matplotlib, which requires Qt graphics libraries, the
        # repplot step does not work currently. This should be resolved when VBI Compare is properly integrated into
        # a Python environment such as Pydro.
        exe_file.write("%s\n" % f"REM call csb repplot -d {self.db_file} -r {self.obs_rep_file} "
                                f"-o {self.batch_storage}/{self.plot_file}")
        exe_file.write("%s\n" % f"if %ERRORLEVEL% == 0 goto :next")
        exe_file.write("%s\n" % f"echo Errors encountered while calculating biases.  Exited with status: %errorlevel%")
        exe_file.write("%s\n" % f"goto :endofscript")
        exe_file.write("%s\n" % f":next")
        exe_file.write("%s\n" % f":endofscript")
        exe_file.write("%s\n" % f"echo Reputation Calculation Complete.")
        exe_file.close()

        self.processes_complete += 1
        self.calc_curr_proc_sig.emit(self.processes_complete)

        if self.run:
            self.status_update_signal.emit(
                '<p style="color:#11B01A">%s</p>' % f"{bat_file} created at {str(self.batch_storage)}.")
            self.exe_batch(complete_batch_name)
        else:
            self.processes_complete = self.total_processes
            self.calc_curr_proc_sig.emit(self.processes_complete)
            self.status_update_signal.emit(
                '<p style="color:#11B01A">%s</p>' % f"{bat_file} stored at {str(self.batch_storage)}.")
            self.status_update_signal.emit('<p style="color:#1C5BC2">%s</p>' % f"Requested process complete.")

    def exe_batch(self, batchfile):
        """If the user as elected to run the batch file, executes the file.
        output: files created during reputation calculation."""

        self.status_update_signal.emit('<p style="color:#000000">%s</p>' % f"Executing reputation calculation."
                                                                           f"This may take several minutes.")

        with subprocess.Popen([batchfile], stdout=subprocess.PIPE, bufsize=1, universal_newlines=True,
                              cwd=self.batch_storage) as proc:
            for line in proc.stdout:
                if line[0:7] == "WARNING":
                    self.status_update_signal.emit('<p style="color:#CCA70E">%s</p>' % f"{line}")
                elif (line[0:5] == "ERROR") or (line[0:6] == "Errors"):
                    self.status_update_signal.emit('<p style="color:#CF0D04">%s</p>' % f"{line}")
                    self.status_update_signal.emit('<p style="color:#CF0D04">%s</p>' % f"Calculation Failed")
                else:
                    self.status_update_signal.emit('<p style="color:#000000">%s</p>' % f"{line}")
            proc.poll()
            # TODO remove this once tested/ repaired.
            print(proc.returncode)

        if proc.returncode == 0:
            self.processes_complete = self.total_processes
            self.calc_curr_proc_sig.emit(self.processes_complete)
            self.status_update_signal.emit(
                '<p style="color:#1C5BC2">%s</p>' % f"Calculation Complete. Files located at {str(self.batch_storage)}")
            self.status_update_signal.emit('<p style="color:#1C5BC2">%s</p>' % f"Requested process complete.")

        elif proc.returncode != 0:
            self.processes_complete = self.total_processes
            self.calc_curr_proc_sig.emit(self.processes_complete)
            err = proc.stderr
            self.status_update_signal.emit('<p style="color:#CF0D04">%s</p>' % f"Calculation Failed: {err}")
            self.status_update_signal.emit('<p style="color:#1C5BC2">%s</p>' % f"Requested process complete.")
