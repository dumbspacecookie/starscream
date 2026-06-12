from geoalchemy2 import Geometry
from geoalchemy2.elements import WKTElement
from sqlalchemy import cast, func


def point_wkt(lat: float, lng: float) -> WKTElement:
    return WKTElement(f"POINT({lng} {lat})", srid=4326)


def location_lat(location_column):
    """Latitude from a Geography/Geometry POINT column."""
    return func.ST_Y(cast(location_column, Geometry))


def location_lng(location_column):
    """Longitude from a Geography/Geometry POINT column."""
    return func.ST_X(cast(location_column, Geometry))
