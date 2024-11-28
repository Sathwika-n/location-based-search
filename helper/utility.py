import server_properties

import logger
log = logger.get_logger()

url = server_properties.GOOGLE_PLACES_API_BASE_URL
api_key = server_properties.GOOGLE_API_KEY

def build_places_url(location, radius, keyword='restaurant'):
    return f"{url}?location={location}&radius={radius}&keyword={keyword}&key={api_key}"
