#@ File (label="Landmark file") landmarksPath
#@ File (label="Input points (csv)") inCsv
#@ File (label="Output points (csv)") outCsv
#@ String (label="X column name", value="x") xColName
#@ String (label="Y column name", value="y") yColName
#@ String (label="Output X column", value="x_warped") outXColName
#@ String (label="Output Y column", value="y_warped") outYColName
#@ String (label="Transformation type", choices={"Thin Plate Spline", "Affine", "Similarity", "Rotation", "Translation"}) transformType
#@ Double (label="Moving image scaling", value=1.0) scaleMoving
#@ Double (label="Fixed image scaling", value=1.0) scaleFixed
#@ Boolean (label="Reverse direction", value=false) swapLandmarks

import java.nio.file.*
import java.io.*
import bigwarp.landmarks.*
import bigwarp.transforms.*
import net.imglib2.realtransform.*

println "\n--- Landmarks file (first 4 lines) ---"
println "Name | Active | mvg-x | mvg-y | fix-x | fix-y"
landmarksPath.withReader { reader ->
    int count = 0
    reader.eachLine { line ->
        if (count < 4) {
            println line
            count++
        }
    }
}

// --- Helper: apply scaling to landmark coordinates ---
def scaleLandmarkColumns(String text, double scaleMoving, double scaleFixed) {
    def lines = []
    text.eachLine { line ->
        def parts = line.split(",", -1)
        if (parts.size() > 5) {
            try {
                // Moving coordinates
                parts[2] = (Double.parseDouble(parts[2].replaceAll('"','')) * scaleMoving).toString()
                parts[3] = (Double.parseDouble(parts[3].replaceAll('"','')) * scaleMoving).toString()
                // Fixed coordinates
                parts[4] = (Double.parseDouble(parts[4].replaceAll('"','')) * scaleFixed).toString()
                parts[5] = (Double.parseDouble(parts[5].replaceAll('"','')) * scaleFixed).toString()
            } catch (NumberFormatException e) {
                // Leave header or invalid lines unchanged
            }
        }
        lines << parts.join(",")
    }

    println "\n--- Landmarks after scaling ---"
    lines.take(4).each { println it }

    return lines.join("\n")
}

// --- Helper: swap fixed/moving landmark columns ---
def swapLandmarkColumns(String text) {
    def lines = []
    text.eachLine { line ->
        def parts = line.split(",", -1)
        if (parts.size() > 5) {
            def tmp2 = parts[2]; def tmp3 = parts[3]
            parts[2] = parts[4]; parts[3] = parts[5]
            parts[4] = tmp2; parts[5] = tmp3
        }
        lines << parts.join(",")
    }

    println "\n--- Landmarks after swapping ---"
    lines.take(4).each { println it }

    return lines.join("\n")
}

// --- Build the transform ---
def buildTransform(File landmarksPath, String transformType, int nd, boolean swapLandmarks, double scaleMoving, double scaleFixed) {
    def text = landmarksPath.text

    // Apply scaling to landmarks
    text = scaleLandmarkColumns(text, scaleMoving, scaleFixed)

    // Apply swap if requested
    if (swapLandmarks)
        text = swapLandmarkColumns(text)

    // Write scaled (and possibly swapped) version to temp file
    def tmpFile = File.createTempFile("landmarks_prepared_", ".csv")
    tmpFile.text = text
    tmpFile.deleteOnExit()

    // Load into LandmarkTableModel
    def ltm = new LandmarkTableModel(nd)
    ltm.load(tmpFile)

    def bwTransform = new BigWarpTransform(ltm, transformType)
    def xfm = bwTransform.getTransformation()

    if (xfm instanceof Wrapped2DTransformAs3D)
        xfm = ((Wrapped2DTransformAs3D) xfm).getTransform()

    return xfm.inverse()
}

// --- Read input CSV ---
List<String> lines
try {
    lines = Files.readAllLines(Paths.get(inCsv.getAbsolutePath()))
} catch (IOException e) {
    e.printStackTrace()
    return
}
if (lines.isEmpty()) {
    System.err.println("Error: Input CSV is empty.")
    return
}

// --- Parse header ---
String header = lines[0]
List<String> columns = header.split(",") as List
int xColIndex = columns.indexOf(xColName)
int yColIndex = columns.indexOf(yColName)
int outXColIndex = columns.indexOf(outXColName)
int outYColIndex = columns.indexOf(outYColName)

// Add output columns if missing
if (outXColIndex == -1) {
    columns.add(outXColName)
    outXColIndex = columns.size() - 1
}
if (outYColIndex == -1) {
    columns.add(outYColName)
    outYColIndex = columns.size() - 1
}
if ([xColIndex, yColIndex].contains(-1)) {
    System.err.println("Error: Could not find specified X/Y columns in CSV.")
    return
}

// --- Build transformation ---
def transform = buildTransform(landmarksPath, transformType, 2, swapLandmarks, scaleMoving, scaleFixed)
if (transform == null) return

// --- Apply transformation ---
println "\n--- Transforming coordinates ---"
List<String> outputLines = [columns.join(",")]
double[] result = new double[2]
int debugCount = 0      // Only print first few rows
int maxDebugRows = 10    // Number of rows to print for debugging
println "Printing first ${maxDebugRows} coordinates:"

for (int i = 1; i < lines.size(); i++) {
    List<String> values = lines[i].split(",", -1) as List
    while (values.size() < columns.size()) values.add("")

    try {
        double x = Double.parseDouble(values[xColIndex])
        double y = Double.parseDouble(values[yColIndex])

        double[] point = [x, y] as double[]
        transform.apply(point, result)

        values[outXColIndex] = String.format("%.6f", result[0])
        values[outYColIndex] = String.format("%.6f", result[1])

        if (debugCount < maxDebugRows) {
            println "Row ${i}: x = ${x}, y = ${y} --> ${outXColName} = ${values[outXColIndex]}, ${outYColName} = ${values[outYColIndex]}"
            debugCount++
        }

    } catch (Exception e) {
        System.err.println("Warning: Failed to transform row ${i + 1}: ${e.message}")
        values[outXColIndex] = "NaN"
        values[outYColIndex] = "NaN"
    }

    outputLines.add(values.join(","))
}

// --- Compute min/max for debugging ---
double minX = Double.POSITIVE_INFINITY
double maxX = Double.NEGATIVE_INFINITY
double minY = Double.POSITIVE_INFINITY
double maxY = Double.NEGATIVE_INFINITY
double minXTrans = Double.POSITIVE_INFINITY
double maxXTrans = Double.NEGATIVE_INFINITY
double minYTrans = Double.POSITIVE_INFINITY
double maxYTrans = Double.NEGATIVE_INFINITY

for (int i = 1; i < lines.size(); i++) {
    List<String> values = lines[i].split(",", -1) as List
    double x = Double.parseDouble(values[xColIndex].replaceAll('"','')) * scaleMoving
    double y = Double.parseDouble(values[yColIndex].replaceAll('"','')) * scaleMoving

    minX = Math.min(minX, x)
    maxX = Math.max(maxX, x)
    minY = Math.min(minY, y)
    maxY = Math.max(maxY, y)

    double[] point = [x, y] as double[]
    transform.apply(point, result)

    minXTrans = Math.min(minXTrans, result[0])
    maxXTrans = Math.max(maxXTrans, result[0])
    minYTrans = Math.min(minYTrans, result[1])
    maxYTrans = Math.max(maxYTrans, result[1])
}

println "\nMinimum and maximum values:"
println "   min X: ${minX} --> ${minXTrans}"
println "   max X: ${maxX} --> ${maxXTrans}"
println "   min Y: ${minY} --> ${minYTrans}"
println "   max Y: ${maxY} --> ${maxYTrans}"

println "\nTransformation complete. Processed ${outputLines.size() - 1} rows."

// --- Write output CSV ---
try {
    Files.write(Paths.get(outCsv.getAbsolutePath()), outputLines)
    println "\nOutput CSV written to: ${outCsv.getAbsolutePath()}"
} catch (IOException e) {
    e.printStackTrace()
}

println "\n--- Done! ---\n"


