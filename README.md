# Bigwarp Zarr to OME TIFF

This document describes how to export Zarr-files from Bigwarp, and then convert them to single-channel OME-TIFF files.

While it is also possible to export TIFF-files, occasionally you may experience an error that prohibits exporting (depending on the size and overlap of the input images) and the channel names will not be preserved upon exporting. Exporting to .zarr seems to avoid these problems, which typically occurs has when exporting "large" warped images, for example images with more than ~2 billion pixels. 

## Prerequisites

Create and activate a conda environment from the `environment.yml` file:

```bash
conda env create -f environment.yml
conda activate zarr-ometiff
```

We used the following versions of Fiji/ImageJ:

- ImageJ 1.54f

and for BigWarp:

- Fiji.app/jars/bigdataviewer-playground-0.8.1.jar
- Fiji.app/jars/bigdataviewer-biop-tools-0.8.3.jar

You can download a zip archive with this exact combination of Fiji and BigWarp [here](https://objectstor.vib.be/s00-spatial.catalyst-team/sw/fiji-bigwarp/fiji-win64-bigwarp-rel1.zip). After downloading, unpack the zip file in any folder you like.

## Creating a Bigwarp dataset

To create a dataset for use in Bigwarp, start the Fiji version from the prerequisites above, and open this menu:

`Plugins > BigDataViewer-Playground > BDVDataset > Create BDV Dataset [Bio-Formats]`

A dialog like this will appear:

![bdv](docs/create_bdv_dataset_bioformats.png)

Add the file you want to use as fixed reference, and the files that need to be registered to this reference.

IMPORTANT: *Make sure to set the `Plane Origin Convention` to `TOP LEFT`!*

The plane origin convention influences the coordinate system that will be used for representing landmark coordinates, but surprisingly, it also seems to influence what part of the images will be warped. If it is set to "middle", then only the bottom left quadrant of the images seems to be saved to .zarr (!).

## Launch Bigwarp

Start Bigwarp via `Plugins > BigDataViewer-Playground > Sources > Register > Launch BigWarp`.

A dialog appears that allows you to specify the images to use as fixed reference (they will not be warped), and the moving images (they will be warped onto the fixed image(s)). Typically one selects a single DAPI image as fixed reference, and all channels from the dataset that needs to be registered onto this fixed reference, as the moving images.

![bdv](docs/launch_bigwarp.png)


## Placing landmarks

To register the moving image(s) to the fixed image, you will need to place landmarks until you get good alignment. Below, we will explain some general guidelines and tips, but for a full list of navigation and editing commands, press `F1` or read the [BigWarp documentation](https://imagej.net/plugins/bigwarp).

- Go to `Setting > Brightness and Color` to adjust the visualization of your images.
- Using left-click and drag, you can rotate one of the images until they are in the same orientation. You can use right-click and drag to pan (move) the image and the mouse wheel to zoom in and out until you find corresponding landmarks.
- Enter landmark mode by pressing the space bar. You can now left-click a cell (or another recognizable feature) in one of the images and subsequently left-click the corresponding cell/feature in the other image. A landmark will now have been added to the Landmarks dialog. It is also possible to delete landmarks by right-clicking them in the Landmarks dialog. When you want move around, make sure to disable landmark mode by pressing the space bar again.
- You will need at least 4 landmarks before you can warp the moving image onto the fixed image and assess the registration quality. Click on the title bar of the fixed or moving image and press F to display a fusion of both images. Press T to warp the moving image onto the fixed image. You will need to place many more landmarks to obtain a nice registration, but after the first 4 landmarks, you can more easily find the corresponding regions by clicking the title bar of one of the images and pressing Q to display the region corresponding to the window of the other image.
- Save your landmarks regularly via `Bigwarp window > File > Export Landmarks`. If you need to stop and close Bigwarp, you can import these landmarks again at a later timepoint.

![bdv](docs/save_landmarks.png)

## Exporting the warped moving image to Zarr

Once you are happy with the warped result shown interactively in Bigwarp, it is time to save the warped images. We will save to .zarr.

`Bigwarp window > File > Export moving image` 

Fill in the export parameters as in the example dialog below:

![bdv](docs/export_moving_image.png)

- threads

  The number of threads should be adapted to the hardware that Bigwarp is running on. Set it to a few cores less than the number of logical cores of the computer.
- File or n5 root: c:\full\path\to\warped_output.zarr

  Specify the path where the zarr should be saved to. It must end in `.zarr` to trigger zarr creation.
- n5 dataset: warped

  The dataset name is the name of the image "group" inside the zarr archive. Zarrs can hold multiple image groups, but we will only write one, so for our purpose it is not very relevant. Set it to a simple string, like "warped" or so.
- n5 block size: 2048
- n5 compression: gzip

Press OK. Warping should start, and progress feedback will be shown in the Console window in Fiji. Progress updates are only done occassionally, with relatively large jumps.

![bdv](docs/progress_feedback.png)

## Converting Bigwarp Zarr to OME TIFF

Once the .zarr file is saved from Bigwarp, you can quit Fiji.

Then, in the conda environment created earlier, convert the .zarr file to OME TIFF with `bigwarp-zarr-to-ometiff.ipynb'.

