# VBI-Compare
Compare Volunteered Bathymetric Information (VBI) to authoritative data for reputation calculations.

The user manual for VBI Compare is located [HERE](scripts/gui/Manual)

**Note:** CSB Python, the necessary files for the Calder Reputation Alorgithm, are not currently publicly available,
so the functionality of VBI Compare to execute a reputation calculation is not currently available.

## Installation
### Download Basemap
Create a folder in VBI-Compare\scripts\gui called "BaseMap."

> Navigate to [Natural Earth Data](https://www.naturalearthdata.com/downloads/10m-raster-data/10m-natural-earth-1/) and download
> "Natural Earth 1 with Shaded Relief, Water, and Drainages."

Extract all the downloaded files to the previously created BaseMap folder.

### Install OSGeo4W
Install OSGeo4W using stand alone installer Long Term Release 3.28.
> See the [OSGeo4W Installers](https://qgis.org/en/site/forusers/alldownloads.html#osgeo4w-installer) page for 
> installer download links and steps.

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
  Run pip install .
```

## Usage
### Starting VBI Compare
Navigate to and run `VBI-Compare\scripts\gui\cmd.qgis.cmd`
In the resulting command prompt run the following line ensuring the `<VBI-Compare location>` is updated.
```
cd C:\<VBI-Compare location>\VBI-Compare
```
Then run the following:
```
python scripts\gui\VBICompare_Main_GUI.py
```

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
