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

# If the error on line 25 is encountered, un-comment line 24:
# from PyQt5.QtWidgets import QApplication, QFrame, QGridLayout, QMainWindow
# ImportError: DLL load failed while importing QtWidgets: The specified module could not be found.
import sys

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QIcon, QCloseEvent, QColor, QTextDocument, QFont
from PyQt5.QtWidgets import QApplication, QMainWindow, QAction, QToolBar, QTabWidget, QHBoxLayout, QGroupBox, \
    QVBoxLayout, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox
from qgis.core import QgsRasterLayer, QgsRectangle, QgsCoordinateReferenceSystem, QgsCoordinateTransform
from qgis.gui import QgsMapToolZoom, QgsMapToolPan, QgsMapToolEmitPoint, QgsMapTool
from qgis.gui import QgsMapCanvas, QgsRubberBand
from qgis.core import QgsApplication, QgsPoint, QgsProject, QgsWkbTypes, QgsPointXY


CRS_WEB_MERCATOR = QgsCoordinateReferenceSystem("EPSG:3857")
CRS_WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")
COORD_XFORM_WEB_MERCATOR_TO_WGS84 = QgsCoordinateTransform(CRS_WEB_MERCATOR,
                                                           CRS_WGS84,
                                                           QgsProject.instance().transformContext())
COORD_XFORM_WGS84_TO_WEB_MERCATOR = QgsCoordinateTransform(CRS_WGS84,
                                                           CRS_WEB_MERCATOR,
                                                           QgsProject.instance().transformContext())


def get_WGS84_coord(pt: QgsPointXY) -> QgsPointXY:
    """
    Transform Web Mercator (EPSG:3857) coordinate to WGS84 (EPSG:4326)
    :param pt: Point in Web Mercator coordinate system
    :return: Point in WGS84 geographic coordinate system
    """
    return COORD_XFORM_WEB_MERCATOR_TO_WGS84.transform(pt)


def get_webmercator_coord(pt: QgsPointXY) -> QgsPointXY:
    """
    Transform Web Mercator (EPSG:3857) coordinate to WGS84 (EPSG:4326)
    :param pt: Point in Web Mercator coordinate system
    :return: Point in WGS84 geographic coordinate system
    """
    return COORD_XFORM_WGS84_TO_WEB_MERCATOR.transform(pt)


class RectangleMapTool(QgsMapToolEmitPoint):
    """Creates tools to drag an area across the canvas, show the perimeter of the area, and output the area in WGS84."""

    def __init__(self, canvas, nw_corner, se_corner):
        self.canvas = canvas
        QgsMapToolEmitPoint.__init__(self, self.canvas)
        self.rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubberBand.setStrokeColor(QColor(255, 0, 0))
        self.rubberBand.setWidth(1)
        self.reset()
        self.startPoint = None
        self.isEmittingPoint = None
        self.endPoint = None
        self.geo_startPoint = None
        self.geo_endPoint = None
        self.nw_corner = nw_corner
        self.se_corner = se_corner
        self.typed_nw = None
        self.typed_se = None

    def reset(self):
        """Resets canvas upon opening"""
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)

    def canvasPressEvent(self, e):
        """Controls what occurs when user clicks on canvas"""
        self.startPoint = self.toMapCoordinates(e.pos())
        self.endPoint = self.startPoint
        self.isEmittingPoint = True
        self.showRect(self.startPoint, self.endPoint)

    def canvasReleaseEvent(self, e):
        """Controls what occurs when user unclicks canvas."""
        self.isEmittingPoint = False
        r = self.rectangle()
        if r is not None:
            nw_corner = f"{r.yMaximum():.4f}, {r.xMinimum():.4f}"
            se_corner = f"{r.yMinimum():.4f}, {r.xMaximum():.4f}"
            self.nw_corner.emit(nw_corner)
            self.se_corner.emit(se_corner)

    def canvasMoveEvent(self, e):
        """Controls what occurs when a user moves across the canvass while button is clicked."""
        if not self.isEmittingPoint:
            return

        self.endPoint = self.toMapCoordinates(e.pos())

        self.showRect(self.startPoint, self.endPoint)

    def showRect(self, startPoint, endPoint):
        """Shows the perimeter of the area user drags."""
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
            return

        point1 = QgsPointXY(startPoint.x(), startPoint.y())
        point2 = QgsPointXY(startPoint.x(), endPoint.y())
        point3 = QgsPointXY(endPoint.x(), endPoint.y())
        point4 = QgsPointXY(endPoint.x(), startPoint.y())
        self.rubberBand.addPoint(point1, False)
        self.rubberBand.addPoint(point2, False)
        self.rubberBand.addPoint(point3, False)
        self.rubberBand.addPoint(point4, True)
        self.rubberBand.show()

    def rectangle(self):
        """Collects and translates bounding box coordinates to WGS84 using get_WGS84_coord"""
        if self.startPoint is None or self.endPoint is None:
            return None
        elif self.startPoint.x() == self.endPoint.x() or\
                self.startPoint.y() == self.endPoint.y():
            return None
        else:
            self.geo_startPoint = get_WGS84_coord(self.startPoint)
            self.geo_endPoint = get_WGS84_coord(self.endPoint)
            return QgsRectangle(self.geo_startPoint, self.geo_endPoint)

    def deactivate(self):
        QgsMapTool.deactivate(self)
        self.deactivated.emit()


class GISWin(QMainWindow):
    """Defines the window for the Area Search Tool pop up"""

    def __init__(self, parent, nw_corner, se_corner, curr_nw, curr_se):
        QMainWindow.__init__(self, parent)

        self.nw_corner_signal = nw_corner
        self.se_corner_signal = se_corner
        self.curr_nw = curr_nw
        self.curr_se = curr_se

        self.setWindowTitle("VBI Compare")
        self.setWindowIcon(QIcon("scripts/gui/media/VBI_Compare.png"))

        # add toolbar
        self.toolbar = QToolBar("Canvas Actions")
        self.toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(self.toolbar)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.setContentsMargins(0, 0, 0, 0)
        self.tabs.setIconSize(QSize(30, 30))
        self.tabs.setTabPosition(QTabWidget.South)

        # Set this to False even though the QGIS docs say to set to True for GUI apps
        # See: https://gis.stackexchange.com/questions/381006/cant-run-a-standalone-qgis-application-importerror-dll-load-failed
        self.qgs = QgsApplication([], False)

        # Supply the path to the qgis install location
        self.qgs.setPrefixPath("C:/OSGeo4W/apps/qgis", True)

        # load providers
        self.qgs.initQgis()

        main_layout = QHBoxLayout()
        group_box = QGroupBox("Area Select")
        layout = QVBoxLayout()

        # Add area corner displays.
        coords_disp_layout = QHBoxLayout()
        layout.addLayout(coords_disp_layout)

        label = QLabel("NW Corner")
        label.setMinimumWidth(60)
        label.setAlignment(Qt.AlignLeft)
        coords_disp_layout.addWidget(label)
        self.nw_corner_box = QLineEdit()
        self.nw_corner_box.setMinimumWidth(100)
        self.nw_corner_box.setReadOnly(False)
        self.nw_corner_box.setPlaceholderText("ex: 43.00, -69.00")
        coords_disp_layout.addWidget(self.nw_corner_box)

        label = QLabel("SE Corner")
        label.setMinimumWidth(60)
        label.setAlignment(Qt.AlignLeft)
        coords_disp_layout.addWidget(label)
        self.se_corner_box = QLineEdit()
        self.se_corner_box.setMinimumWidth(100)
        self.se_corner_box.setReadOnly(False)
        self.se_corner_box.setPlaceholderText("ex: 41.00, -67.00")
        coords_disp_layout.addWidget(self.se_corner_box)

        self.typed_area_draw = QPushButton("Draw Input")
        self.typed_area_draw.setFixedSize(100, 35)
        self.typed_area_draw.setDisabled(False)
        coords_disp_layout.addWidget(self.typed_area_draw, Qt.AlignLeft)
        self.typed_area_draw.clicked.connect(self.typed_area)

        map_layout = QHBoxLayout()
        self.canvas = QgsMapCanvas()
        self.canvas.setCanvasColor(Qt.black)
        self.canvas.enableAntiAliasing(True)

        basemap = "url=https://tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png&zmax=19&zmin=0&type=xyz"
        rlayer = QgsRasterLayer(basemap, 'OpenStreetMap', 'wms')
        if not rlayer.isValid():
            print("Layer failed to load!")

        # add layer to the registry
        QgsProject.instance().addMapLayer(rlayer)

        # # set Coordinate Reference System
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
        map_legend = QVBoxLayout()
        legend = QTextEdit()
        legend.setMaximumWidth(400)
        legend.setMaximumHeight(35)
        legend.append('<span style="color:red;font-weight:bold">%s <span style="color:black;font-weight:bold">%s '
                      % ("Red- Selected Search Area,", "Black- Previous Search Area"))
        legend.setReadOnly(True)
        legend.setAlignment(Qt.AlignCenter)
        map_legend.addWidget(legend)
        map_legend.addStretch(False)
        map_legend.setAlignment(Qt.AlignCenter)
        layout.addLayout(map_legend)

        # Add "Apply" button.
        apply_button_layout = QHBoxLayout()
        apply_data_button = QPushButton("Apply!")
        apply_data_button.setFixedSize(75, 50)
        apply_button_layout.addWidget(apply_data_button, Qt.AlignRight)
        apply_data_button.clicked.connect(self.applybutton)

        layout.addLayout(apply_button_layout)

        group_box.setLayout(layout)
        main_layout.addWidget(group_box)

        widget = QWidget()
        widget.setLayout(main_layout)
        self.idx_box = self.tabs.insertTab(1, widget, QIcon("scripts/gui/media/area.png"), "")
        self.tabs.setTabToolTip(self.idx_box, "Area Search")

        # Add toolbar buttons
        self.actionzoomin = QAction("Zoom in", self)
        self.actionzoomout = QAction("Zoom out", self)
        self.actionpan = QAction("Pan", self)
        self.actionbox = QAction("Drag Box", self)

        self.actionzoomin.setCheckable(True)
        self.actionzoomout.setCheckable(True)
        self.actionpan.setCheckable(True)
        self.actionbox.setCheckable(True)

        self.actionzoomin.triggered.connect(self.zoomin)
        self.actionzoomout.triggered.connect(self.zoomout)
        self.actionpan.triggered.connect(self.pan)
        self.actionbox.triggered.connect(self.box)

        self.toolbar.addAction(self.actionzoomin)
        self.toolbar.addAction(self.actionzoomout)
        self.toolbar.addAction(self.actionpan)
        self.toolbar.addAction(self.actionbox)

        self.toolbar.setContentsMargins(0, 0, 0, 0)
        self.toolbar.layout().setSpacing(20)
        self.toolbar.layout().setContentsMargins(0, 0, 0, 0)

        self.toolpan = QgsMapToolPan(self.canvas)
        self.toolpan.setAction(self.actionpan)
        self.toolzoomin = QgsMapToolZoom(self.canvas, False)  # false = in
        self.toolzoomin.setAction(self.actionzoomin)
        self.toolzoomout = QgsMapToolZoom(self.canvas, True)  # true = out
        self.toolzoomout.setAction(self.actionzoomout)
        self.tooldragbox = RectangleMapTool(self.canvas, self.nw_corner_signal, self.se_corner_signal)
        self.tooldragbox.setAction(self.actionbox)
        self.pan()

        self.show()

        self.mQFont = "Sans Serif"
        self.mQFontsize = 9
        self.mLabelQString = "© OpenStreetMap: openstreetmap.org/copyright"
        self.mMarginHorizontal = 0
        self.mMarginVertical = 0
        self.mLabelQColor = "#FF0000"
        self.inches_to_mm = 0.0393700787402  # 1 millimeter = 0.0393700787402 inches

        # Emitted when the canvas has rendered
        self.canvas.renderComplete.connect(self._on_render_complete)

        if self.curr_nw and self.curr_se != '':
            self.nw_corner_box.insert(self.curr_nw)
            self.se_corner_box.insert(self.curr_se)
            self.current_area()

    def __del__(self):
        """Destroys pop up when close for a fresh implementation later."""
        self.qgs.exitQgis()

    def add_copyright(self, p, text, xOffset, yOffset):
        """Adds copyright text to GIS Window"""
        p.translate(xOffset, yOffset)
        text.drawContents(p)
        p.setWorldTransform(p.worldTransform())
        self.canvas.refresh()

    def _on_render_complete(self, p):
        """Refreshes GIS window after manipulation"""

        deviceHeight = p.device().height()  # Get paint device height on which this painter is currently painting
        deviceWidth = p.device().width()  # Get paint device width on which this painter is currently painting

        # Create new container for structured rich text
        text = QTextDocument()
        font = QFont()
        font.setFamily(self.mQFont)
        font.setPointSize(int(self.mQFontsize))
        text.setDefaultFont(font)
        style = f"<style type=\"text/css\"> p color:{self.mLabelQColor}</style>"
        text.setHtml(f"{style}<p>{self.mLabelQString}</p>")
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

    def current_area(self):
        """Shows current area if a previously selected area exists in User Input GUI"""
        geo_start = list(map(float, self.curr_nw.split(", ")))
        geo_end = list(map(float, self.curr_se.split(", ")))
        xy_start = QgsPointXY(geo_start[1], geo_start[0])
        xy_end = QgsPointXY(geo_end[1], geo_end[0])
        startPoint = get_webmercator_coord(xy_start)
        endPoint = get_webmercator_coord(xy_end)

        point1 = startPoint
        point2 = QgsPointXY(startPoint.x(), endPoint.y())
        point3 = endPoint
        point4 = QgsPointXY(endPoint.x(), startPoint.y())

        rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        rubberBand.setStrokeColor(QColor(0, 0, 0))
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
        self.canvas.zoomToFeatureExtent(rect)

    def zoomin(self):
        self.canvas.setMapTool(self.toolzoomin)

    def zoomout(self):
        self.canvas.setMapTool(self.toolzoomout)

    def pan(self):
        self.canvas.setMapTool(self.toolpan)

    def box(self):
        """Connects coordinate displays to bounding box creation tool"""
        self.nw_corner_signal.connect(self.nw_corner)
        self.se_corner_signal.connect(self.se_corner)
        self.canvas.setMapTool(self.tooldragbox)

    def applybutton(self):
        self.close()

    def nw_corner(self, nw_corner: str):
        self.nw_corner_box.clear()
        self.nw_corner_box.insert(nw_corner)

    def se_corner(self, se_corner: str):
        self.se_corner_box.clear()
        self.se_corner_box.insert(se_corner)

    def typed_area(self):
        """Allows user to type coords into NW/ SE corner boxes if desired."""
        typed_nw = self.nw_corner_box.text()
        typed_se = self.se_corner_box.text()

        valid = self.typed_area_validate(typed_nw, typed_se)
        if not valid:
            return

        xy_start = QgsPointXY(self.geo_start[1], self.geo_start[0])
        xy_end = QgsPointXY(self.geo_end[1], self.geo_end[0])
        startPoint = get_webmercator_coord(xy_start)
        endPoint = get_webmercator_coord(xy_end)
        self.tooldragbox.typed_nw = startPoint
        self.tooldragbox.typed_se = endPoint
        self.tooldragbox.showRect(self.tooldragbox.typed_nw, self.tooldragbox.typed_se)
        rect = QgsRectangle(startPoint, endPoint)
        self.canvas.zoomToFeatureExtent(rect)
        self.nw_corner_signal.emit(typed_nw)
        self.se_corner_signal.emit(typed_se)

    def typed_area_validate(self, typed_nw, typed_se):
        """Validates user typed bounding box coords"""
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

    def closeEvent(self, event: QCloseEvent) -> None:
        event.accept()
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = GISWin(parent=None)
    window.show()

    app.exec_()
    app.exit()
