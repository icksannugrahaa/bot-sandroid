import math
import random
import storage

# 1 degree of latitude is ~111km (111139 meters)
LAT_METER_DEG = 1.0 / 111139.0

def load_locations() -> dict:
    return storage.get_attendance_locations()

def save_location(name: str, lat: float, lng: float):
    storage.upsert_attendance_location(name, lat, lng)


def _meters_to_lng_deg(latitude: float) -> float:
    """Lng distance changes depending on latitude due to Earth's curvature."""
    return 1.0 / (111139.0 * math.cos(math.radians(latitude)))


def get_random_location(pool_type: str) -> dict:
    """
    Returns a random {lat, lng} within a 50m radius of the requested pool center.
    Default fallback is 'kanpus'.
    """
    pool_type = pool_type.lower()
    locations = load_locations()
    
    if pool_type in locations:
        center_lat, center_lng = locations[pool_type]
    elif "kanpus" in locations:
        # Default fallback to "kanpus"
        center_lat, center_lng = locations["kanpus"]
    else:
        # Failsafe if db is empty
        center_lat, center_lng = (-6.216556144511367, 106.81407082204778)

    # Generate random distance up to 50m
    max_radius_m = 50.0
    r = max_radius_m * math.sqrt(random.random())
    theta = random.random() * 2 * math.pi

    # Offset in meters
    dx = r * math.cos(theta)
    dy = r * math.sin(theta)

    # Offset in degrees
    d_lat = dy * LAT_METER_DEG
    d_lng = dx * _meters_to_lng_deg(center_lat)

    return {
        "lat": center_lat + d_lat,
        "lng": center_lng + d_lng
    }
