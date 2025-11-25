This document describes how you can transform a series of XY coordinates from a CSV file using `BigWarp` in `FIJI`.

<b>Steps</b>:
1. <b>Place landmarks in BigWarp</b>
    - Load your moving and fixed images into `BigWarp`, place corresponding landmarks until they are nicely coregistered, and export the landmarks.csv (see detailed explanation in README.md). One of your images should be in the same coordinate space as the XY coordinates (preferably the moving image, but this can be reversed later if needed). The other image should be in the coordinate space you wish to transform the coordinates into (the fixed image).
    - Optionally, export the warped moving image at this time as well (see README.md).
2. <b>Transform the XY coordinates according to the BigWarp transformation</b>
    - Open the `warp_points_bigwarp.groovy` script from this repository in FIJI.
    - Select the landmarks.csv file produced by BigWarp.
    - Select the CSV containing your XY coordinates.
    - Pick a path to save the output CSV.
    - Specify which columns correspond to the X and Y coordinates (usually `x` and `y`).
    - Choose names for the output columns (e.g. `x_warped`, `y_warped`).
    - Pick the transformation model (e.g. Thin Plate Spline, Affine, ...).
    - Apply scaling to the moving and/or fixed landmark coordinates if needed. Depending on how you use BigWarp, the landmark coordinates can be in pixels, micrometers, millimeters, ...
    - Optionally, swap the moving and fixed landmarks. If unchecked, the script will transform from moving image to fixed image. If checked, the transformation direction will be reversed.