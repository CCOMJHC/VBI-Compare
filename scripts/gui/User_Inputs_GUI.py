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

import sip
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, \
    QPushButton, QListWidget, QFileDialog, QMessageBox, \
    QGroupBox, QGridLayout, QRadioButton, QLineEdit, QDialog
from PyQt5.QtCore import QSize, Qt, QSettings, QObject, QThread
from PyQt5.QtCore import pyqtSignal as Signal
from PyQt5.QtCore import pyqtSlot as Slot
from scripts.nbs_dcdb_downloader import DataDownload
from Monitoring_Win_GUI import PopUpMonitor  # Monitor
from Area_Search_GUI import GISWin  # Area Selection


class Worker(QObject):
    """Creates a worker thread for parallel processing of GUI and nbs_dcdb_downloader"""
    finished = Signal()

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        self.fn()
        self.finished.emit()
        self.finished.disconnect()


class UserInputs(QMainWindow):
    """
    Defines the guts to the main GUI window and the various functions controlled by it.
    Starts the download tool on 'run' and initiates a pop-up process monitoring window."""

    # Signals for sending downloader status updates to monitor window
    status_update_signal: Signal = Signal((str,))
    total_proc_signal: Signal = Signal((int,))
    curr_proc_signal: Signal = Signal((int,))
    chart_outline_signal: Signal = Signal((list,))
    tile_outline_signal: Signal = Signal((list,))
    trackline_signal: Signal = Signal((list,))
    nw_corner_signal: Signal = Signal((str,))
    se_corner_signal: Signal = Signal((str,))
    calc_proc_total_sig: Signal = Signal((int,))
    calc_curr_proc_sig: Signal = Signal((int,))

    def __init__(self, parent):
        QMainWindow.__init__(self, parent)
        main_layout = QHBoxLayout()
        group_box = QGroupBox("User Inputs")

        layout = QVBoxLayout()

        # Check boxes
        grid = QGridLayout()

        primary_source = QGroupBox("Select your primary data source")
        self.ps_radio1 = QRadioButton("National Bathy Source")
        self.ps_radio2 = QRadioButton("DCDB Crowdsourced Bathy")
        hbox = QHBoxLayout()
        hbox.addWidget(self.ps_radio1)
        hbox.addWidget(self.ps_radio2)
        hbox.addStretch(1)
        primary_source.setLayout(hbox)
        grid.addWidget(primary_source, 0, 0)
        self.ps_radio1.toggled.connect(self.specific_charts)
        self.ps_radio2.toggled.connect(self.specific_vessels)

        secondary_source = QGroupBox("Get secondary data based on primary?")
        self.ss_radio1 = QRadioButton("Yes")
        self.ss_radio2 = QRadioButton("No")
        hbox = QHBoxLayout()
        hbox.addWidget(self.ss_radio1)
        hbox.addWidget(self.ss_radio2)
        hbox.addStretch(1)
        secondary_source.setLayout(hbox)
        grid.addWidget(secondary_source, 1, 0)
        self.ss_radio1.toggled.connect(self.rep)

        processing_method = QGroupBox("What data collection method is preferred?")
        self.pm_radio1 = QRadioButton("Compile S3 URLs")
        self.pm_radio2 = QRadioButton("Download Resources Locally")
        hbox = QHBoxLayout()
        hbox.addWidget(self.pm_radio1)
        hbox.addWidget(self.pm_radio2)
        hbox.addStretch(1)
        processing_method.setLayout(hbox)
        grid.addWidget(processing_method, 1, 1)

        input_method = QGroupBox("Data Search Method")
        self.im_radio1 = QRadioButton("Specific Vessels")
        self.im_radio2 = QRadioButton("Specific Charts")
        self.im_radio3 = QRadioButton("Area Search")
        self.im_radio1.setCheckable(False)
        self.im_radio2.setCheckable(False)
        self.im_radio3.setCheckable(False)
        self.im_radio1.setStyleSheet("QRadioButton{background-color : lightgray}")
        self.im_radio2.setStyleSheet("QRadioButton{background-color : lightgray}")
        self.im_radio3.setStyleSheet("QRadioButton{background-color : lightgray}")
        hbox = QHBoxLayout()
        hbox.addWidget(self.im_radio1)
        hbox.addWidget(self.im_radio2)
        hbox.addWidget(self.im_radio3)
        hbox.addStretch(1)
        input_method.setLayout(hbox)
        grid.addWidget(input_method, 0, 1)
        self.im_radio1.toggled.connect(self.vessels)
        self.im_radio2.toggled.connect(self.charts)
        self.im_radio3.toggled.connect(self.area)

        layout.addLayout(grid)

        # Add "Area Search" button and corner displays.
        area_search_layout = QHBoxLayout()
        self.area_search_button = QPushButton("Select Area")
        self.area_search_button.setFixedSize(100, 35)
        self.area_search_button.setDisabled(True)
        area_search_layout.addWidget(self.area_search_button, Qt.AlignLeft)
        self.area_search_button.clicked.connect(self.area_search)
        layout.addLayout(area_search_layout)

        label = QLabel("Or Type: NW Corner")
        label.setMinimumWidth(60)
        label.setAlignment(Qt.AlignLeft)
        area_search_layout.addWidget(label)
        self.nw_corner_box = QLineEdit()
        self.nw_corner_box.setMinimumWidth(100)
        self.nw_corner_box.setReadOnly(True)
        self.nw_corner_box.setPlaceholderText("ex: 43.00, -69.00")
        area_search_layout.addWidget(self.nw_corner_box)

        label = QLabel("SE Corner")
        label.setMinimumWidth(60)
        label.setAlignment(Qt.AlignLeft)
        area_search_layout.addWidget(label)
        self.se_corner_box = QLineEdit()
        self.se_corner_box.setMinimumWidth(100)
        self.se_corner_box.setReadOnly(True)
        self.se_corner_box.setPlaceholderText("ex: 41.00, -67.00")
        area_search_layout.addWidget(self.se_corner_box)

        # Specific Vessels
        vessels_layout = QHBoxLayout()
        label = QLabel("List Desired Vessels:")
        label.setMinimumWidth(99)
        label.setAlignment(Qt.AlignLeft)
        vessels_layout.addWidget(label)
        self.vessel_box = QLineEdit()
        self.vessel_box.setMinimumWidth(500)
        self.vessel_box.setPlaceholderText("ex: Copper Star, Tapestry")
        self.vessel_box.setDisabled(True)
        vessels_layout.addWidget(self.vessel_box)
        vessels_layout.addStretch(True)
        layout.addLayout(vessels_layout)

        # Specific Chart List
        charts_layout = QHBoxLayout()
        label = QLabel("List Desired Charts:")
        label.setMinimumWidth(99)
        label.setAlignment(Qt.AlignLeft)
        charts_layout.addWidget(label)
        self.chart_box = QLineEdit()
        self.chart_box.setMinimumWidth(500)
        self.chart_box.setPlaceholderText("ex: US3MA1AC, US3MA1BF")
        self.chart_box.setDisabled(True)
        charts_layout.addWidget(self.chart_box)
        charts_layout.addStretch()
        layout.addLayout(charts_layout)

        # add an output location
        output_location_layout = QHBoxLayout()
        label = QLabel("Output Directory:")
        output_location_layout.addWidget(label)
        label.setMinimumWidth(99)
        self.output_folder = QListWidget()
        self.output_folder.setMaximumHeight(100)
        output_location_layout.addWidget(self.output_folder)
        file_buttons = QVBoxLayout()
        output_location_layout.addLayout(file_buttons)
        self.button_add_output = QPushButton("...")
        self.button_add_output.setToolTip("Navigate to output location.")
        file_buttons.addWidget(self.button_add_output)
        self.button_add_output.clicked.connect(self.click_add_output_folder)

        layout.addLayout(output_location_layout)

        # Run Reputation Calculation Query
        rep_layout = QHBoxLayout()
        run_rep = QGroupBox("Run Reputation Calculation?")
        run_rep.setMaximumHeight(100)
        run_rep.setMaximumWidth(200)
        self.rep_radio1 = QRadioButton("Yes")
        self.rep_radio2 = QRadioButton("No")
        self.rep_radio1.setCheckable(False)
        self.rep_radio2.setChecked(True)
        hbox = QHBoxLayout()
        hbox.addWidget(self.rep_radio1, Qt.AlignCenter)
        hbox.addWidget(self.rep_radio2, Qt.AlignCenter)
        hbox.addStretch(1)
        run_rep.setLayout(hbox)
        rep_layout.addWidget(run_rep)
        layout.addLayout(rep_layout, Qt.AlignCenter)

        # Add "Clear Data" button.
        clear_button_layout = QHBoxLayout()
        clear_data_button = QPushButton("Clear Data")
        clear_data_button.setFixedSize(100, 35)
        clear_button_layout.addWidget(clear_data_button, Qt.AlignCenter)
        clear_data_button.clicked.connect(self.click_clear_data)

        layout.addLayout(clear_button_layout)

        # Add "Run" button.
        run_button_layout = QHBoxLayout()
        run_data_button = QPushButton("Run!")
        run_data_button.setFixedSize(100, 75)
        run_button_layout.addWidget(run_data_button, Qt.AlignRight)
        run_data_button.clicked.connect(self.click_run)

        layout.addLayout(run_button_layout)

        group_box.setLayout(layout)
        main_layout.addWidget(group_box)

        widget = QWidget()
        widget.setLayout(main_layout)
        self.setCentralWidget(widget)

        self.popupmonitor = None
        self.popuparea = None
        self.worker = None
        self.thread = None

    def specific_charts(self, selected):
        """Sets initial check value, checkability, and background color for specific charts radial"""
        if selected:
            self.im_radio2.setCheckable(True)
            self.im_radio3.setCheckable(True)
            self.im_radio2.setStyleSheet("QRadioButton{background-color : lightgreen}")
            self.im_radio3.setStyleSheet("QRadioButton{background-color : lightgreen}")
            self.im_radio1.setChecked(False)
            self.im_radio1.setCheckable(False)
            self.im_radio1.setStyleSheet("QRadioButton{background-color : lightgray}")
        else:
            self.im_radio2.setChecked(False)

    def specific_vessels(self, selected):
        """Sets initial check value, checkability, and background color for specific vessels radial"""
        if selected:
            self.im_radio1.setCheckable(True)
            self.im_radio3.setCheckable(True)
            self.im_radio1.setStyleSheet("QRadioButton{background-color : lightgreen}")
            self.im_radio3.setStyleSheet("QRadioButton{background-color : lightgreen}")
            self.im_radio2.setChecked(False)
            self.im_radio2.setCheckable(False)
            self.im_radio2.setStyleSheet("QRadioButton{background-color : lightgray}")
        else:
            self.im_radio1.setChecked(False)

    def vessels(self, selected):
        """Determines availability of specific vessel input box. Clears chart input if vessel input is selected"""
        if selected:
            self.vessel_box.setEnabled(True)
            self.chart_box.clear()
            self.chart_box.setDisabled(True)
        else:
            self.vessel_box.clear()
            self.vessel_box.setDisabled(True)

    def charts(self, selected):
        """Determines availability of specific charts input box. Clears vessel input if vessel input is selected"""
        if selected:
            self.chart_box.setEnabled(True)
            self.vessel_box.clear()
            self.vessel_box.setDisabled(True)
        else:
            self.chart_box.clear()
            self.chart_box.setDisabled(True)

    def area(self, selected):
        """Determines availability of Area search tool. Clears vessel and chart input boxes if area is used"""
        if selected:
            self.area_search_button.setEnabled(True)
            self.nw_corner_box.setReadOnly(False)
            self.se_corner_box.setReadOnly(False)
            self.vessel_box.clear()
            self.vessel_box.setDisabled(True)
            self.chart_box.clear()
            self.chart_box.setDisabled(True)
        else:
            self.area_search_button.setDisabled(True)
            self.nw_corner_box.clear()
            self.se_corner_box.clear()

    def area_search(self):
        """Connects slots and signals to area selection tool. Initiates Area Search GUI. Passes existing area
         coordinates to Area Search GUI if available."""
        self.nw_corner_signal.connect(self.nw_corner)
        self.se_corner_signal.connect(self.se_corner)
        curr_nw = self.nw_corner_box.text()
        curr_se = self.se_corner_box.text()

        if curr_nw != '' or curr_se != '':
            valid = self.typed_area_validate(curr_nw, curr_se)
            if not valid:
                return

        self.popuparea = GISWin(self, self.nw_corner_signal, self.se_corner_signal, curr_nw, curr_se)

        self.popuparea.show()

    def nw_corner(self, nw_corner: str):
        """Clears current NW corner bounds and inserts new from Area Search GUI."""
        self.nw_corner_box.clear()
        self.nw_corner_box.insert(nw_corner)

    def se_corner(self, se_corner: str):
        """Clears current SE corner bounds and inserts new from Area Search GUI."""
        self.se_corner_box.clear()
        self.se_corner_box.insert(se_corner)

    def typed_area_validate(self, typed_nw, typed_se):
        """Validates the syntax of typed coordinates in the NW/ SE area search boxes. Creates pop up warning if
        input does not match requirements."""

        # Validate typed inputs
        messages = list()
        try:
            self.geo_start = list(map(float, typed_nw.split(", ")))
        except:
            self.geo_start = []
            messages.append("Format Error in the NW point. Please update and retry.")

        try:
            self.geo_end = list(map(float, typed_se.split(", ")))
        except:
            self.geo_end = []
            messages.append("Format Error in the NW point. Please update and retry.")

        if (len(self.geo_start) != 2) or (len(self.geo_end) != 2) or len(messages) > 0:
            pop_up = QMessageBox(self)
            pop_up.setWindowTitle("Coordinate Error.")
            pop_up.setText("Coordinates are missing information or formatted incorrectly for one or more points. "
                           "Please review and retry. ex: 43.00, -69.00")
            pop_up.exec_()
            return False

        if len(self.geo_start) == 2:
            if self.geo_start[0] > 90 or self.geo_start[0] < -90:
                messages.append("NW point latitude is out of range. Latitude must be between 90 and -90")
            if self.geo_start[1] > 180 or self.geo_start[1] < -180:
                messages.append("NW point longitude is out of bounds. Longitude must be between 180 and -180")

        if len(self.geo_end) == 2:
            if self.geo_end[0] > 90 or self.geo_end[0] < -90:
                messages.append("SE point latitude is out of range. Latitude must be between 90 and -90")
            if self.geo_end[1] > 180 or self.geo_end[1] < -180:
                messages.append("SE point longitude is out of bounds Longitude must be between 180 and -180")

        if len(messages) > 0:
            pop_up = QMessageBox(self)
            pop_up.setWindowTitle("Coordinate Error.")
            pop_up.setText("There is an error with the provided coordinates. Please review and retry.")
            pop_up.setDetailedText(str(messages))
            pop_up.exec_()
            return False
        return True

    def click_add_output_folder(self):
        """Provides a pop up for the user to input their desired output location. Prompts warning messages if
        location address is malformed."""

        self.output_folder.clear()

        selection = QFileDialog.getExistingDirectory(self, "Set output folder",
                                                     QSettings().value("data_download_folder"), )

        # create error message window
        def error_window(message):
            dialog_window = QMessageBox(self)
            dialog_window.setWindowTitle("There is a problem.")
            dialog_window.setText(message)
            dialog_window.exec_()

        # check for a space in the file grid names.
        if " " in selection:
            message = "Please check both filename or filepath to remove any spaces or hyphens and rerun script.."
            error_window(message)
            print(message)
            selection = ""

        if selection == "":
            return
        else:
            self.output_folder.addItem(selection)

    def rep(self, selected):
        """Sets initial state for Run reputation selections."""
        if selected:
            self.rep_radio1.setCheckable(True)
            self.rep_radio2.setCheckable(True)
        else:
            self.rep_radio1.setChecked(False)
            self.rep_radio1.setCheckable(False)
            self.rep_radio2.setChecked(True)

    def click_clear_data(self):
        """Clears data inputs if Clear Data button is clicked. Does not affect radial selections."""

        self.output_folder.clear()
        self.vessel_box.clear()
        self.chart_box.clear()
        self.nw_corner_box.clear()
        self.se_corner_box.clear()

    def click_run(self):
        """Initial validation of input data is completed upon clicking run button. Error messages are collected.
        If validation fails, an error pop up is displayed showing the necessary fixes. If validation passes, establishes
        slots/ signals to monitor window and nbs_dcdb_downloader. Also initiates worker thread for parallel
        processing"""

        # create list for error messages for missing items.
        messages = list()

        # validation
        # Throw an error if desired vessels is empty and specific vessels is checked.
        if self.vessel_box.text() == '' and self.im_radio1.isChecked():
            messages.append("Error! Specific Vessel search selected. Please provide vessel list!")
        # Throw an error if desired charts is empty and specific charts is checked.
        if self.chart_box.text() == '' and self.im_radio2.isChecked():
            messages.append("Error!: Specific Charts search selected. Please provide chart list!")
        # Throw an error if area search is selected, but area is not valid.
        if self.im_radio3.isChecked():
            valid = self.typed_area_validate(self.nw_corner_box.text(), self.se_corner_box.text())
            if not valid:
                messages.append("Error!: Please provide a valid search area!")
        # Throw an error if output is empty.
        if self.output_folder.count() == 0:
            messages.append("Error!: Please select an output folder location!")
        elif self.output_folder.count() > 1 and self.pm_radio2.isChecked():
            messages.append("Error!: Too many output folder locations selected!")
        # Throw an error if primary data source is not selected
        if not self.ps_radio1.isChecked() and not self.ps_radio2.isChecked():
            messages.append("Error!: Please select a primary data source!")
        # Throw an error if no search method is selected.
        if not self.im_radio1.isChecked() and not self.im_radio2.isChecked() and not self.im_radio3.isChecked():
            messages.append("Error!: Please select a data search method!")
        # Throw an error if desire for secondary data is not selected
        if not self.ss_radio1.isChecked() and not self.ss_radio2.isChecked():
            messages.append("Error!: Please indicate if secondary data is needed!")
        # Throw an error if data collection method is not selected
        if not self.pm_radio1.isChecked() and not self.pm_radio2.isChecked():
            messages.append("Error!: Please indicate the data collection method desired!")
        # Throw an error if desire to run reputation is not selected
        if not self.rep_radio1.isChecked() and not self.rep_radio2.isChecked():
            messages.append("Error!: Please indicate if the reputation calculation is to be executed.")

        # If validation fails, show message box.
        if len(messages) > 0:
            pop_up = QMessageBox(self)
            pop_up.setWindowTitle("There is a problem.")
            pop_up.setText("There are %s issues with the given inputs. See below for details." % (len(messages)))
            pop_up.setDetailedText(str(messages))
            pop_up.exec_()
            return

        # If Validation passes, start the downloader
        # Pop Up Monitor
        self.popupmonitor = PopUpMonitor(self)
        # Register signals with slots to send status to monitor
        self.status_update_signal.connect(self.popupmonitor.status_update)
        self.total_proc_signal.connect(self.popupmonitor.prog_bar_range)
        self.curr_proc_signal.connect(self.popupmonitor.progress_update)
        self.chart_outline_signal.connect(self.popupmonitor.chart_outline)
        self.tile_outline_signal.connect(self.popupmonitor.tile_outline)
        self.trackline_signal.connect(self.popupmonitor.tracklines)
        self.calc_proc_total_sig.connect(self.popupmonitor.calc_bar_range)
        self.calc_curr_proc_sig.connect(self.popupmonitor.calc_prog_update)

        if self.nw_corner_box.text() != '':
            self.popupmonitor.showAreaRect(self.nw_corner_box.text(), self.se_corner_box.text())

        self.popupmonitor.setFixedSize(QSize(650, 850))
        self.popupmonitor.show()

        self.thread = QThread()
        self.worker = Worker(self.start_downloader)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def start_downloader(self):
        """Creates instance of the downloader tool and provides all user input data to the downloader."""

        # Create downloader instance
        downloader = DataDownload(self.status_update_signal,
                                  self.total_proc_signal,
                                  self.curr_proc_signal,
                                  self.chart_outline_signal,
                                  self.tile_outline_signal,
                                  self.trackline_signal,
                                  self.calc_proc_total_sig,
                                  self.calc_curr_proc_sig)
        # Register with monitor's signal that will indicate when the monitor is closed.
        self.popupmonitor.monitor_closed.connect(self.close_monitor)

        # set values in downloader from radio buttons
        # primary source Todo Make these Enum values
        if self.ps_radio1.isChecked():
            downloader.data_source = "nbs"
        elif self.ps_radio2.isChecked():
            downloader.data_source = "dcdb"

        # download secondary?
        if self.ss_radio1.isChecked():
            downloader.get_charts = True
            downloader.get_csb = True
            downloader.both_data = True
        elif self.ss_radio2.isChecked():
            downloader.get_charts = False
            downloader.get_csb = False
            downloader.both_data = False

        #  processing method
        if self.pm_radio1.isChecked():
            downloader.process = "c"
        elif self.pm_radio2.isChecked():
            downloader.process = "l"

        # input method
        if self.im_radio1.isChecked() or self.im_radio2.isChecked():
            downloader.search_type = "s"
        elif self.im_radio3.isChecked():
            downloader.search_type = "b"

        # add list of charts to downloader
        if self.chart_box.text() != '':
            chartbox_input = self.chart_box.text()
            chart_list = list(map(lambda x: x.upper(), chartbox_input.split(", ")))
            downloader.charts = chart_list
        else:
            downloader.charts = []

        # add list of vessels to downloader
        if self.vessel_box.text() != '':
            vesselbox_input = self.vessel_box.text()
            vessel_list = list(map(lambda x: x.upper(), vesselbox_input.split(", ")))
            downloader.platform = vessel_list
        else:
            downloader.platform = []

        # add output folder to downloader
        if self.output_folder.count() == 1:
            output_folder = self.output_folder.item(0).text()
            downloader.data_storage = output_folder
        else:
            downloader.data_storage = None

        # send NW/ SE corners to downloader
        if self.nw_corner_box.text() != '':
            nw_corner_input = self.nw_corner_box.text()
            nw_corner_list = list(map(float, nw_corner_input.split(", ")))
            downloader.nw_corner = [nw_corner_list]
            se_corner_input = self.se_corner_box.text()
            se_corner_list = list(map(float, se_corner_input.split(", ")))
            downloader.se_corner = [se_corner_list]

        # complete reputation selection to downloader
        if self.rep_radio1.isChecked():
            downloader.run_rep = True
        elif self.rep_radio2.isChecked():
            downloader.run_rep = False

        # Start downloader
        downloader.execute()

    @Slot()
    def close_monitor(self):
        """Closes process, disconnects slots/ signals, resets program when the user closes the monitor."""
        if not sip.isdeleted(self.thread) and self.thread.isFinished() is False:
            self.thread.terminate()
            term_pop_up = QDialog(self)
            term_pop_up.setWindowTitle("Terminating Process!")
            layout = QVBoxLayout()
            warning = QLabel('<p style="color:#CF0D04;font-weight:bold">%s</p>'
                             % "Process has been terminated at user request!")
            layout.addWidget(warning)
            term_pop_up.setLayout(layout)
            term_pop_up.show()
            return

        # Disconnect signals
        self.status_update_signal.disconnect(self.popupmonitor.status_update)
        self.total_proc_signal.disconnect(self.popupmonitor.prog_bar_range)
        self.curr_proc_signal.disconnect(self.popupmonitor.progress_update)
        self.chart_outline_signal.disconnect(self.popupmonitor.chart_outline)
        self.tile_outline_signal.disconnect(self.popupmonitor.tile_outline)
        self.trackline_signal.disconnect(self.popupmonitor.tracklines)
        self.calc_curr_proc_sig.disconnect(self.popupmonitor.calc_prog_update)
        self.calc_proc_total_sig.disconnect(self.popupmonitor.calc_bar_range)

        # Destroy monitor so that a new one can be created when the run button is clicked again
        del self.popupmonitor
        self.popupmonitor = None

        self.thread = None
        self.worker = None

        # import pdb;
        # pdb.set_trace()  # Debugger
