from datetime import datetime
from databases import Database
from numpy import float64, isnan, isnat, nan, datetime_as_string
from xarray import DataArray
import rioxarray  # noqa: F401
import numpy.typing as npt
from rasterio import MemoryFile

DEFAULT_NODATA_VALUE = -999


def array_to_geotiff(array: npt.NDArray, metadata: dict) -> bytes:

    with MemoryFile() as memfile:
        with memfile.open(**metadata, compress='DEFLATE', predictor=1) as dataset:
            if array.ndim == 3:
                dataset.write(array)
            else:
                dataset.write(array, indexes=1)

            del array

        return memfile.read()  # type: ignore


def data_array_to_rows(dataset: DataArray, unique_id: str, product_id: str) -> list[dict]:
    result: list = []

    for sample_index in range(dataset['time'].size):
        sample_data: DataArray = dataset[sample_index]
        sample_time: DataArray = sample_data.time.values

        if isnat(sample_time):
            continue

        if bool(isnan(sample_data).all().values) is True:  # type: ignore
            continue

        product_date = datetime.strptime(str(datetime_as_string(sample_time, 'D')), '%Y-%m-%d')

        sample_metadata: dict = {
            'crs': sample_data.rio.crs,
            'transform': sample_data.rio.transform(),
            'width': sample_data.rio.width,
            'height': sample_data.rio.height,
            'nodata': -999,
            'driver': 'GTiff',
            'count': 1,
            'dtype': float64
        }

        result.append(
            {'plot_id': unique_id,
             'product_name': product_id,
             'product_date': product_date,
             'rast': array_to_geotiff(array=sample_data.to_numpy(), metadata=sample_metadata)}
        )

    return result


def normalized_index(left_band: DataArray, right_band: DataArray,
                     cloud_mask: DataArray, crs_code: int) -> DataArray:
    """Compute a general form of normalized spectral index

    Parameters
    ----------
        left_band : xarray.DataArray
            Left hand operator
        right_band : xarray.DataArray
            Right hand operator
        cloud_mask : xarray.DataArray
            Cloud mask
        crs_code : int
            Target CRS code
        clip_geometry : Polygon
            Polygon to clip raster by

    Returns
    -------
    DataArray
        DataArray with the same dimmensions (time, x and y) as input bands
    """

    spectral_index: DataArray = (left_band - right_band) / (left_band + right_band)

    # Set pixels that match the cloud mask to nan
    spectral_index = spectral_index.where(~cloud_mask, other=nan)

    # Keep only pixels greather than -1, others are set to nodata
    spectral_index = spectral_index.where(lambda x: x >= -1, other=DEFAULT_NODATA_VALUE)

    # Explicitly set the nodata value in the metadata
    spectral_index.rio.write_nodata(DEFAULT_NODATA_VALUE, encoded=True,
                                    inplace=True).astype('float64')

    # Explicitly set the CRS code in the metadata
    spectral_index.rio.write_crs(f'epsg:{crs_code}', inplace=True)

    return spectral_index


async def apply_storage_optimizations(db_conn: Database) -> None:

    # Create spatial index on raster convex hulls
    await db_conn.execute('CREATE INDEX ON public.products USING gist (st_convexhull(rast));')

    # Apply raster constraints
    await db_conn.execute('''SELECT AddRasterConstraints('public'::name, 'products'::name,
                             'rast'::name, 'srid', 'pixel_types', 'num_bands',
                             'nodata_values', 'scale_x', 'scale_y');''')

    # Compute statistics
    await db_conn.execute('ANALYZE public.products;')

    # Refresh spectral indices stats view
    await db_conn.execute('REFRESH MATERIALIZED VIEW spectral_indices_stats;')
