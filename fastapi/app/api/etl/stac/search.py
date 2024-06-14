from datetime import date, datetime
from itertools import groupby
import logging
from typing import Any, Callable

from satsearch import Search
from satsearch.search import SatSearchError
from satstac.itemcollection import ItemCollection
from shapely.geometry import shape, Polygon


group_by_scene_date: Callable[[ItemCollection], Any] = lambda scene: scene.date


def filter_items(items: Any, geometry: str) -> ItemCollection:
    valid_items: ItemCollection = []

    plot: Polygon = shape(geometry)
    min_cloud_cover: float
    best_match_scene: ItemCollection = None

    for scene_date, scenes_per_day in groupby(items, group_by_scene_date):
        min_cloud_cover = 100.0
        best_match_scene = None

        for scene in scenes_per_day:
            if shape(scene.geometry).contains(plot):
                current_cloud_cover = scene.properties['eo:cloud_cover']
                if current_cloud_cover <= min_cloud_cover:
                    min_cloud_cover = current_cloud_cover
                    best_match_scene = scene

        if best_match_scene:
            valid_items.append(best_match_scene)
        else:
            logging.info('Current plot is not fully contained in any Sentinel 2 scene')
            logging.info(f'This date {scene_date} will not be considered!')

    logging.info(f'Found {len(valid_items)} matching Sentinel 2 scenes...')

    return valid_items


def get_item_collection(start_date: date, end_date: date, geometry: str,
                        not_filter: bool = False) -> ItemCollection:

    _tz = datetime.now().astimezone().timetz()

    start_date = datetime.combine(start_date, _tz)
    end_date = datetime.combine(end_date, _tz)

    items: ItemCollection = []

    search = Search(
        url='https://earth-search.aws.element84.com/v1',
        limit=1000,
        intersects=geometry,
        datetime=f'{start_date.isoformat()}/{end_date.isoformat()}',
        collections=['sentinel-2-l2a']
    )

    try:
        if search.found() < 1:
            return items
    except Exception as e:
        logging.exception(e)

        if isinstance(e, SatSearchError):
            return items
        else:
            raise

    if not_filter:
        return search.items()

    return filter_items(items=search.items(), geometry=geometry)
