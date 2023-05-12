# VBI-Compare
Compare Volunteered Bathymetric Information (VBI) to authoritative data for reputation calculations.

VBI Compare was created by the Center for Coastal and Ocean Mapping (CCOM) to compare Volunteered Bathymetric Information (VBI) to collocated authoritative data for reputation calculations. Currently, it is functional for US waters only using the [National Bathymetric Source (NBS)](https://www.nauticalcharts.noaa.gov/data/bluetopo.html) as its authoritative data source. The goal of this program is to quickly collect VBI and NBS data to determine the quality of the VBI source and data. Based on user inputs, the program collects the desired data for comparison from the Amazon Web Service S3 bucket holdings of the NBS and the Crowd Sourced Bathymetry holdings of the [Data Centre for Digital Bathymetry (DCDB)](https://www.ngdc.noaa.gov/iho/). Data is then optionally donwloaded or URLs to the data in the cloud are collected. A batch file is created to initiate the reputation calculation. The batch file can be run immediately or stored for later and processed via a command prompt.

The user manual for VBI Compare is located [HERE](scripts/gui/Manual).

**Note:** These installation steps are required for this stand alone version of VBI-Compare. Once VBI-Compare is added to 
hydrographic tool suites such as [Pydro](https://nauticalcharts.noaa.gov/data/tools-apps.html) or [Hydroffice](https://www.hydroffice.org/), 
these requirements would no longer be required.

**Note:** CSB Python, the necessary files for the Calder Reputation Alorgithm, are not currently publicly available,
so the functionality of VBI Compare to execute a reputation calculation is not currently available.

## Installation
### Download Basemap
Create a folder in VBI-Compare\scripts\gui called "BaseMap."

> Navigate to [Natural Earth Data](https://www.naturalearthdata.com/downloads/10m-raster-data/10m-natural-earth-1/) and download
> "Natural Earth 1 with Shaded Relief, Water, and Drainages: large size"

Extract all the downloaded files to the previously created BaseMap folder.

### Install QGIS Using the OSGeo4W Installer
Install QGIS LTR (version 3.28) using the installer.
> See the [OSGeo4W Installers](https://qgis.org/en/site/forusers/alldownloads.html#osgeo4w-installer) page for 
> installer download links and steps.

Use the Advanced Install method

On the "Select Packages" window, expand Desktop and select qgis-ltr 3.28.x.

Click "Next"

When warned of unmet dependencies, for QGIS, make sure to enable `Install these packages to meet dependencies (RECOMMENDED).`

## Usage
### Starting VBI Compare
Navigate to and run `VBI-Compare\scripts\gui\cmd.qgis.cmd`
In the resulting command prompt run the following line ensuring the `<VBI-Compare location>` is updated.
```
cd ..\..\
```
Then run the following:
```
python -m pip install boto3
python scripts\gui\VBICompare_Main_GUI.py
```
> Note: `boto3` is a Python library used to interact with AWS services like S3

**File Descriptions**
### VBICompare_Main_GUI
Creates the main GUI window
  
### User_Inputs_GUI
Creates the tabs and all widgets within the main GUI window.

### Area_Search_GUI
Creates the pop-up window including its widgets for visual selection of a search area from the the main GUI.
  
### Monitoring_Win_GUI
Creates the pop-up window including its widgets for monitoring the data and providing status updates

### nbs_dcdb_downloader
Executes the data collection and management as described in the manual based on the inputs provided by the user in the main GUI.
Provides status updates to the monitoring window.
  
### Batch_Builder
Builds and conditionally executes a batch file which operates the CSB python scripts for the Calder Reputation Alorithm.

## Using with CSB Python

When CSB-Python is released, these additional steps will be required in order to use it in combination with VBI-Compare

### Install Miniconda3
Install Minicond3 Windows 64-bit for Python version 3.9.
> See the [Miniconda Installers](https://docs.conda.io/en/latest/miniconda.html#windows-installers) page for 
> installer download links and steps.

### Environment Setup
* Open a command prompt
* Enter the following code ensuring the `<VBI-Compare location>` is updated.
```
 cd C:\<VBI-Compare location>\VBI-Compare
```
* Run the following code in the command prompt.
```
call scripts\install\activate_env.bat
```
* Activate the conda environment by running this line in the command prompt.
```
pip install .
```
