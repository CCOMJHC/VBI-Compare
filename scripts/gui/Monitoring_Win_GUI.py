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

from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QLabel, QMessageBox, \
    QGroupBox, QTextEdit, QProgressBar, QTabWidget, QHBoxLayout
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QIcon, QCloseEvent, QColor, QTextDocument, QFont
from PyQt5.QtCore import pyqtSignal as Signal
from qgis.core import QgsRasterLayer, QgsRectangle, QgsCoordinateReferenceSystem, QgsCoordinateTransform
from qgis.gui import QgsMapCanvas, QgsRubberBand
from qgis.core import QgsApplication, QgsProject, QgsWkbTypes, QgsPointXY


CRS_WEB_MERCATOR = QgsCoordinateReferenceSystem("EPSG:3857")
CRS_WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")
COORD_XFORM_WGS84_TO_WEB_MERCATOR = QgsCoordinateTransform(CRS_WGS84,
                                                           CRS_WEB_MERCATOR,
                                                           QgsProject.instance().transformContext())
BASEMAP = "url=https://tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png&zmax=19&zmin=0&type=xyz"

# UI element colors
TRACKLINE_COLOR = QColor(255, 0, 127)
MCD_CHART_COLOR = QColor(0, 204, 0)
NBS_TILE_COLOR = QColor(107, 0, 255)
USR_AREA_COLOR = QColor(255, 0, 0)
TTL_AREA_COLOR = QColor(102, 51, 0)


def get_webmercator_coord(pt: QgsPointXY) -> QgsPointXY:
    """
    Transform Web Mercator (EPSG:3857) coordinate to WGS84 (EPSG:4326)
    :param pt: Point in Web Mercator coordinate system
    :return: Point in WGS84 geographic coordinate system
    """
    return COORD_XFORM_WGS84_TO_WEB_MERCATOR.transform(pt)


class PopUpMonitor(QMainWindow):
    """Defines the window for the pup-up process monitor."""

    monitor_closed = Signal()

    def __init__(self, parent):
        QMainWindow.__init__(self, parent)
        version = "1.0"
        self.setWindowTitle(f"VBI Compare v. {version}")
        self.setWindowIcon(QIcon("scripts/gui/media/VBI_Compare.png"))
        # Make Tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.setContentsMargins(0, 0, 0, 0)
        self.tabs.setIconSize(QSize(45, 45))
        self.tabs.setTabPosition(QTabWidget.South)

        # Creates Tab layout
        main_layout = QHBoxLayout()
        group_box = QGroupBox("Process Monitoring")
        layout = QVBoxLayout()

        # QGIS plug in showing selected box, chart outlines, and ship tracks
        # Set this to False even though the QGIS docs say to set to True for GUI apps
        # See: https://gis.stackexchange.com/questions/381006/cant-run-a-standalone-qgis-application-importerror-dll-load-failed
        self.qgs = QgsApplication([], False)

        # Supply the path to the qgis install location
        self.qgs.setPrefixPath("C:/OSGeo4W/apps/qgis", True)

        # load providers
        self.qgs.initQgis()

        map_layout = QHBoxLayout()
        self.canvas = QgsMapCanvas()
        self.canvas.setCanvasColor(Qt.black)
        self.canvas.enableAntiAliasing(True)

        rlayer = QgsRasterLayer(BASEMAP, 'OpenStreetMap', 'wms')
        if not rlayer.isValid():
            print("Layer failed to load!")

        # add layer to the registry
        QgsProject.instance().addMapLayer(rlayer)

        # set Coordinate Reference System
        crs = CRS_WEB_MERCATOR
        QgsProject.instance().setCrs(crs)

        # set extent to the extent of our layer
        self.canvas.setExtent(rlayer.extent())

        # set the map canvas layer
        self.canvas.setLayers([rlayer])
        map_layout.addWidget(self.canvas)
        map_layout.addStretch(True)
        layout.addLayout(map_layout)

        # Map legend
        map_legend = QHBoxLayout()
        legend = QTextEdit()
        legend.setMinimumWidth(600)
        legend.setMaximumHeight(35)
        legend.append('<span style="color:red;font-weight:bold">%s <span style="color:green;font-weight:bold">%s '
                      '<span style="color:purple;font-weight:bold">%s <span style="color:brown;font-weight:bold">%s'
                      ' <span style="color:violet;font-weight:bold">%s'
                      % ("Red- Search Area,", "Green- Chart Area,", "Purple- NBS Tile,",
                         "Brown- Total Tile Area,", "Pink- Vessel Tracklines"))
        legend.setReadOnly(True)
        legend.setAlignment(Qt.AlignCenter)
        map_legend.addWidget(legend)
        map_legend.addStretch(True)
        map_legend.setAlignment(Qt.AlignHCenter)
        layout.addLayout(map_legend)

        # Show Print outputs from Downloader
        printout_layout = QHBoxLayout()
        label = QLabel("Download Status")
        label.setMinimumWidth(99)
        label.setAlignment(Qt.AlignLeft)
        printout_layout.addWidget(label)
        self.printout = QTextEdit()
        self.printout.setMinimumWidth(450)
        self.printout.setMaximumHeight(200)
        self.printout.setLineWrapColumnOrWidth(430)
        self.printout.setLineWrapMode(QTextEdit.FixedPixelWidth)
        self.printout.setReadOnly(True)
        printout_layout.addWidget(self.printout)
        printout_layout.addStretch(True)
        layout.addLayout(printout_layout)

        # Download Status Bar
        progress_layout = QHBoxLayout()
        label = QLabel("Download Progress")
        label.setMinimumWidth(99)
        label.setAlignment(Qt.AlignLeft)
        progress_layout.addWidget(label)
        self.progress = QProgressBar(self)
        self.progress.setMinimumWidth(400)
        progress_layout.addWidget(self.progress)
        progress_layout.addStretch(True)
        layout.addLayout(progress_layout)
        self.total_proc = 0

        # Reputation Calculation Status Bar
        calc_progress_layout = QHBoxLayout()
        label = QLabel("Calc Progress")
        label.setMinimumWidth(99)
        label.setAlignment(Qt.AlignLeft)
        calc_progress_layout.addWidget(label)
        self.calc_prog = QProgressBar(self)
        self.calc_prog.setMinimumWidth(400)
        calc_progress_layout.addWidget(self.calc_prog)
        calc_progress_layout.addStretch(True)
        layout.addLayout(calc_progress_layout)
        self.calc_proc_total = 0

        group_box.setLayout(layout)
        main_layout.addWidget(group_box)

        widget = QWidget()
        widget.setLayout(main_layout)
        self.idx_monitor = self.tabs.insertTab(1, widget, QIcon("scripts/gui/media/Monitor.png"), "")
        self.tabs.setTabToolTip(self.idx_monitor, "Download Monitor")

        self.query_area = 0
        self.total_area = 0
        self.total_tiles_nw_corner: list[QgsPointXY] = []
        self.total_tiles_se_corner: list[QgsPointXY] = []

        self.mQFont = "Sans Serif"
        self.mQFontsize = 9
        self.mLabelQString = "© OpenStreetMap: openstreetmap.org/copyright"
        self.mMarginHorizontal = 0
        self.mMarginVertical = 0
        self.mLabelQColor = "#FF0000"
        # 1 millimeter = 0.0393700787402 inches
        self.inches_to_mm = 0.0393700787402

        # Emitted when the canvas has rendered
        self.canvas.renderComplete.connect(self._on_render_complete)

    def add_copyright(self, p, text, xOffset, yOffset):
        """Places copyright text on GIS Window"""
        p.translate(xOffset, yOffset)
        text.drawContents(p)
        p.setWorldTransform(p.worldTransform())
        self.canvas.refresh()

    def _on_render_complete(self, p):
        """Refreshes GIS window when zooming/ panning"""
        # Get paint device height on which this painter is currently painting
        deviceHeight = p.device().height()
        # Get paint device width on which this painter is currently painting
        deviceWidth = p.device().width()

        # Create new container for structured rich text
        text = QTextDocument()
        font = QFont()
        font.setFamily(self.mQFont)
        font.setPointSize(int(self.mQFontsize))
        text.setDefaultFont(font)
        style = "<style type=\"text/css\"> p {color: " + self.mLabelQColor + "}</style>"
        text.setHtml(style + "<p>" + self.mLabelQString + "</p>")
        # Text Size
        size = text.size()

        # RenderMillimeters
        pixelsInchX = p.device().logicalDpiX()
        pixelsInchY = p.device().logicalDpiY()
        xOffset = pixelsInchX * self.inches_to_mm * int(self.mMarginHorizontal)
        yOffset = pixelsInchY * self.inches_to_mm * int(self.mMarginVertical)

        # Bottom Right
        yOffset = deviceHeight - yOffset - size.height()
        xOffset = deviceWidth - xOffset - size.width()
        self.add_copyright(p, text, xOffset, yOffset)

    def showAreaRect(self, geo_startPoint: str, geo_endPoint: str):
        """Shows the rectangle of the area selected by the use in GIS window"""

        geo_start = list(map(float, geo_startPoint.split(", ")))
        geo_end = list(map(float, geo_endPoint.split(", ")))
        xy_start = QgsPointXY(geo_start[1], geo_start[0])
        xy_end = QgsPointXY(geo_end[1], geo_end[0])
        startPoint = get_webmercator_coord(xy_start)
        endPoint = get_webmercator_coord(xy_end)

        point1 = startPoint
        point2 = QgsPointXY(startPoint.x(), endPoint.y())
        point3 = endPoint
        point4 = QgsPointXY(endPoint.x(), startPoint.y())

        rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        rubberBand.setStrokeColor(USR_AREA_COLOR)
        rubberBand.setOpacity(50.00)
        rubberBand.setWidth(1)

        rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
            return

        rubberBand.addPoint(point1, False)
        rubberBand.addPoint(point2, False)
        rubberBand.addPoint(point3, False)
        rubberBand.addPoint(point4, True)
        rubberBand.show()

        rect = QgsRectangle(startPoint, endPoint)
        self.query_area = rect.area()
        self.canvas.zoomToFeatureExtent(rect)

    def chart_outline(self, chart_outline: list):
        """Shows outlines of MCD Charts in GIS window"""
        xy_start = QgsPointXY(chart_outline[1], chart_outline[0])
        xy_end = QgsPointXY(chart_outline[3], chart_outline[2])
        startPoint = get_webmercator_coord(xy_start)
        endPoint = get_webmercator_coord(xy_end)

        point1 = startPoint
        point2 = QgsPointXY(startPoint.x(), endPoint.y())
        point3 = endPoint
        point4 = QgsPointXY(endPoint.x(), startPoint.y())

        rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        rubberBand.setStrokeColor(MCD_CHART_COLOR)
        rubberBand.setOpacity(50.00)
        rubberBand.setWidth(1)

        rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
            return

        rubberBand.addPoint(point1, False)
        rubberBand.addPoint(point2, False)
        rubberBand.addPoint(point3, False)
        rubberBand.addPoint(point4, True)
        rubberBand.show()

    def tile_outline(self, tile_outline: list):
        """Displays the outline of NBS tiles in the GIS Window"""
        xy_start = QgsPointXY(tile_outline[1], tile_outline[0])
        xy_end = QgsPointXY(tile_outline[3], tile_outline[2])
        startPoint = get_webmercator_coord(xy_start)
        endPoint = get_webmercator_coord(xy_end)
        self.total_tiles_nw_corner.append(startPoint)
        self.total_tiles_se_corner.append(endPoint)

        point1 = startPoint
        point2 = QgsPointXY(startPoint.x(), endPoint.y())
        point3 = endPoint
        point4 = QgsPointXY(endPoint.x(), startPoint.y())

        rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        rubberBand.setStrokeColor(NBS_TILE_COLOR)
        rubberBand.setOpacity(50.00)
        rubberBand.setWidth(1)

        rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
            return

        rubberBand.addPoint(point1, False)
        rubberBand.addPoint(point2, False)
        rubberBand.addPoint(point3, False)
        rubberBand.addPoint(point4, True)
        rubberBand.show()

        nw = list(zip(*self.total_tiles_nw_corner))
        tile_area_nw = QgsPointXY(min(nw[0]), max(nw[1]))
        se = list(zip(*self.total_tiles_se_corner))
        tile_area_se = QgsPointXY(max(se[0]), min(se[1]))

        rect = QgsRectangle(tile_area_nw, tile_area_se)
        self.total_area = rect.area()

    def total_tile_area(self):
        """Determines and shows bounding box containing all NBS tiles collected."""
        nw = list(zip(*self.total_tiles_nw_corner))
        chart_area_nw = QgsPointXY(min(nw[0]), max(nw[1]))
        se = list(zip(*self.total_tiles_se_corner))
        chart_area_se = QgsPointXY(max(se[0]), min(se[1]))

        point1 = chart_area_nw
        point2 = QgsPointXY(chart_area_nw.x(), chart_area_se.y())
        point3 = chart_area_se
        point4 = QgsPointXY(chart_area_se.x(), chart_area_nw.y())

        rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        rubberBand.setStrokeColor(TTL_AREA_COLOR)
        rubberBand.setOpacity(50.00)
        rubberBand.setWidth(3)

        rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        if chart_area_nw.x() == chart_area_se.x() or chart_area_nw.y() == chart_area_se.y():
            return

        rubberBand.addPoint(point1, False)
        rubberBand.addPoint(point2, False)
        rubberBand.addPoint(point3, False)
        rubberBand.addPoint(point4, True)
        rubberBand.show()

        rect = QgsRectangle(chart_area_nw, chart_area_se)
        if self.total_area > self.query_area:
            self.canvas.zoomToFeatureExtent(rect)

    def tracklines(self, trackline: list):
        """Displays vessel tracklines on GIS window"""
        rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        rubberBand.setStrokeColor(QColor(255, 0, 127))
        rubberBand.setWidth(1)
        rubberBand.reset(QgsWkbTypes.LineGeometry)

        count = 1
        while count <= len(trackline):
            for point in trackline:
                geo_point = QgsPointXY(point[0], point[1])
                xy_point = get_webmercator_coord(geo_point)
                if count < len(trackline):
                    rubberBand.addPoint(xy_point, False)
                    count += 1
                elif count == len(trackline):
                    count += 1
                    rubberBand.addPoint(xy_point, True)
                    rubberBand.show()

    def status_update(self, status: str):
        """Prints status updates to text output box"""
        self.printout.append(status)

    def prog_bar_range(self, proc_total: int):
        """Sets the download progress bar range"""
        self.progress.setRange(0, proc_total)
        self.total_proc = proc_total

    def progress_update(self, curr_proc: int):
        """Updates download progress bar each complete step"""
        self.progress.setValue(curr_proc)
        if curr_proc == self.total_proc:
            self.process_complete()

    def calc_bar_range(self, calc_proc_total: int):
        """Sets the calculation progress bar range"""
        self.calc_prog.setRange(0, calc_proc_total)
        self.calc_proc_total = calc_proc_total

    def calc_prog_update(self, calc_curr_proc: int):
        """Updates calculation progress bar each complete step"""
        self.calc_prog.setValue(calc_curr_proc)
        # need to do anything once complete?

    def process_complete(self):
        """Once download process is complete, initiates total area bounding box creation."""
        if self.total_area != 0:
            self.total_tile_area()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Prompts the user to confirm when close request is made. Closes monitor window only."""
        pop_up = QMessageBox(self)
        pop_up.setWindowTitle("End Process?")
        pop_up.setText("Are you sure you wish to end this process?")
        pop_up.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        pop_up.exec_()
        if pop_up.standardButton(pop_up.clickedButton()) == QMessageBox.Yes:
            event.accept()
            self.monitor_closed.emit()
        else:
            event.ignore()
