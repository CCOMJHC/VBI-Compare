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

import sys
import os
import webbrowser
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QToolBar, QAction, QTabWidget
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QIcon, QCloseEvent
from User_Inputs_GUI import UserInputs


class MainWindow(QMainWindow):
    """Defines the main window for the control GUI of VBI Compare."""
    def __init__(self):
        super().__init__()

        version = "1.0"

        self.setWindowTitle("VBI Compare v. %s" % version)
        self.setWindowIcon(QIcon("scripts/gui/media/VBI_Compare.png"))

        self.setFixedSize(QSize(700, 900))

        # toolbar for manual
        toolbar = QToolBar("Main toolbar")
        toolbar.setIconSize(QSize(30, 30))
        self.addToolBar(toolbar)

        manual_button = QAction(QIcon("scripts/gui/media/manual.png"), "Open Manual", self)
        manual_button.triggered.connect(self.open_manual)
        toolbar.addAction(manual_button)

        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.layout().setSpacing(20)
        toolbar.layout().setContentsMargins(0, 0, 0, 0)

        # Make Tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.setContentsMargins(0, 0, 0, 0)
        self.tabs.setIconSize(QSize(45, 45))
        self.tabs.setTabPosition(QTabWidget.South)

        # User Input Tab
        self.user_input = UserInputs(self)
        self.idx_user_input = self.tabs.insertTab(1, self.user_input, QIcon("scripts/gui/media/scales.png"), "")
        self.tabs.setTabToolTip(self.idx_user_input, "User Inputs")

    def open_manual(self):
        """Opens locally stored User Manual html document in web browser"""
        script_location = os.getcwd()
        manual_location = os.path.join(script_location, "scripts/gui/manual/", "VBI_Compare_Manual.pdf")
        webbrowser.open(manual_location)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Confirms closure request from user and exits the program closing all GUI and processes."""
        pop_up = QMessageBox(self)
        pop_up.setWindowTitle("Close?")
        pop_up.setText("Are you sure you wish to close VBI Compare?")
        pop_up.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        pop_up.exec_()
        if pop_up.standardButton(pop_up.clickedButton()) == QMessageBox.Yes:
            exit()
        else:
            event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    app.exec_()