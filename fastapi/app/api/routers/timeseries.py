from json import loads
from typing import Any
from databases import Database
from asyncpg import Record
from fastapi import APIRouter, Depends, HTTPException, status

from db.utils import ProductName, get_database


router = APIRouter(
    prefix='/netcarbon', tags=['Time Series']
)


@router.get(
    '/timeseries/{plot_id}/{spectral_index}/mean',
    status_code=200
)
async def get_means_time_serie(
    plot_id: str,
    spectral_index: ProductName = ProductName.ndvi,
    database: Database = Depends(get_database)
) -> Any:

    content: Record = await database.fetch_one(
        query='''SELECT json_object_agg(product_date, mean) AS timeserie
                 FROM spectral_indices_stats
                 WHERE plot_id = :plot_id AND product_name = :spectral_index;''',
        values={'plot_id': plot_id, 'spectral_index': spectral_index}
    )

    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="There's no data for the given parameters"
        )

    return loads(content.timeserie)
