import asyncio
from csv import reader
from argparse import ArgumentParser, FileType
import logging
from typing import Any
from datetime import date
from databases import Database
from numpy import nan
import stackstac

from shapely import from_wkt
from shapely.geometry import Polygon

from etl.stac.search import get_item_collection
from db.utils import get_database
from utils.datetime import date_from_string
from etl.tools.geometry import crs_transform, meters_to_decimal_degrees, remove_polygon_holes
from etl.tools.raster import apply_storage_optimizations, normalized_index, data_array_to_rows

from xarray import DataArray
import rioxarray  # noqa: F401


DEFAULT_CRS = 2154
DEFAULT_BUFFER = 15  # in meters


async def generate_series(start_date: date, end_date: date, input_file: Any,
                          db_conn: Database, load: bool = True) -> int:

    plots = reader(input_file)
    headers = next(input_file)

    for col_index, col_header in enumerate(headers.split(',')):
        if col_header == 'geometry':
            geometry_index = col_index

        if col_header == 'ID_PARCEL_2022':
            parcel_id_index = col_index

    for plot in plots:

        plot_id = plot[parcel_id_index]

        # Geometry in the default CRS
        default_crs_geometry: Polygon = remove_polygon_holes(from_wkt(plot[geometry_index]))

        # Geometry in WGS 84 coordinates
        wgs84_geometry: Polygon = crs_transform(f'EPSG:{DEFAULT_CRS}', 'EPSG:4326',
                                                default_crs_geometry)

        items = get_item_collection(start_date=start_date, end_date=end_date,
                                    geometry=wgs84_geometry.__geo_interface__)

        # Sentinel 2 bands are clipped with a 10 meters buffer, so there are
        # more pixels outside parcel borders
        wgs84_bounds = wgs84_geometry.buffer(
            meters_to_decimal_degrees(
                meters=DEFAULT_BUFFER,
                latitude=wgs84_geometry.centroid.y)).bounds

        sentinel_bands: DataArray = stackstac.stack(
            items=items,
            bounds_latlon=wgs84_bounds,
            assets=['red', 'nir', 'swir16', 'nir08', 'scl'],
            epsg=DEFAULT_CRS,
            resolution=10
        )

        sentinel_bands = sentinel_bands.compute()

        # Sentinel 2 uses 0 as nodata value
        sentinel_bands = sentinel_bands.where(lambda x: x > 0, other=nan)

        scl: DataArray = sentinel_bands.sel(band='scl').astype('uint8')

        cloud_mask: DataArray = scl.isin([2, 3, 8, 9, 11])

        ndvi: DataArray = normalized_index(left_band=sentinel_bands.sel(band='nir'),
                                           right_band=sentinel_bands.sel(band='red'),
                                           cloud_mask=cloud_mask,
                                           crs_code=DEFAULT_CRS)

        ndmi: DataArray = normalized_index(left_band=sentinel_bands.sel(band='nir08'),
                                           right_band=sentinel_bands.sel(band='swir16'),
                                           cloud_mask=cloud_mask,
                                           crs_code=DEFAULT_CRS)

        # Test raster creation, without loading any data into postgresql
        if not load:
            continue

        ndvi_rows = data_array_to_rows(ndvi, plot_id, 'ndvi')

        ndmi_rows = data_array_to_rows(ndmi, plot_id, 'ndmi')

        # Load the current parcel and all its spectral indices in a single transaction
        async with db_conn.transaction():
            try:
                await insert_plot(payload=(plot_id, default_crs_geometry.wkt), db_conn=db_conn)

                await insert_normalized_index(ndvi_rows, target_crs=DEFAULT_CRS, db_conn=db_conn)

                await insert_normalized_index(ndmi_rows, target_crs=DEFAULT_CRS, db_conn=db_conn)

            except Exception as e:
                logging.error(e)

    # Post processing database routines
    await apply_storage_optimizations(db_conn=db_conn)

    return 0


async def insert_plot(payload: tuple, db_conn: Database) -> None:
    plot_id, wkt_geometry = payload

    await db_conn.execute(query='INSERT INTO plots (id, geom) VALUES (:id, :geom);',
                          values={'id': plot_id, 'geom': wkt_geometry})


async def insert_normalized_index(rows: list[dict], target_crs: int, db_conn: Database) -> None:
    await db_conn.execute_many(query=f'''
                                INSERT INTO products (plot_id, product_name, rast, product_date)
                                VALUES (:plot_id,
                                        :product_name,
                                        ST_FromGDALRaster(:rast, {target_crs}),
                                        :product_date)
                                ON CONFLICT DO NOTHING;
                               ''', values=rows)


async def main() -> int:

    parser = ArgumentParser(
        description='''ETL modules to generate spectral indices based on Sentinel 2 images,
        and load the data into a database'''
    )

    parser.add_argument('-f', '--input-file', type=FileType(mode='r', encoding='utf-8'),
                        required=True,
                        help='CSV file with at least two columns: an identifier and a polygon encoded as WKB')
    parser.add_argument('-s', '--start-date', action='store', type=date_from_string,
                        required=True, help='Initial date to search for Sentinel 2 images')
    parser.add_argument('-e', '--end-date', action='store', type=date_from_string,
                        required=True, help='End date to search for Sentinel 2 images')
    parser.add_argument('--not-load', action='store_false',
                        required=False,
                        help='Search images and generate indices without loading data into the database')

    args = parser.parse_args()

    # Obtain an asynchronous database connection
    db_conn = get_database()

    await db_conn.connect()

    result = await generate_series(input_file=args.input_file,
                                   start_date=args.start_date,
                                   end_date=args.end_date,
                                   load=args.not_load,
                                   db_conn=db_conn)

    # Close DB connection
    await db_conn.disconnect()

    return result


if __name__ == "__main__":
    asyncio.run(main())
    exit(0)
