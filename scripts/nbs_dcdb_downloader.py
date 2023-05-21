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

import os.path
import boto3
import botocore
from botocore import UNSIGNED
from botocore.client import Config
from urllib.request import urlopen
from urllib.parse import urlparse, urlunparse
import json
from string import Template
from pathlib import Path
from datetime import datetime
from scripts.Batch_Builder import BatchBuilder
from typing import Union, Iterator, Tuple, NamedTuple
import sqlite3
import re
import logging
from functools import wraps
from time import time
import requests

logger = logging.getLogger(__file__)
WKT_POLY_TEMPLATE = Template(
    "POLYGON(($nw_lon $se_lat, $nw_lon $nw_lat, $se_lon $nw_lat, $se_lon $se_lat, $nw_lon $se_lat))")
SQL_TABLE_NAME_RE = re.compile("^[a-zA-Z][a-zA-Z_0-9]*$")

# 10m buffer constant
LAT_BUF_CONST = 0.01
LON_BUF_CONST = LAT_BUF_CONST * 1000


class BlueTopoTileDescriptor(NamedTuple):
    tile_name: str
    geotiff_url: str
    min_x: float
    min_y: float
    max_x: float
    max_y: float


class DataDownload:
    """A data file compiler for NOAA NBS and IHO DCDB data"""

    def __init__(self, status_update_signal, total_proc_signal, curr_proc_signal, chart_outline_signal,
                 tile_outline_signal, trackline_signal, calc_proc_total_sig, calc_curr_proc_sig):
        self.platform: list[str] = []
        self.charts: list[str] = []
        self.affected_charts: list[str] = []
        self.nbs_tiles: list[str] = []
        self.nbs_tile_corners: list[list[tuple[float, float]]] = []
        self.data_source: [str] = None  # TODO make enumerated
        self.data_storage: [str] = None
        self.get_charts: [bool] = None
        self.get_csb: [bool] = None
        self.data_paths: list = []
        self.process: [str] = None
        self.nbs_bucket = "noaa-ocs-nationalbathymetry-pds"
        self.dcdb_bucket = "noaa-dcdb-bathymetry-pds"
        self.nbs_urls: list[str] = []
        self.dcdb_urls: list[str] = []
        self.nbs_docs: list[str] = []
        self.dcdb_docs: list[str] = []
        self.tracklines: list[list[tuple[float, float]]] = []
        self.nw_corner: list[tuple[float, float]] = []
        self.se_corner: list[tuple[float, float]] = []
        self.search_type: [str] = None
        self.status_update_signal = status_update_signal
        # Indicates total number of processes to complete for monitoring purposes
        self.total_processes: [int] = None
        self.total_proc_signal = total_proc_signal
        self.processes_complete: [int] = 0
        self.curr_proc_signal = curr_proc_signal
        self.chart_outline_signal = chart_outline_signal
        self.tile_outline_signal = tile_outline_signal
        self.trackline_signal = trackline_signal
        self.calc_proc_total_sig = calc_proc_total_sig
        self.calc_curr_proc_sig = calc_curr_proc_sig
        self.run_rep: [bool] = None
        self.both_data: [bool] = None
        self.nbs_doc_file: [str] = None
        self.dcdb_doc_file: [str] = None
        self.nbs_url_file: [str] = None
        self.dcdb_url_file: [str] = None

    def execute(self) -> None:
        # set total processes by inputs
        if (self.data_source == 'nbs' and self.get_csb is False and self.search_type == 'b' and self.process == 'c') or \
           (self.data_source == 'dcdb' and self.get_charts is False and self.process == 'c'):
            self.total_processes = 4
            self.total_proc_signal.emit(self.total_processes)
        elif (self.data_source == 'dcdb' and self.get_charts is False and self.process == 'l') or \
             (self.data_source == 'nbs' and self.search_type == 's' and self.get_csb is False and self.process == 'c') or \
             (self.data_source == 'nbs' and self.search_type == 'b' and self.get_csb is False and self.process == 'l'):
            self.total_processes = 5
            self.total_proc_signal.emit(self.total_processes)
        elif self.data_source == 'nbs' and self.search_type == 's' and self.get_csb is False and self.process == 'l':
            self.total_processes = 6
            self.total_proc_signal.emit(self.total_processes)
        elif self.get_charts is True and self.process == 'l':
            self.total_processes = 12
            self.total_proc_signal.emit(self.total_processes)
        elif (self.get_charts is True and self.process == 'c') or \
                (self.get_csb is True and self.process == 'l' and self.search_type == 'b'):
            self.total_processes = 10
            self.total_proc_signal.emit(self.total_processes)
        elif self.get_csb is True and self.process == 'l' and self.search_type == 's':
            self.total_processes = 11
            self.total_proc_signal.emit(self.total_processes)
        elif self.get_csb is True and self.process == 'c' and self.search_type == 's':
            self.total_processes = 9
            self.total_proc_signal.emit(self.total_processes)
        elif self.get_csb is True and self.process == 'c' and self.search_type == 'b':
            self.total_processes = 8
            self.total_proc_signal.emit(self.total_processes)

        # add to process count
        self.processes_complete += 1
        self.curr_proc_signal.emit(self.processes_complete)

        # nbs s l
        if (self.data_source == 'nbs') and (self.search_type == 's') and (self.process == 'l'):
            self.get_charts = False
            self.status_update_signal.emit(f'<p style="color:#000000"> Starting NBS Download.</p>')
            self.nbs_chart_data()
        # nbs s c
        elif (self.data_source == 'nbs') and (self.search_type == 's') and (self.process == 'c'):
            self.get_charts = False
            self.status_update_signal.emit(f'<p style="color:#000000"> Starting NBS URL Compilation.</p>')
            self.nbs_chart_data()
        # nbs a l
        # nbs a c
        elif (self.data_source == 'nbs') and (self.search_type == 'b'):
            self.get_charts = False
            self.status_update_signal.emit(f'<p style="color:#000000"> "Starting NBS process.</p>')
            self.nbs_by_area()
        # dcdb s l
        # dcdb s c
        elif (self.data_source == "dcdb") and (self.search_type == 's'):
            self.get_csb = False
            self.status_update_signal.emit(f'<p style="color:#000000"> "Starting DCDB Process.</p>')
            self.dcdb()
        # dcdb a l
        # dcdb a c
        elif (self.data_source == 'dcdb') and (self.search_type == 'b'):
            self.get_csb = False
            self.status_update_signal.emit(f'<p style="color:#000000"> "Starting DCDB process.</p>')
            self.dcdb_by_area()

    def create_output_location(self) -> None:
        """Creates specific parent file locations based on data source.
            Tests if the path already exists and only creates new paths and archives."""

        self.status_update_signal.emit(
            f'<p style="color:#000000"> Stored Data Path: {self.data_storage}/{self.data_source}</p>')

        if self.data_source == 'nbs':
            directory = f"{self.data_storage}/{self.data_source}"
            pth = Path(directory)
            self.data_paths.append(pth)
            if not pth.exists():
                Path.mkdir(pth, parents=True)

            arc_pth = Path(pth, "Archive")
            arc_exists = arc_pth.exists()
            if not arc_exists:
                Path.mkdir(arc_pth, parents=True)

        if self.data_source == 'dcdb':
            directory = f"{self.data_storage}/{self.data_source}"
            pth = Path(directory)
            is_exists = pth.exists()
            if not is_exists:
                Path.mkdir(pth, parents=True)

        # add to process count
        self.processes_complete += 1
        self.curr_proc_signal.emit(self.processes_complete)

    def dwnld_location(self) -> None:
        """Creates specific file locations for locally downloaded data.
            Tests if the path already exists and only creates new paths and archives. Only used if the user
            chooses the local processing option"""

        self.status_update_signal.emit(
            f'<p style="color:#000000"> Creating sub folders for downloaded data in '
            f'{self.data_storage}/{self.data_source}</p>')

        if self.data_source == "nbs" and len(self.nbs_tiles) > 0:
            for tile in self.nbs_tiles:
                directory = f"{self.data_storage}/nbs/tiles/{tile}"
                pth = Path(directory)
                self.data_paths.append(pth)
                is_exists = pth.exists()
                if not is_exists:
                    Path.mkdir(pth, parents=True)
                    arc_pth = Path(pth, "Archive")
                    Path.mkdir(arc_pth, parents=True)

        # Creates a file path in the designated place .../dcdb/ship name. Also creates an archive in the ship folder.
        elif self.data_source == "dcdb":
            for ship in self.platform:
                ship = ship.rstrip()
                ship = ship.replace('/', '')
                directory = f"{self.data_storage}/{self.data_source}/{ship}"
                pth = Path(directory)
                self.data_paths.append(pth)
                is_exists = pth.exists()
                if not is_exists:
                    Path.mkdir(pth, parents=True)
                    arc_pth = Path(pth, "Archive")
                    Path.mkdir(arc_pth, parents=True)

        # add to process count
        self.processes_complete += 1
        self.curr_proc_signal.emit(self.processes_complete)

    @staticmethod
    def bounding_box_to_wkt_polygon(se_corner: Tuple[float, float], nw_corner: Tuple[float, float]) -> str:
        """
        Return a WKT POLYGON representing a bounding box described by a SE and NW corners.
        :param se_corner: SE corner of bounding box as a tuple of two floats, the first being latitude,
            the second being longitude
        :param nw_corner: NW corner of bounding box as a tuple of two floats, the first being latitude,
            the second being longitude
        :return: WKT POLYGON representing a bounding box
        """

        return WKT_POLY_TEMPLATE.substitute({
            'se_lat': se_corner[0],
            'se_lon': se_corner[1],
            'nw_lat': nw_corner[0],
            'nw_lon': nw_corner[1]
        })

    @staticmethod
    def table_name_is_safe(tablename: str) -> bool:
        m = SQL_TABLE_NAME_RE.fullmatch(tablename)
        return m is not None

    @staticmethod
    def query_blue_topo_gpkg(gpkg_path: Union[Path, str], se_corner: Tuple[float, float],
                             nw_corner: Tuple[float, float]) -> Iterator[BlueTopoTileDescriptor]:
        """
        Query BlueTopo tile scheme
        <https://noaa-ocs-nationalbathymetry-pds.s3.amazonaws.com/index.html#BlueTopo/BlueTopo-Tile-Scheme/>
        returning strings representing URLs to BlueTopo tiles that intersect a geographic (WGS84) bounding box.
        :param gpkg_path: Path to BlueTopo GeoPackage file to query
        :param se_corner: SE corner of bounding box as a tuple of two floats, the first being latitude,
            the second being longitude
        :param nw_corner: NW corner of bounding box as a tuple of two floats, the first being latitude,
            the second being longitude
        :return: generator yielding a ``BlueTopoTileDescriptor`` describing each matching tile.
        """
        if not os.path.exists(gpkg_path):
            raise FileNotFoundError(f"Can't find GeoPackage file at path '{gpkg_path}'.")
        if not os.access(gpkg_path, os.R_OK):
            raise PermissionError(f"Can't access GeoPackage file at path '{gpkg_path}'.")

        # Open DB connection and enable Spatialite extension
        conn = sqlite3.connect(gpkg_path)
        conn.enable_load_extension(True)
        conn.execute('SELECT load_extension("mod_spatialite")')
        conn.enable_load_extension(False)

        # Get name of tile scheme table
        cur = conn.cursor()
        cur.execute('SELECT table_name FROM gpkg_contents')
        row = cur.fetchone()
        if not row:
            raise ValueError(f"No tile scheme tables found in GeoPackage file at path '{gpkg_path}'.")
        table_name = row[0]

        # Make sure table_name is just a table name and not malicious SQL since we need to use Python string
        # substitution to dynamically fill in the table name (since the DB library doesn't allow table names to be
        # parameterized, just values)
        if not DataDownload.table_name_is_safe(table_name):
            raise ValueError(f"Invalid tile scheme table name '{table_name}' in GeoPackage file at path '{gpkg_path}'")

        logger.debug(f"Using tile scheme table '{table_name}' from GeoPackage file at path '{gpkg_path}'.")

        # Get WKT POLYGON version of bounding box corners
        bbox_poly = DataDownload.bounding_box_to_wkt_polygon(se_corner, nw_corner)

        cur.execute(("SELECT tile, GeoTIFF_Link, "
                     "MbrMinX(GeomFromGPB(geom)) as minX, MbrMinY(GeomFromGPB(geom)) as minY, "
                     "MbrMaxX(GeomFromGPB(geom)) as maxX, MbrMaxY(GeomFromGPB(geom)) as maxY "
                     f"FROM {table_name} "
                     "WHERE ST_Intersects(GeomFromGPB(geom), ST_GeomFromText(?))"),
                    (bbox_poly,))
        for row in cur:
            yield BlueTopoTileDescriptor(row[0], row[1], row[2], row[3], row[4], row[5])

    def neg_area_buffer(self, tile_corners):
        """Negative buffer the NBS tiles to ensure only charts that overlap are returned,
        not those that only meet at the edge.
        Overcomes decimal place discrepancy between NBS and MCD."""

        avglat = (tile_corners[0][0] + tile_corners[1][0]) / 2
        # del_lon is used to find the difference in longitude to be added/ subtracted to the given corner longitudes.
        # It finds the equivalent of 10m of longitude at that average latitude on the WGS 84 ellipsoid.
        # This is done to avoid collecting tiles which only share a boundary, but do not actually overlap
        del_lon = LON_BUF_CONST / (-11.364 * avglat ** 2 - 245.76 * avglat + 112345)
        latmax = tile_corners[0][0] - LAT_BUF_CONST
        latmin = tile_corners[1][0] + LAT_BUF_CONST
        lonmax = tile_corners[1][1] - del_lon
        lonmin = tile_corners[0][1] + del_lon
        return latmax, latmin, lonmax, lonmin

    def nbs_by_area(self) -> None:
        """Determines the NBS tiles within the selected search area by querying NBS Geopackage file.
        Places tile names into self.nbs_tiles, tile geometry into self.nbs_tile_corners, and tile http url locations
        into self.nbs_urls.
        Downloads/ confirms current NBS tile geopackage exists in local download location."""

        self.create_output_location()

        # Determine if the NBS tile layout Geopackage exists. If not, download it.
        resource = boto3.resource('s3', config=Config(signature_version=UNSIGNED))
        bucket = resource.Bucket(self.nbs_bucket)
        gpkg_s3fldr = f"BlueTopo/_BlueTopo_Tile_Scheme/"

        gpkg_key = str()
        for gpkg in bucket.objects.filter(Prefix=gpkg_s3fldr):
            gpkg_key = gpkg.key

        gpkg_target = f"{self.data_storage}/nbs{gpkg_key[30:]}"

        # If the geopackage already exists in the local folder, skip.
        if os.path.exists(gpkg_target):
            self.status_update_signal.emit(f'<p style="color:#000000"> Current NBS GeoPackage is up to date.</p>')

        else:
            # If a previous geopackage already exists, but has a different date in the file name, move it to archive.
            directory = Path(gpkg_target).parents[0]
            gpkg_file = list(directory.glob('*.gpkg'))
            if len(gpkg_file) != 0:
                for file in gpkg_file:
                    self.status_update_signal.emit(
                        f'<p style="color:#CCA70E"> Moving {str(file)} to Archive</p>')
                    file.rename(directory / "Archive" / file.name)

            # If geopackage does not exist in the file, download.
            if not os.path.exists(gpkg_target):
                self.status_update_signal.emit(f'<p style="color:#000000"> Downloading latest NBS GeoPackage'
                                               f' to {gpkg_target}.</p>')
                bucket.download_file(gpkg_key, gpkg_target)

        count = 0
        for corner in self.se_corner:
            tile_corners = [self.nw_corner[count], corner]
            latmax, latmin, lonmax, lonmin = self.neg_area_buffer(tile_corners)
            se_corner = (latmin, lonmax)
            nw_corner = (latmax, lonmin)

            # Determine the NBS tiles that intersect the area(s) of interest and append tile names to self.nbs_tiles
            # # and nw/ se corners to self.nbs_tile_corners
            for desc in DataDownload.query_blue_topo_gpkg(gpkg_target, se_corner, nw_corner):
                self.nbs_tiles.append(desc.tile_name)
                self.nbs_tile_corners.append([(desc.max_y, desc.min_x), (desc.min_y, desc.max_x)])
                self.nbs_urls.append(desc.geotiff_url)
            count += 1

        # If no tiles are available in the given area, end the process
        if not self.nbs_tiles:
            self.status_update_signal.emit(
                f'<p style="color:#CCA70E"> No NBS tile data available in given area.</p>')
            self.status_update_signal.emit(f'<p style="color:#1C5BC2"> \nRequest Cancelled.</p>')
            self.processes_complete = self.total_processes
            self.curr_proc_signal.emit(self.processes_complete)
            return

        # add to process count
        self.processes_complete += 1
        self.curr_proc_signal.emit(self.processes_complete)

        if self.process == "l":
            self.status_update_signal.emit(f'<p style="color:#000000"> Starting NBS tile download</p>')
            self.data_source = 'nbs'
            self.data_paths = []
            self.nbs_download()
        elif self.process == "c":
            self.status_update_signal.emit(f'<p style="color:#000000"> Starting NBS S3 URL Compilation</p>')
            self.nbs_cloud()

    def nbs_download(self) -> None:
        """ Download data from the NBS BlueTopo AWS bucket based on user inputs.
            Will download all files associated with the desired NBS tiles and place
            them in the same tile name directory."""

        self.dwnld_location()

        # Create NBS tile AWS objects
        aws_folder = list()
        for tile in self.nbs_tiles:
            obj_name = f"BlueTopo/{str(tile)}/"
            aws_folder.append(obj_name)

        resource = boto3.resource('s3', config=Config(signature_version=UNSIGNED))
        bucket = resource.Bucket(self.nbs_bucket)

        self.status_update_signal.emit(f'<p style="color:#000000"> Determining if NBS files are available.</p>')
        # Collect download locations and object keys for download.
        targets: list[str] = []
        keys: list[str] = []
        count = 0
        while count <= (len(self.nbs_tiles) - 1):
            # Determine if there are any files for the given tile in the AWS bucket.
            objects = list(bucket.objects.filter(Prefix=aws_folder[count]))
            if len(objects) == 0:
                self.status_update_signal.emit(
                    f'<p style="color:#CCA70E"> No NBS files available for tile: {aws_folder[count][9:-1]}</p>')
                count += 1
            else:
                # Determine the charts affected by the tile and display their outlines on monitor.
                self.nbs_chart_outlines(self.nbs_tile_corners[count])

                # If objects exists, display tile outline on the monitor and create URL to it.
                tile_corners = [self.nbs_tile_corners[count][0][0], self.nbs_tile_corners[count][0][1],
                                self.nbs_tile_corners[count][1][0], self.nbs_tile_corners[count][1][1]]
                self.tile_outline_signal.emit(tile_corners)

                for obj in bucket.objects.filter(Prefix=aws_folder[count]):
                    target = f"{self.data_paths[count]}/{obj.key[18:]}"
                    targets.append(target)
                    keys.append(obj.key)
                    # This line ensures that both available files .tiff, and .tiff.aux.xml are collected before moving
                    # on to the next tile.
                    if len(keys) % 2 == 0:
                        count += 1
            if len(keys) == (2 * len(self.nbs_tiles)):
                break

        # If none of the desired tiles are available, end the download
        if len(targets) == 0:
            self.status_update_signal.emit(f'<p style="color:#CCA70E"> No NBS tile data available.</p>')
            self.status_update_signal.emit(f'<p style="color:#1C5BC2"> \nRequest Complete.</p>')
            self.processes_complete = self.total_processes
            self.curr_proc_signal.emit(self.processes_complete)
            return

        # Perform download while checking for existing local files
        target_count = 0
        for target in targets:
            self.nbs_docs.append(target)
            target_path = Path(target)
            target_exists = target_path.exists()
            directory = f"{target.split('/', 1)[0]}/"
            file_count = list(Path(directory).glob('*.*'))
            object_size = bucket.Object(keys[target_count]).content_length
            # Determine if the directory holds older files. If so, move them to archive.
            if len(file_count) != 0:
                for file in file_count:
                    # look at the date in the target file name to determine file age
                    if keys[target_count][36:44] not in str(file):
                        source = Path(directory)
                        self.status_update_signal.emit(
                            f'<p style="color:#CCA70E"> Moving {str(file)} to Archive</p>')
                        file.rename(source / "Archive" / file.name)

            # Target folder has file in it that is the same name, age, and size; skip download
            if target_exists and (target_path.stat().st_size == object_size):
                self.status_update_signal.emit(
                    f'<p style="color:#CCA70E"> Skipping existing file at: {target}</p>')
                target_count += 1

            # Target folder has partial file of the same name
            elif target_exists and (target_path.stat().st_size != object_size):
                source = Path(directory)
                self.status_update_signal.emit(f'<p style="color:#CCA70E"> '
                                               f'Moving corrupt {keys[target_count]} to Archive</p>')
                target_path.rename(source / "Archive" / target_path.name)

                self.status_update_signal.emit(
                    f'<p style="color:#11B01A"> Downloading file: {keys[target_count][18:]}</p>')
                self.status_update_signal.emit(f'<p style="color:#000000"> File location: {target}</p>')
                bucket.download_file(keys[target_count], target)
                target_count += 1

            # Target folder is empty or has one of two expected files, download
            elif not target_exists:
                self.status_update_signal.emit(
                    f'<p style="color:#11B01A"> Downloading file: {keys[target_count][18:]}</p>')
                self.status_update_signal.emit(f'<p style="color:#000000"> File location: {target}</p>')
                bucket.download_file(keys[target_count], target)
                target_count += 1

            if len(targets) == target_count:
                self.status_update_signal.emit(f'<p style="color:#000000"> '
                                               f'NBS Download Complete. Writing location file</p>')
                # add to process count
                self.processes_complete += 1
                self.curr_proc_signal.emit(self.processes_complete)
                self.status_update_signal.emit(
                    f'<p style="color:#11B01A"> MCD charts [{len(self.affected_charts)}] potentially affected by '
                    f'selected datasets include: {self.affected_charts}</p>')
                self.write_nbs_docs_file()

    def nbs_cloud(self) -> None:
        """Creates a list of URLs to desired and available nbs tile data in the NBS AWS for use in cloud processing"""
        self.data_source = "nbs"

        # Create NBS tile AWS objects
        aws_folder = list()
        for tile in self.nbs_tiles:
            obj_name = f"BlueTopo/{str(tile)}/"
            aws_folder.append(obj_name)

        resource = boto3.resource('s3', config=Config(signature_version=UNSIGNED))
        bucket = resource.Bucket(self.nbs_bucket)

        # Determine if data for tile exists. If data is available, create and store s3 url to file. Used to confirm
        # that data listed in the gpkg file is actually available.
        count = 0
        while count < len(self.nbs_tiles):
            # Determine if there are any files for the given tile in the AWS bucket.
            objects = list(bucket.objects.filter(Prefix=aws_folder[count]))
            if len(objects) == 0:
                self.status_update_signal.emit(
                    f'<p style="color:#CCA70E"> No NBS files available for tile: {aws_folder[count][9:-1]}</p>')
                self.nbs_urls[count] = "N/A"
                count += 1
            else:
                # Determine the charts affected by the tile and display their ouline on the monitor.
                self.nbs_chart_outlines(self.nbs_tile_corners[count])

                # If objects exists, display tile outline on the monitor and create URL to it.
                tile_corners = [self.nbs_tile_corners[count][0][0], self.nbs_tile_corners[count][0][1],
                                self.nbs_tile_corners[count][1][0], self.nbs_tile_corners[count][1][1]]

                self.tile_outline_signal.emit(tile_corners)

                self.status_update_signal.emit(
                    f'<p style="color:#11B01A"> Collecting NBS tile: {self.nbs_tiles[count]}</p>')
                # Change from HTTP URL to S3 URL
                url_lst = list(urlparse(self.nbs_urls[count]))
                url_lst[0] = 's3'
                url_lst[1] = 'noaa-ocs-nationalbathymetry-pds'
                new_url = urlunparse(url_lst)
                self.nbs_urls[count] = new_url
                count += 1

            # Determine if files were collected, if yes then move on, if not alert the user and end the process.
            if count == len(self.nbs_tiles) and len(self.nbs_urls) != 0:
                # add to process count
                self.processes_complete += 1
                self.curr_proc_signal.emit(self.processes_complete)
                self.status_update_signal.emit(
                    f'<p style="color:#000000"> NBS URL compilation complete. Writing to file.</p>')
                self.status_update_signal.emit(
                    f'<p style="color:#11B01A"> MCD charts [{len(self.affected_charts)}] potentially affected by '
                    f'selected datasets include: {self.affected_charts}</p>')
                self.write_nbs_txt_file()
            elif count == len(self.charts) and len(self.nbs_urls) == 0:
                self.status_update_signal.emit(
                    f'<p style="color:#CCA70E"> No available NBS files exist for requested charts.</p>')
                self.status_update_signal.emit(f'<p style="color:#1C5BC2"> \nRequest Complete.</p>')
                self.processes_complete = self.total_processes
                self.curr_proc_signal.emit(self.processes_complete)
                return

    def nbs_chart_outlines(self, tile_corners) -> None:
        """Obtains NW and SE corners of each affected chart area for display on monitor."""

        latmax, latmin, lonmax, lonmin = self.neg_area_buffer(tile_corners)

        bands = [1, 2, 3, 4]  # these are the layer number for chart bands 2-5 in the ARC API

        for band in bands:
            s = Template(
                'https://gis.charttools.noaa.gov/arcgis/rest/services/MarineChart_Services/Status_New_NOAA_ENCs/'
                'MapServer/$band_num/query?where=&text=&objectIds=&time=&timeRelation=esriTimeRelationOverlaps&'
                'geometry=%7B%0D%0A++%22xmin%22%3A+$lonmin%2C%0D%0A++%22ymin%22%3A+$latmin%2C%0D%0A++%22xmax%22'
                '%3A+$lonmax%2C%0D%0A++%22ymax%22%3A+$latmax%2C%0D%0A++%22spatialReference%22%3A+%7B%0D%0A++++'
                '%22wkid%22%3A+4326%0D%0A++%7D%0D%0A%7D&geometryType=esriGeometryEnvelope&inSR=4326&'
                'spatialRel=esriSpatialRelIntersects&distance=&units=esriSRUnit_Foot&relationParam=&'
                'outFields=*&returnGeometry=true&returnTrueCurves=false&maxAllowableOffset=&geometryPrecision=&'
                'outSR=&havingClause=&returnIdsOnly=false&returnCountOnly=false&orderByFields=&'
                'groupByFieldsForStatistics=&outStatistics=&returnZ=false&returnM=false&gdbVersion=&'
                'historicMoment=&returnDistinctValues=false&resultOffset=&resultRecordCount=&'
                'returnExtentOnly=false&sqlFormat=none&datumTransformation=&parameterValues=&rangeValues=&'
                'quantizationParameters=&featureEncoding=esriDefault&f=pjson')

            url = s.substitute(latmax=latmax, latmin=latmin, lonmax=lonmax,
                               lonmin=lonmin, band_num=band)
            with urlopen(url) as response:
                body = response.read()
                response.close()
                files = json.loads(body)
                if 'status' in files and files['status'] == "error":
                    self.status_update_signal.emit(
                        f'<p style="color:#CF0D04"> \nError: Could not access MCD server. '
                        f'Please try again later"</p>')
                    self.processes_complete = self.total_processes
                    self.curr_proc_signal.emit(self.processes_complete)
                    return
                for file in files["features"]:
                    if file["attributes"]["cell_name"] not in self.affected_charts:
                        self.affected_charts.append(file["attributes"]["cell_name"])
                        geometry = file["geometry"]["rings"]
                        geometry = geometry[0]
                        geometry[1][0], geometry[1][1] = geometry[1][1], geometry[1][0]
                        geometry[3][0], geometry[3][1] = geometry[3][1], geometry[3][0]
                        chart_corners = (geometry[1] + geometry[3])
                        self.chart_outline_signal.emit(chart_corners)

    def nbs_chart_area(self, charts) -> None:
        """Obtains NW and SE corners of MCD charts and appends them to a list for future queries."""

        self.status_update_signal.emit(
            f'<p style="color:#000000"> Determining the bounding box(s) for the requested chart(s).</p>')

        s = Template("https://gis.charttools.noaa.gov/arcgis/rest/services/MarineChart_Services/"
                     "Status_New_NOAA_ENCs/MapServer/$band/query?where=CELL_NAME+%3D+%27$chart_num%27&text=&"
                     "objectIds=&time=&timeRelation=esriTimeRelationOverlaps&geometry=&"
                     "geometryType=esriGeometryEnvelope&inSR=&spatialRel=esriSpatialRelIntersects&distance=&"
                     "units=esriSRUnit_Foot&relationParam=&outFields=*&returnGeometry=true&returnTrueCurves=false&"
                     "maxAllowableOffset=&geometryPrecision=&outSR=4326&havingClause=&returnIdsOnly=false&"
                     "returnCountOnly=false&orderByFields=&groupByFieldsForStatistics=&outStatistics=&"
                     "returnZ=false&returnM=false&gdbVersion=&historicMoment=&returnDistinctValues=false&"
                     "resultOffset=&resultRecordCount=&returnExtentOnly=false&sqlFormat=none&datumTransformation=&"
                     "parameterValues=&rangeValues=&quantizationParameters=&featureEncoding=esriDefault&f=pjson")
        count = 0
        for chart in charts:
            url = s.substitute(band=chart[2], chart_num=chart)
            count += 1
            with urlopen(url) as response:
                body = response.read()
                response.close()
                files = json.loads(body)
                if 'status' in files and files['status'] == "error":
                    self.status_update_signal.emit(
                        f'<p style="color:#CF0D04"> \nError: Could not access MCD server machines.</p>' 
                        f'Please try again later')
                    self.processes_complete = self.total_processes
                    self.curr_proc_signal.emit(self.processes_complete)
                    return
                for file in files["features"]:
                    geometry = file["geometry"]["rings"]
                    # Collect chart geometry and re-arrange in to lat, long for NW and SE corners
                    geometry = geometry[0]
                    geometry[1][0], geometry[1][1] = geometry[1][1], geometry[1][0]
                    geometry[3][0], geometry[3][1] = geometry[3][1], geometry[3][0]
                    self.nw_corner.append(geometry[1])
                    self.se_corner.append(geometry[3])

        if count == len(charts):
            self.status_update_signal.emit(f'<p style="color:#000000"> Chart bounding box(s) found.</p>')
            # add to process count
            self.processes_complete += 1
            self.curr_proc_signal.emit(self.processes_complete)
            self.nbs_by_area()

    def nbs_chart_data(self) -> None:
        """Starts the collection for each desired chart individually.Specifically used for processes where NBS is the
        the primary data source."""

        chart_count = 0
        for chart in self.charts:
            if chart_count > 0:
                # reset process count
                self.processes_complete = 0
                self.curr_proc_signal.emit(self.processes_complete)
                self.affected_charts = []
                self.nbs_tiles = []
                self.nbs_urls = []
                self.nbs_docs = []
                self.se_corner = []
                self.nw_corner = []
                self.nbs_tile_corners = []

            self.status_update_signal.emit(f'<p style="color:#000000"> Processing chart: {chart}</p>')
            self.affected_charts.append(chart)
            self.nbs_chart_area([chart])
            chart_count += 1

    def dcdb_by_area(self) -> None:
        """Determines the DCDB CSB data desired by the user based on a bounding box input.
        Searches the DCDB ARC API for files names using a GET request.
        Converts API file names to DCDB S3 Bucket object names. Stores them in a list called dcdb_aws.
        Requests a download or compilation of the data using dcdb_download or dcdb_cloud functions."""

        self.create_output_location()

        # Determine DCDB file names for the given area via GET request against DCDB API
        self.status_update_signal.emit(
            f'<p style="color:#000000"> Finding DCDB data within desired bounding box.</p>')
        file_names: list[str] = []
        file_numbers: list[int] = []
        s = Template('https://gis.ngdc.noaa.gov/arcgis/rest/services/csb/MapServer/1/query?where=&text=&objectIds=&'
                     'time=&geometry=%7B%0D%0A++%22xmin%22%3A+$lonmin%2C%0D%0A++%22ymin%22%3A+$latmin%2C+%0D%0A++%22'
                     'xmax%22%3A+$lonmax%2C%0D%0A++%22ymax%22%3A+$latmax%2C%0D%0A++%22spatialReference%22%3A+%7B%0D'
                     '%0A++++%3C$srid%3E%0D%0A++%7D%0D%0A%7D&geometryType=esriGeometryEnvelope&inSR=$srid&'
                     'spatialRel=esriSpatialRelIntersects&distance=&units=esriSRUnit_Foot&relationParam=&outFields=*&'
                     'returnGeometry=true&returnTrueCurves=false&maxAllowableOffset=&geometryPrecision=&outSR=4326&'
                     'havingClause=&returnIdsOnly=false&returnCountOnly=false&orderByFields=&'
                     'groupByFieldsForStatistics=&outStatistics=&returnZ=false&returnM=false&gdbVersion=&'
                     'historicMoment=&returnDistinctValues=false&resultOffset=&resultRecordCount=&'
                     'returnExtentOnly=false&datumTransformation=&parameterValues=&rangeValues=&'
                     'quantizationParameters=&featureEncoding=esriDefault&f=pjson')
        area_count = 0
        for corner in self.nw_corner:
            url = s.substitute(latmax=corner[0], latmin=self.se_corner[area_count][0],
                               lonmax=self.se_corner[area_count][1], lonmin=corner[1], srid="4326")
            with urlopen(url) as response:
                body = response.read()
                response.close()
                files = json.loads(body)
                for file in files["features"]:
                    if file["attributes"]["PLATFORM"] not in self.platform:
                        self.platform.append(file["attributes"]["PLATFORM"])
                ship_count = 0
                while ship_count < len(self.platform):
                    for file in files["features"]:
                        if file["attributes"]["PLATFORM"] == self.platform[ship_count]:
                            file_names.append(file["attributes"]["NAME"])
                            geometry = file["geometry"]["paths"]
                            self.tracklines.append(geometry[0])
                        else:
                            continue
                    ship_count += 1
                    file_numbers.append(len(file_names))
                area_count += 1
        # Convert API file names to S3 object names
        dcdb_aws: list[str] = []
        for name in file_names:
            name.split('.')
            dcdb_name = name[:-7]
            obj_name = \
                f"csb/csv/{dcdb_name[:4]}/{dcdb_name[4:6]}/{dcdb_name[6:8]}/{dcdb_name[:20]}_{dcdb_name[21:]}_pointData.csv"
            dcdb_aws.append(obj_name)

        if len(dcdb_aws) == 0:
            self.status_update_signal.emit(
                f'<p style="color:#CCA70E"> \nNo DCDB data available in specified box. Process cancelled.</p>')
            self.processes_complete = self.total_processes
            self.curr_proc_signal.emit(self.processes_complete)
            return

        # add to process count
        self.processes_complete += 1
        self.curr_proc_signal.emit(self.processes_complete)

        if self.process == "l":
            self.status_update_signal.emit(f'<p style="color:#000000"> Starting DCDB download</p>')
            self.dcdb_download(file_numbers, dcdb_aws)

        elif self.process == "c":
            self.status_update_signal.emit(f'<p style="color:#000000"> Starting DCDB S3 URL compilation.</p>')
            self.dcdb_cloud(dcdb_aws)

    def dcdb(self) -> None:
        """Determines the DCDB CSB data desired by the user based on vessel list input.
        Searches the DCDB ARC API for files names using a GET request.
        Converts API file names to DCDB S3 Bucket object names. Stores them in a list called dcdb_aws
        Requests a download or compilation of the data using dcdb_download or dcdb_cloud functions."""

        self.create_output_location()

        file_names: list[str] = []
        file_numbers: list[int] = []
        for platform in self.platform:
            ship = platform.replace(' ', '+')
            url = 'https://gis.ngdc.noaa.gov/arcgis/rest/services/csb/MapServer/1/query?' \
                  'where=PLATFORM%3D%27' + ship + '%27&text=&objectIds=&time=&geometry=&' \
                  'geometryType=esriGeometryEnvelope&inSR=&spatialRel=esriSpatialRelIntersects&distance=&' \
                  'units=esriSRUnit_Foot&relationParam=&outFields' \
                  '=*&returnGeometry=true&returnTrueCurves=false&maxAllowableOffset=&geometryPrecision=&outSR=4326' \
                  '&havingClause=&returnIdsOnly=false&returnCountOnly=false&orderByFields=&' \
                  'groupByFieldsForStatistics=&outStatistics=&returnZ=false&' \
                  'returnM=false&gdbVersion=&historicMoment=&returnDistinctValues=false&resultOffset=&' \
                  'resultRecordCount=&returnExtentOnly=false&datumTransformation=&parameterValues=&rangeValues=&' \
                  'quantizationParameters=&featureEncoding=esriDefault&f=pjson'
            with urlopen(url) as response:
                body = response.read()
                response.close()
                files = json.loads(body)
                for file in files["features"]:
                    file_names.append(file["attributes"]["NAME"])
                    geometry = file["geometry"]["paths"]
                    self.tracklines.append(geometry[0])
                    # self.trackline_signal.emit(geometry[0])
                file_numbers.append(len(file_names))

        # Extract CSB line AWS object names
        dcdb_aws: list[str] = []
        for name in file_names:
            name.split('.')
            dcdb_name = name[:-7]
            obj_name = \
                f"csb/csv/{dcdb_name[:4]}/{dcdb_name[4:6]}/{dcdb_name[6:8]}/{dcdb_name[:20]}_{dcdb_name[21:]}_pointData.csv"
            dcdb_aws.append(obj_name)

        # add to process count
        self.processes_complete += 1
        self.curr_proc_signal.emit(self.processes_complete)

        if self.process == "l":
            self.status_update_signal.emit(f'<p style="color:#000000"> Starting DCDB download.</p>')
            self.dcdb_download(file_numbers, dcdb_aws)

        elif self.process == "c":
            self.status_update_signal.emit(f'<p style="color:#000000"> Starting DCDB S3 URL compilation.</p>')
            self.dcdb_cloud(dcdb_aws)

    def dcdb_download(self, file_numbers, dcdb_aws) -> None:
        """Downloads data from IHO DCDB bucket based on user inputs.
        Will download all files associated with the desired S3 objects and places
        them in the same directory based on ship name.
        Collects local addresses to downloaded files in self.dcdb_docs.
        Requests text doc creation for list of file addresses."""

        self.dwnld_location()

        # Download line files from AWS
        resource = boto3.resource('s3', config=Config(signature_version=UNSIGNED))
        bucket = resource.Bucket(self.dcdb_bucket)

        file_count = 0
        proc_counter = 0
        skip_count = 0
        for obj in dcdb_aws:
            # Create target by concatenating data path and aws object
            # ex: {C:\Users\user\Desktop\Thesis\User_Output_Location\dcdb\COPPER STAR\} +
            # {20190222113324825195_7cb9a8c2-5d2a-4c91-ac35-13fd2340a589_pointData.csv}
            target = f"{self.data_paths[file_count]}{obj[18:]}"
            target_exists = Path(target).exists()

            try:
                # Collect file size of file in dcdb bucket for comparison to previously downloaded versions
                object_size = bucket.Object(obj).content_length
            # If the file does not exist in the AWS bucket, skip it.
            except botocore.exceptions.ClientError as e:
                e = str(e)
                if e == "An error occurred (404) when calling the HeadObject operation: Not Found":
                    self.status_update_signal.emit(
                        f'<p style="color:#CCA70E"> {obj[19:]} does not exist in DCDB AWS bucket. </p>'
                        f'Skipping.')
                    proc_counter += 1
                    skip_count += 1
                    continue

            self.dcdb_docs.append(target)
            # Target directory has file in it that is the same, skip download
            if target_exists and (Path(target).stat().st_size == object_size):
                self.status_update_signal.emit(
                    f'<p style="color:#CCA70E"> Skipping existing file at: {self.data_paths[file_count]}</p>')
                self.trackline_signal.emit(self.tracklines[proc_counter])
                proc_counter += 1
                continue

            # Target directory has a file that is corrupt. Move bad file to archive
            elif target_exists and (Path(target).stat().st_size != object_size):
                source = Path(target)
                self.status_update_signal.emit(f'<p style="color:#CCA70E"> Moving bad {obj[18:]} to Archive</p>')
                source.rename(source.parent / "Archive" / source.name)
                self.status_update_signal.emit(f'<p style="color:#11B01A"> '
                                               f'Downloading: {obj[19:]} to {self.data_paths[file_count]}</p>')
                self.trackline_signal.emit(self.tracklines[proc_counter])
                proc_counter += 1
                bucket.download_file(obj, target)

            # File does not exist in directory, download
            elif not target_exists:
                self.status_update_signal.emit(f'<p style="color:#11B01A"> '
                                               f'Downloading: {obj[19:]} to {self.data_paths[file_count]}</p>')
                self.trackline_signal.emit(self.tracklines[proc_counter])
                proc_counter += 1
                bucket.download_file(obj, target)

            if file_numbers[file_count] == proc_counter:
                file_count += 1

            # end the process and print status if none of the selected files are available in S3 Bucket.
        if file_numbers[-1] == skip_count:
            self.status_update_signal.emit(f'<p style="color:#CCA70E"> '
                                           f'\nNo DCDB data available for the desired track lines.'
                                           f'\n Double check vessel spelling. '
                                           f'Otherwise, data for requested vessel(s) may not be available in'
                                           f' DCDB S3 holdings.</p>')
            self.status_update_signal.emit(f'<p style="color:#1C5BC2"> \nRequest Cancelled.</p>')
            self.processes_complete = self.total_processes
            self.curr_proc_signal.emit(self.processes_complete)
            return

        # If files were collected, create a plain text file of local addresses.
        if file_numbers[-1] == proc_counter:
            # add to process count
            self.processes_complete += 1
            self.curr_proc_signal.emit(self.processes_complete)
            self.status_update_signal.emit(
                f'<p style="color:#000000"> DCDB Download Complete. Writing location file.</p>')
            self.write_dcdb_docs_file()

    def dcdb_cloud(self, dcdb_aws) -> None:
        """Collects a list of S3 URLs to desired vessel trackline data in the DCDB bucket for cloud based processing.
        Will collect URLs to all files associated with the desired S3 objects and places
        them in a list called self.dcdb_urls.
        Requests text doc creation for list of file URLs."""

        resource = boto3.resource('s3', config=Config(signature_version=UNSIGNED))
        proc_count = 0

        # Determine if desired files exist in the AWS bucket
        for obj in dcdb_aws:
            try:
                resource.Object(self.dcdb_bucket, obj).load()
            # If the file does not exist in the AWS bucket, skip it.
            except botocore.exceptions.ClientError as e:
                e = str(e)
                if e == "An error occurred (404) when calling the HeadObject operation: Not Found":
                    self.status_update_signal.emit(
                        f'<p style="color:#CCA70E"> {obj[19:]} does not exist in DCDB AWS bucket. Skipping</p>')
                    proc_count += 1
                    pass
            # If the file does exist, build its URL
            else:
                url = f"s3://{self.dcdb_bucket}/{obj}"
                self.dcdb_urls.append(url)
                self.trackline_signal.emit(self.tracklines[proc_count])
                proc_count += 1
        # If no files are found, cancel the process
        if len(self.dcdb_urls) == 0:
            self.status_update_signal.emit(f'<p style="color:#CCA70E"> '
                                           f'\nNo DCDB data available for the desired track lines.'
                                           f'\n Double check vessel spelling. '
                                           f'Otherwise, data for requested vessel(s) may not be available in'
                                           f' DCDB AWS offerings.</p>')
            self.status_update_signal.emit(f'<p style="color:#1C5BC2"> \nRequest Cancelled.</p>')
            self.processes_complete = self.total_processes
            self.curr_proc_signal.emit(self.processes_complete)

        # If files do exist, request creation of txt file containing URL list
        if len(dcdb_aws) == proc_count:
            # add to process count
            self.processes_complete += 1
            self.curr_proc_signal.emit(self.processes_complete)
            self.status_update_signal.emit(
                f'<p style="color:#000000"> DCDB url compilation complete. Writing to file</p>')
            self.write_dcdb_txt_file()

    def charts_from_tracks(self) -> None:
        """Determines which MCD Charts the collected DCDB CSB data intersects.
        Initiates nbs data discovery process."""
        bands = [1, 2, 3, 4]  # these are the layer number for chart bands 2-5 in the ARC API
        self.status_update_signal.emit(
            f'<p style="color:#000000"> Determining charts that intersect selected track lines.'
            f' This may take some time.</p>')

        payload = {'timeRelation': 'esriTimeRelationOverlaps',
                   'geometry': '{"paths":%s,"spatialReference":{"wkid":4326}}' % self.tracklines,
                   'geometryType': 'esriGeometryPolyline',
                   'inSR': '4326',
                   'spatialRel': 'esriSpatialRelIntersects',
                   'units': 'esriSRUnit_Foot',
                   'outFields': '*',
                   'returnGeometry': 'false',
                   'returnTrueCurves': 'false',
                   'returnIdsOnly': 'false',
                   'returnCountOnly': 'false',
                   'returnZ': 'false',
                   'returnM': 'false',
                   'returnDistinctValues': 'false',
                   'returnExtentOnly': 'false',
                   'sqlFormat': 'none',
                   'featureEncoding': 'esriDefault',
                   'f': 'pjson'}

        for band in bands:
            s = Template(
                'https://gis.charttools.noaa.gov/arcgis/rest/services/MarineChart_Services/Status_New_NOAA_ENCs/MapServer/$band_num/query')
            url = s.substitute(band_num=band)
            r = requests.post(url, data=payload)
            response_json = r.json()
            for file in response_json["features"]:
                if file["attributes"]["cell_name"] not in self.charts:
                    self.charts.append(file["attributes"]["cell_name"])

        self.data_source = 'nbs'
        self.data_paths = []

        # add to process count
        self.processes_complete += 1
        self.curr_proc_signal.emit(self.processes_complete)

        if self.process == "l":
            self.status_update_signal.emit(f'<p style="color:#000000"> Starting NBS download</p>')
        elif self.process == "c":
            self.status_update_signal.emit(f'<p style="color:#000000"> Starting NBS S3 URL Compilation</p>')
        self.nbs_chart_area(self.charts)

    def write_nbs_docs_file(self) -> None:
        """Writes text files to the NBS data directory selected by the user.
        One file will be created.
        File holds local file locations for nbs .tiff files."""
        directory = f"{self.data_storage}/{self.data_source}"
        date_time = datetime.now().strftime("%m_%d_%Y_%H%M%S")
        txt_file = f"{self.data_source}_filepaths_{date_time}.txt"
        complete_file = f"{directory}/{txt_file}"
        doc_file = open(complete_file, "w")

        # Write plain txt file for nbs data
        if self.data_source == "nbs":
            self.nbs_doc_file = complete_file
            for doc in self.nbs_docs:
                if not doc.endswith("xml"):
                    doc_file.write(f"{doc}\n")
            self.status_update_signal.emit(f'<p style="color:#11B01A"> {txt_file} created at {directory}.</p>')
            # add to process count
            self.processes_complete += 1
            self.curr_proc_signal.emit(self.processes_complete)
            doc_file.close()

            if self.get_csb:
                self.get_csb = False
                self.data_source = "dcdb"
                self.data_paths = []
                self.status_update_signal.emit(f'<p style="color:#000000"> Starting DCDB process.</p>')
                self.dcdb_by_area()

            elif not self.get_csb:
                self.status_update_signal.emit(
                    f'<p style="color:#1C5BC2"> Data Discovery Complete.</p>')
                self.processes_complete = self.total_processes
                self.curr_proc_signal.emit(self.processes_complete)
                if self.both_data:
                    self.reputation_calc()

    def write_dcdb_docs_file(self) -> None:
        """Writes text files to the NBS data directory selected by the user.
        One file will be created.
        File holds local file locations for dcdb .csv files."""
        directory = f"{self.data_storage}/{self.data_source}"
        date_time = datetime.now().strftime("%m_%d_%Y_%H%M%S")
        txt_file = f"{self.data_source}_filepaths_{date_time}.txt"
        complete_file = f"{directory}/{txt_file}"
        doc_file = open(complete_file, "w")

        # Write plain txt file for dcdb data
        if self.data_source == "dcdb":
            self.dcdb_doc_file = complete_file
            for doc in self.dcdb_docs:
                doc_file.write(f"{doc}\n")
            self.status_update_signal.emit(f'<p style="color:#11B01A"> {txt_file} created at {directory}.</p>')
            # add to process count
            self.processes_complete += 1
            self.curr_proc_signal.emit(self.processes_complete)
            doc_file.close()

            if self.get_charts:
                self.status_update_signal.emit(f'<p style="color:#000000"> Starting NBS process.</p>')
                self.get_charts = False
                self.data_paths = []
                self.charts_from_tracks()

            elif not self.get_charts:
                self.status_update_signal.emit(
                    f'<p style="color:#1C5BC2"> Data Discovery Complete.</p>')
                self.processes_complete = self.total_processes
                self.curr_proc_signal.emit(self.processes_complete)
                if self.both_data:
                    self.reputation_calc()

    def write_nbs_txt_file(self) -> None:
        """Writes text files to the NBS data directory selected by the user.
        One file will be created.
        File holds s3 url locations for NBS .tiff files."""
        directory = f"{self.data_storage}/{self.data_source}"
        date_time = datetime.now().strftime("%m_%d_%Y_%H%M%S")
        txt_file = f"{self.data_source}_S3URLpaths_{date_time}.txt"
        complete_file = f"{directory}/{txt_file}"
        url_file = open(complete_file, "w")

        # Write file for nbs data
        if self.data_source == "nbs":
            self.nbs_url_file = complete_file
            for url in self.nbs_urls:
                if not url.endswith("xml") and url != "N/A":
                    url_file.write(f"{url}\n")
            self.status_update_signal.emit(f'<p style="color:#11B01A"> {txt_file} created at {directory}.</p>')
            # add to process count
            self.processes_complete += 1
            self.curr_proc_signal.emit(self.processes_complete)
            url_file.close()

            if self.get_csb:
                self.get_csb = False
                self.data_source = "dcdb"
                self.data_paths = []
                self.status_update_signal.emit(f'<p style="color:#000000"> Starting DCDB process.</p>')
                self.dcdb_by_area()

            elif not self.get_csb:
                self.status_update_signal.emit(
                    f'<p style="color:#1C5BC2"> Data Discovery Complete.</p>')
                self.processes_complete = self.total_processes
                self.curr_proc_signal.emit(self.processes_complete)
                if self.both_data:
                    self.reputation_calc()

    def write_dcdb_txt_file(self) -> None:
        """Writes text files to the DCDB data directory selected by the user.
        One file will be created.
        File holds s3 url locations for DCDB .csv files."""
        directory = f"{self.data_storage}/{self.data_source}"
        date_time = datetime.now().strftime("%m_%d_%Y_%H%M%S")
        txt_file = f"{self.data_source}_S3URLpaths_{date_time}.txt"
        complete_file = f"{directory}/{txt_file}"
        url_file = open(complete_file, "w")

        # import pdb;
        # pdb.set_trace()  # Debugger
        # Write file for dcdb data
        if self.data_source == "dcdb":
            self.dcdb_url_file = complete_file
            for url in self.dcdb_urls:
                url_file.write(f"{url}\n")
            self.status_update_signal.emit(f'<p style="color:#11B01A"> {txt_file} created at {directory}.</p>')
            # add to process count
            self.processes_complete += 1
            self.curr_proc_signal.emit(self.processes_complete)
            url_file.close()

            if self.get_charts:
                self.status_update_signal.emit(f'<p style="color:#000000"> Starting NBS process.</p>')
                self.get_charts = False
                self.data_paths = []
                self.charts_from_tracks()

            elif not self.get_charts:
                self.status_update_signal.emit(
                    f'<p style="color:#1C5BC2"> Data Discovery Complete.</p>')
                self.processes_complete = self.total_processes
                self.curr_proc_signal.emit(self.processes_complete)
                if self.both_data:
                    self.reputation_calc()

    def reputation_calc(self):
        """Executes the Batch_Builder.py and provides it with the data discovered by the downloader."""
        # Create Batch Builder instance
        batch = BatchBuilder(self.status_update_signal, self.calc_proc_total_sig, self.calc_curr_proc_sig)
        batch.run = self.run_rep
        batch.data_storage = self.data_storage
        if self.process == 'l':
            nbs_data_pth = Path(self.nbs_doc_file)
            dcdb_data_pth = Path(self.dcdb_doc_file)
            batch.nbs_data = f"..\\..\\{nbs_data_pth.parent.name}/{nbs_data_pth.name}"
            batch.dcdb_data = f"..\\..\\{dcdb_data_pth.parent.name}/{dcdb_data_pth.name}"
        elif self.process == 'c':
            nbs_data_pth = Path(self.nbs_url_file)
            dcdb_data_pth = Path(self.dcdb_url_file)
            batch.nbs_data = f"..\\..\\{nbs_data_pth.parent.name}/{nbs_data_pth.name}"
            batch.dcdb_data = f"..\\..\\{dcdb_data_pth.parent.name}/{dcdb_data_pth.name}"
        batch.build_batch()

        # import pdb;
        # pdb.set_trace()  # Debugger
