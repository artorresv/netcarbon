from datetime import datetime
from typing import Any
from databases import Database
from asyncpg import Record
from fastapi import APIRouter, Depends, HTTPException, Path, Response

from db.utils import FileFormat, ProductName, get_database


router = APIRouter(
    prefix='/netcarbon', tags=['Spectral Indices']
)


@router.get(
    '/spectral_indices/{plot_id}_{product_date}_{spectral_index}_{srid}.{file_format}',
    response_class=Response,
    responses={200: {'content': {'image/tiff': {}}}}
)
async def print_spectral_index(
    plot_id: str,
    srid: int = 2154,
    product_date: str = Path(..., regex=r'20\d{2}\d{2}\d{2}'),
    spectral_index: ProductName = ProductName.ndvi,
    file_format: FileFormat = FileFormat.tiff,
    database: Database = Depends(get_database)
) -> Any:
    """Returns an spectral index encoded as a TIFF or PNG image

    Parameters
    ----------
        plot_id : int
            Plot identifier
        Output SRID : int
            Generated file will have this SRID. Only applies to GeoTiff format
        product_date : str
            Spectral index date, in YYYYMMDD format
        spectral_index : str
            ndvi or ndmi
        file_format : str
            Output format, tiff or png

    Returns
    -------
    Image:
        Image in binary format, encoded as a single band TIFF file with pixel values corresponding to
        NDVI or NDMI values, with 1 meter  spatial resolution.
        Or a RGBA PNG file, without spatial reference
    """

    db_function = f'Spectral_Index_As{file_format}'

    # Fetch an spectral index as PNG or GeoTiff file, the file is generated on the fly
    content: Record = await database.fetch_one(
        query=f'SELECT {db_function}(:plot_id, :spectral_index, :product_date, 1, :srid) AS image;',
        values={'plot_id': plot_id,
                'spectral_index': spectral_index,
                'product_date': datetime.strptime(product_date, '%Y%m%d').date(),
                'srid': srid}
    )

    if not content:
        raise HTTPException(
            status_code=404, detail="Requested image not found"
        )

    return Response(content=content.image,
                    media_type=f'image/{file_format}')
