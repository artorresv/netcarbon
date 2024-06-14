from math import cos, pi
from shapely.ops import transform
from pyproj import Transformer, CRS

from shapely import Geometry
from shapely.geometry import Polygon, MultiPolygon


def crs_transform(from_crs: str, to_crs: str, geometry: Geometry) -> Geometry:
    return transform(
        Transformer.from_crs(CRS(from_crs), CRS(to_crs), always_xy=True).transform,
        geometry
    )


def meters_to_decimal_degrees(meters: float, latitude: float) -> float:
    """Converts meters to decimal degrees, using an approximation based on the latitude

    Parameters
    ----------
        meters : float
        latitude : float

    Returns
    -------
    float
        An approximated equivalent of the provided number, in meters, to decimal degrees
    """

    # Taken from here:
    # https://stackoverflow.com/questions/25237356/convert-meters-to-decimal-degrees/25237446#25237446

    if meters < 0:
        raise ValueError('Meters must be a positive float number')

    if latitude < -90 or latitude > 90:
        raise ValueError('Latitude must be a value between +90 and -90')

    return (meters / (111.32 * 1000 * cos(latitude * (pi / 180))))


def remove_polygon_holes(polygon: Polygon) -> MultiPolygon:
    # Taken from here
    # https://gis.stackexchange.com/questions/409340/removing-small-holes-from-the-polygon/409398#409398

    list_interiors = []
    eps = 1000

    for interior in polygon.interiors:
        p = Polygon(interior)
        if p.area > eps:
            list_interiors.append(interior)

    return MultiPolygon([Polygon(polygon.exterior.coords, holes=list_interiors)])
