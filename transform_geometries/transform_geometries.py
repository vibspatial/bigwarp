from typing import Union
from pathlib import Path
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon, MultiPolygon, Point, MultiPoint, LineString, MultiLineString
import json

def convert_geometries_for_bigwarp(
    input_data: Union[str, Path, gpd.GeoDataFrame], 
    output_csv: Union[str, Path, None] = None,
) -> Union[pd.DataFrame, None]:
    """
    Extracts coordinates from geometries from a GeoJSON file or GeoDataFrame and saves them in a CSV format or pandas DataFrame
    suitable for transformations using BigWarp in FIJI (see `warp_points_bigwarp.groovy` script). 
    For reconstruction of geometries in new coordinate space after BigWarp transformation see `create_warped_geojson`.

    The output CSV/DataFrame will include:
        - geometry_type: type of geometry (Polygon, MultiPolygon, Point, MultiPoint, LineString, MultiLineString are supported).
        - x, y: coordinates of the points in the original coordinate space.
        - coords: set to 'coords' if coordinates belong to exterior, 'interior_coords' if coordinates part of polygon interiors (required for reconstruction of the geometries in the new coordinate space).
        - row_id: the index of the feature in the original GeoJSON (required for reconstruction of the geometries in the new coordinate space).
        - polygon_id: index of the polygon within a MultiPolygon (required for reconstruction of the geometries in the new coordinate space).
        - interior_id: index of the interior ring within a polygon (if any; required for reconstruction of the geometries in the new coordinate space).
        - other metadata columns from the original GeoJSON.

    Args:
        input_data (str, Path, or GeoDataFrame): 
            Path to a GeoJSON file or a GeoDataFrame containing geometries.
        output_csv (str, Path, optional): 
            Path to the output CSV file. If None, returns DataFrame.
    
    Returns:
        DataFrame if output_csv is None, else None (CSV saved to disk).
    """
    
    # Load the input data
    if isinstance(input_data, gpd.GeoDataFrame):
        gdf = input_data.copy()
        print(f"Processing {len(gdf)} geometries from provided GeoDataFrame.")
    elif isinstance(input_data, (str, Path)):
        gdf = gpd.read_file(input_data)
        print(f"Loaded {len(gdf)} geometries from '{input_data}'.")
    else:
        raise TypeError("input_data must be a file path (str or Path) or a GeoDataFrame.")
    
    # Explode classification column from TissUUmaps/Qupath to avoid problems in groovy script.
    gdf = _explode_classification_column(gdf)
    
    # Create pandas DataFrame (keeping all columns)
    df = pd.DataFrame(gdf.drop(columns="geometry"))
    df["row_id"] = gdf.index
    df["geometry_type"] = gdf.geometry.type
    
    # Helper functions to extract coordinate tuples
    def _extract_coords(geom):
        if isinstance(geom, Polygon):
            return [list(geom.exterior.coords)]
        elif isinstance(geom, MultiPolygon):
            return [list(poly.exterior.coords) for poly in geom.geoms]
        elif isinstance(geom, Point):
            return [list(geom.coords)]
        elif isinstance(geom, MultiPoint):
            return [list(point.coords) for point in geom.geoms]
        elif isinstance(geom, LineString):
            return [list(geom.coords)]
        elif isinstance(geom, MultiLineString):
            return [list(line.coords) for line in geom.geoms]
        else:
            return None
        
    def _extract_interior_coords(geom):
        if isinstance(geom, Polygon) and geom.interiors:
            return [[list(interior.coords) for interior in geom.interiors]]
        elif isinstance(geom, MultiPolygon) and any(poly.interiors for poly in geom.geoms):
            return [[list(interior.coords) for interior in poly.interiors] for poly in geom.geoms]
        else:
            return None

    # Extract coordinates for all rows
    df["coords_list"] = gdf["geometry"].apply(_extract_coords)
    df["interior_coords_list"] = gdf["geometry"].apply(_extract_interior_coords)

    # Convert to long format
    rows = []

    for idx, row in df.iterrows():
        metadata = row.drop(["coords_list", "interior_coords_list"]).to_dict()
        
        coords_list = row["coords_list"]
        interior_coords_list = row["interior_coords_list"]
        
        if coords_list:
            for poly_idx, coords in enumerate(coords_list):
                for x, y in coords:
                    rows.append({
                        **metadata, "x": x, "y": y, "coords": "coords", "polygon_id": poly_idx, "interior_id": None}
                    )
                    
        if interior_coords_list:
            for poly_idx, poly_list in enumerate(interior_coords_list):
                for interior_idx, interior_coords in enumerate(poly_list):
                    for x, y in interior_coords:
                        rows.append({
                            **metadata, "x": x, "y": y, "coords": "interior_coords", "polygon_id": poly_idx, "interior_id": interior_idx}
                        )

    df_long = pd.DataFrame(rows)       

    # Save to CSV
    if output_csv:
        df_long.to_csv(output_csv, index=False)
        print(f"Saved {len(df_long)} coordinate rows from {len(gdf)} geometries to '{output_csv}'.")
        return None
    else:
        print(f"Returning DataFrame with {len(df_long)} coordinate rows from {len(gdf)} geometries.")
        return df_long


def create_warped_geometries(
    input_csv: Union[str, Path, pd.DataFrame],
    x_col: str,
    y_col: str,
    output_geojson: Union[str, Path, None] = None,
) -> Union[gpd.GeoDataFrame, None]:
    """
        Reconstructs geometries from a CSV or DataFrame containing BigWarp-transformed coordinates and metadata.
        Supports CSVs produced by `convert_geometries_for_bigwarp` after coordinate transformation
        (e.g., using `warp_points_bigwarp.groovy` script). Can return a GeoDataFrame or save to GeoJSON.

        The CSV/DataFrame must contain:
            - geometry_type: type of geometry (Polygon, MultiPolygon, Point, MultiPoint, LineString, MultiLineString are supported).
            - x_col, y_col: coordinates in the new coordinate space
            - coords: set to 'coords' if coordinates belong to exterior, 'interior_coords' if coordinates part of polygon interiors (required for reconstruction of the geometries in the new coordinate space).
            - row_id: the index of the feature in the original GeoJSON (required for reconstruction of the geometries in the new coordinate space).
            - polygon_id: index of the polygon within a MultiPolygon (required for reconstruction of the geometries in the new coordinate space).
            - interior_id: index of the interior ring within a polygon (if any; required for reconstruction of the geometries in the new coordinate space).
            - other metadata columns from the original GeoJSON (optional).

        Args:
            input_csv (str, Path, or DataFrame): 
                Path to the CSV or a pandas DataFrame.
            x_col (str): 
                Column name for X coordinates in warped space.
            y_col (str): 
                Column name for Y coordinates in warped space.
            output_geojson (str, Path, optional): 
                Path to save the reconstructed GeoJSON. If None, returns GeoDataFrame.

        Returns:
            GeoDataFrame if output_geojson is None, else None (GeoJSON saved to disk).
        """
        
    # Load input
    if isinstance(input_csv, pd.DataFrame):
        df_long = input_csv.copy()
        print(f"Using provided DataFrame with {len(df_long)} rows.")
    else:
        df_long = pd.read_csv(input_csv)
        print(f"Loaded {len(df_long)} rows from '{input_csv}'.")

    # Group by geometry ID
    geoms = []
    metadata_list = []

    for id, group in df_long.groupby("row_id"):
        geom_type = group["geometry_type"].iloc[0]
        metadata = group.iloc[0].drop(["row_id", "geometry_type", "x", "y", "coords", "polygon_id", "interior_id", x_col, y_col]).to_dict()

        if geom_type in ["Polygon", "MultiPolygon"]:
            polygons = []
            for polygon_id, polygon_group in group.groupby("polygon_id"):
                exterior_group = polygon_group[polygon_group["coords"] == "coords"]
                exterior = [(x, y) for x, y in zip(exterior_group[x_col], exterior_group[y_col])]

                interiors = []
                interior_rows = polygon_group[polygon_group["coords"] == "interior_coords"]
                if not interior_rows.empty:
                    for interior_id, interior_group in interior_rows.groupby("interior_id"):
                        interiors.append([(x, y) for x, y in zip(interior_group[x_col], interior_group[y_col])])

                polygons.append(Polygon(exterior, interiors))

            geom = polygons[0] if geom_type == "Polygon" else MultiPolygon(polygons)

        elif geom_type == "Point":
            geom = Point(group.iloc[0][x_col], group.iloc[0][y_col])

        elif geom_type == "MultiPoint":
            geom = MultiPoint([Point(x, y) for x, y in zip(group[x_col], group[y_col])])

        elif geom_type == "LineString":
            geom = LineString([(x, y) for x, y in zip(group[x_col], group[y_col])])

        elif geom_type == "MultiLineString":
            geom = MultiLineString([[(x, y) for x, y in zip(group[x_col], group[y_col])]])

        else:
            geom = None

        geoms.append(geom)
        metadata_list.append(metadata)

    gdf = gpd.GeoDataFrame(metadata_list, geometry=geoms, crs="EPSG:4326")
    if "name" in gdf.columns:
        gdf["name"] = gdf["name"].fillna("Annotation") # To avoid problems with None when reading in data in Qupath.
    
    # Rebuild classification column for Qupath/TissUUmaps
    gdf = _rebuild_classification_column(gdf)
    
    # Save new GeoJSON
    if output_geojson:
        gdf.to_file(output_geojson, driver="GeoJSON")
        print(f"Saved warped GeoJSON with {len(gdf)} geometries to '{output_geojson}'.")
        return None
    else:
        print(f"Returning GeoDataFrame with {len(gdf)} geometries.")
        return gdf
    

def _explode_classification_column(gdf):
    """
    Convert the nested 'classification' column into flat columns:
        - classification_name
        - classification_color_r/g/b

    Removes the original 'classification' column.
    """
    if "classification" not in gdf.columns:
        return gdf
    
    def parse_classification(c):
        if isinstance(c, str):
            try:
                c = json.loads(c)
            except json.JSONDecodeError:
                return None
        return c if isinstance(c, dict) else None

    gdf["classification"] = gdf["classification"].apply(parse_classification)

    # Prepare new columns
    gdf["classification_name"] = gdf["classification"].apply(
        lambda c: c.get("name") if isinstance(c, dict) else None
    )
    gdf["classification_color_r"] = gdf["classification"].apply(
        lambda c: c.get("color", [None, None, None])[0] if isinstance(c, dict) else None
    )
    gdf["classification_color_g"] = gdf["classification"].apply(
        lambda c: c.get("color", [None, None, None])[1] if isinstance(c, dict) else None
    )
    gdf["classification_color_b"] = gdf["classification"].apply(
        lambda c: c.get("color", [None, None, None])[2] if isinstance(c, dict) else None
    )

    # Drop nested dict
    gdf = gdf.drop(columns=["classification"])

    return gdf


def _rebuild_classification_column(gdf):
    """
    Combine flattened classification columns back into the
    original nested dictionary structure used by QuPath / TissUUmaps.
    """
    if "classification_name" not in gdf.columns:
        return gdf

    def _make_classification(row):
        name = row["classification_name"]
        r = row["classification_color_r"]
        g = row["classification_color_g"]
        b = row["classification_color_b"]

        if pd.isna(name):
            return None

        return {
            "name": name,
            "color": [int(r), int(g), int(b)]
        }

    gdf["classification"] = gdf.apply(_make_classification, axis=1)

    # Drop flattened columns
    gdf = gdf.drop(
        columns=[
            "classification_name",
            "classification_color_r",
            "classification_color_g",
            "classification_color_b",
        ]
    )

    return gdf


