import datetime
from fastapi import HTTPException
import requests
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import server_properties
import logger
from helper import utility
from bs4 import BeautifulSoup
from helper import constants

from datetime import timedelta

log = logger.get_logger()

api_key = server_properties.GOOGLE_API_KEY
# Elasticsearch connection configuration
es = Elasticsearch(
    hosts=[server_properties.ES_HOST],
    http_auth=(server_properties.ES_USER, server_properties.ES_PASSWORD)
)

def get_lat_long(location):
    url = server_properties.GOOGLE_GEOCODE_API_BASE_URL
    params = {'address': location, 'key': api_key}
    response = requests.get(url, params=params, verify=False)
    log.info("Response Status Code: %s", response.status_code)
    data = response.json()

    if response.status_code == 200 and 'results' in data and data['results']:
        latitude = data['results'][0]['geometry']['location']['lat']
        longitude = data['results'][0]['geometry']['location']['lng']
        return latitude, longitude
    else:
        return None, None

def get_photo_url(photo_reference, api_key, max_width=400):
    """
    Given a photo reference, return the URL of the photo.
    max_width is the size of the photo to request.
    """
    base_url = "https://maps.googleapis.com/maps/api/place/photo"
    photo_url = f"{base_url}?maxwidth={max_width}&photoreference={photo_reference}&key={api_key}"
    return photo_url

def find_nearby_restaurants(api_key, location, user_id, radius=5000, keyword='restaurant'):
    log.info("Inside find_nearby_restaurants")
    user_id1 = radius

    # First, try to get latitude and longitude for the given location
    latitude, longitude = get_lat_long(location)
    if latitude is None or longitude is None:
        raise HTTPException(status_code=400, detail="Error while fetching latitude or longitude")
    radius = user_id
    user_id = user_id1
    
    print("latitude",latitude,"longitude",longitude,"radius",radius,"user_id",user_id)
    print("radius in miles ",radius)
    radius_in_meters = radius * 1609.34
    print("radius_in_meters",radius_in_meters)


    # Check if nearby restaurants are cached in Elasticsearch
    cached_restaurants = get_cached_nearby_restaurants(latitude, longitude, radius_in_meters)
    if cached_restaurants:
        log.info("Found cached restaurants.")
        
        # Fetch user favorites
        print("user_id",user_id1)
        user_favorites = fetch_user_favorites(user_id1)
        print("user_favourite ",user_favorites)
        favorite_ids = {fav['id'] for fav in user_favorites} if user_favorites else set()
        
        # Add isFavorite flag to cached restaurants
        for restaurant in cached_restaurants:
            restaurant['isFavorite'] = restaurant['id'] in favorite_ids
        
        return cached_restaurants

    # If no cached restaurants, fetch from Google API
    location_str = f"{latitude},{longitude}"
    log.info(f"Fetching nearby restaurants from Google API near {location_str}...")
    url = utility.build_places_url(location_str, radius, keyword)
    response = requests.get(url, verify=False)

    log.info("Response Status Code: %s", response.status_code)
    response_data = response.json()

    if response.status_code == 200 and 'results' in response_data:
        results = response_data['results']
        if results:
            restaurants = []
            
            # Fetch user favorites
            user_favorites = fetch_user_favorites(user_id)
            favorite_ids = {fav['id'] for fav in user_favorites} if user_favorites else set()

            for place in results:
                restaurant_info = {
                    'id': place.get('place_id'),
                    'name': place.get('name'),
                    'address': place.get('vicinity'),
                    'rating': place.get('rating'),
                    'latitude': latitude,
                    'longitude': longitude,
                    'radius': radius,
                    'isFavorite': place.get('place_id') in favorite_ids  # Check if this restaurant is a favorite
                }

                # Check if photos are available
                if 'photos' in place:
                    photo_reference = place['photos'][0].get('photo_reference')
                    if photo_reference:
                        photo_url = get_photo_url(photo_reference, api_key)
                        restaurant_info['photo_url'] = photo_url

                restaurants.append(restaurant_info)

            # Store the fetched restaurants in Elasticsearch for future use
            store_nearby_restaurants(restaurants, latitude, longitude, radius)

            # Return sorted restaurants by rating (high to low)
            sorted_data = sorted(restaurants, key=lambda x: x['rating'], reverse=True)
            return sorted_data
        else:
            log.info("Found 0 restaurants.")
            return []
    else:
        log.error(f"Error fetching restaurants: {response_data.get('error_message', 'Unknown error')}")
        return []


# Helper method to fetch cached restaurants from Elasticsearch
def get_cached_nearby_restaurants(latitude, longitude, radius):
    #index_name = "restaurants"
    index_name = constants.RESTAURANTS_INDEX

    query = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"latitude": latitude}},
                    {"match": {"longitude": longitude}},
                    {"match": {"radius": radius}}
                ]
            }
        }
    }
    print("query -> ",query)
    response = es.search(index=index_name, body=query)
    if response['hits']['total']['value'] > 0:
        restaurants = [hit['_source'] for hit in response['hits']['hits']]
        log.info("Returning cached restaurants.")
        return restaurants
    else:
        return []
def store_nearby_restaurants(restaurant_data, latitude, longitude, radius):
    #index_name = "restaurants"
    index_name = constants.RESTAURANTS_INDEX
    actions = []
    
    # Prepare actions for the bulk API
    for restaurant in restaurant_data:
        # Add the additional fields for latitude, longitude, and radius
        restaurant['latitude'] = latitude
        restaurant['longitude'] = longitude
        restaurant['radius'] = radius

        # Prepare the document action for the bulk API
        action = {
            "_op_type": "index",  # Operation type: "index" means create or replace
            "_index": index_name,
            "_source": restaurant
        }
        actions.append(action)
    
    # Perform the bulk insert into Elasticsearch
    if actions:
        success, failed = bulk(es, actions)
        log.info(f"Bulk insert completed. {success} documents indexed, {failed} failed.")
    else:
        log.info("No restaurants to index.")

def get_restaurant_details(api_key, restaurant_id, user_id=None):
    # First, check if restaurant details are already cached in Elasticsearch
    cached_details = get_cached_restaurant_details(restaurant_id)
    if cached_details:
        log.info(f"Found cached details for restaurant ID: {restaurant_id}")
        # Add isFavorite flag if user_id is provided
        if user_id:
            user_favorites = fetch_user_favorites(user_id)
            favorite_ids = {fav['id'] for fav in user_favorites} if user_favorites else set()
            cached_details['isFavorite'] = restaurant_id in favorite_ids
        return cached_details

    # If not cached, fetch the details from Google Places API
    log.info(f"Fetching details for restaurant ID: {restaurant_id} from Google API...")
    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={restaurant_id}&key={api_key}"
    response = requests.get(url, verify=False)

    if response.status_code == 200:
        details = response.json().get('result', {})

        # Store the fetched details in Elasticsearch for future use
        store_restaurant_details(details)

        # Add isFavorite flag if user_id is provided
        if user_id:
            user_favorites = fetch_user_favorites(user_id)
            favorite_ids = {fav['id'] for fav in user_favorites} if user_favorites else set()
            details['isFavorite'] = restaurant_id in favorite_ids

        return details
    else:
        log.error(f"Error fetching details for restaurant ID {restaurant_id}: {response.content}")
        return {}
    

def store_restaurant_details(restaurant_details):
    # Index the restaurant details in Elasticsearch
    # index_name = "restaurants_details"
    index_name = constants.RESTAURANT_DETAILS
    restaurant_id = restaurant_details.get('place_id')
    if restaurant_id:
        es.index(index=index_name, id=restaurant_id, document=restaurant_details)
        log.info(f"Stored restaurant details for {restaurant_id} in Elasticsearch.")

# Get restaurant details from Elasticsearch (cached)
def get_cached_restaurant_details(restaurant_id):
    # index_name = "restaurants_details"
    index_name = constants.RESTAURANT_DETAILS
    query = {
        "query": {
            "match": {
                "restaurant_id": restaurant_id
            }
        }
    }
    response = es.search(index=index_name, body=query)
    if response['hits']['total']['value'] > 0:
        return response['hits']['hits'][0]['_source']
    else:
        return None

# Store reviews in Elasticsearch
def store_user_review(data: dict):
    #index_name = "user_reviews"
    print(data)
    user_id = data["user_id"]
    print(user_id)
    index_name = constants.USER_REVIEWS
    query = {
            "query": {
                "term": {
                    "user_id":user_id
                }
            }
        }

    res = es.search(index=constants.USER_INDEX, body=query)
    log.info("Fetched user info from index...")

    if res['hits']['total']['value'] == 0:
        return {"success": False, "error": "User Doesn't Exist"}

    user_data = res['hits']['hits'][0]['_source']

    # Create review data structure
    review_data = {
        "review_id": f"{user_id}_{data["restaurant_id"]}",
        "user_id": user_id,
        "restaurant_id": data["restaurant_id"],
        "rating": data["rating"],
        "review_text": data["review_text"],
        "created_at": datetime.datetime.utcnow().isoformat(),
        "author_name":user_data['username']
    }
    print(review_data)
    response = es.index(index=index_name, document=review_data)
    log.info(f"Stored review for user {review_data['user_id']} at restaurant {review_data['restaurant_id']}.")
    return response

def fetch_restaurant_reviews(api_key, restaurant_id):
    # Fetch restaurant details using the existing method
    result = get_restaurant_details(api_key, restaurant_id)
    log.info("Response received from get_restaurant_details method", result)

    # Extract the relevant data
    if 'reviews' in result and result['reviews']:
        reviews_data = []
        
        # Collect reviews
        for review in result['reviews']:
            review_info = {
                'user_name': review.get('author_name'),
                'rating': review.get('rating'),
                'text': review.get('text')
            }
            reviews_data.append(review_info)
        
        # Return the data: total ratings count and the reviews list
        return {
            'total_ratings_count': result.get('user_ratings_total', 0),
            'reviews': reviews_data
        }
    else:
        return {
            'total_ratings_count': 0,
            'reviews': []
        }


# Store restaurant reviews in Elasticsearch
def store_restaurant_review(review_data):
    # index_name = "restaurant_reviews"
    index_name = constants.RESTAURANT_REVIEWS
    response = es.index(index=index_name, document=review_data)
    return response

# Store user favorites in Elasticsearch
def store_user_favorite(favorite_data):
    # index_name = "user_favorites"
    index_name = constants.USER_FAVORITES
    response = es.index(index=index_name, document=favorite_data)
    return response

def fetch_user_favorites(user_id):
    # index_name = "user_favorites"
    index_name = constants.USER_FAVORITES
    query = {
        "query": {
            "match": {
                "user_id": user_id
            }
        }
    }
    
    # Fetch user favorites from Elasticsearch
    response = es.search(index=index_name, body=query)
    print(response)
    print(response['hits']['total']['value'])
    if(response['hits']['total']['value']==0):
        return response['hits']['total']['value']
    
    # List to store restaurant details
    restaurant_details_list = []
    
    # Loop through the favorites and fetch restaurant details
    for hit in response['hits']['hits']:
        restaurant_id = hit['_source']['restaurant_id']
        
        # Fetch restaurant details using the provided function
        details = get_restaurant_details(api_key, restaurant_id)
        
        if details:
            restaurant_info = {
                "id": restaurant_id,
                "name": details.get("name"),
                "location": extract_locality_from_adr_address(details.get("adr_address")),
                "map_url": details.get("url"),
                "rating": details.get("rating"),
                "image": get_photo_url(details.get("photos")[0]['photo_reference'], api_key) if details.get("photos") else None
            }
            
            restaurant_details_list.append(restaurant_info)
    
    return restaurant_details_list


def fetch_reviews_by_restaurant(restaurant_id):
    #index_name = "user_reviews"
    index_name = constants.USER_REVIEWS
    query = {
        "query": {
            "match": {
                "restaurant_id": restaurant_id
            }
        }
    }
    response = es.search(index=index_name, body=query)
    if response['hits']['total']['value'] > 0:
        reviews = [hit['_source'] for hit in response['hits']['hits']]
        log.info(f"Found {len(reviews)} reviews for restaurant {restaurant_id}.")
        return reviews
    else:
        log.info(f"No reviews found for restaurant {restaurant_id}.")
        return []
    
def fetch_reviews_by_user(user_id):
    log.info("fetching user reviews...")
    # index_name = "user_reviews"
    index_name = constants.USER_REVIEWS
    query = {
        "query": {
            "match": {
                "user_id": user_id
            }
        }
    }
    log.info(f"query -> {query}")
    response = es.search(index=index_name, body=query)
    if response['hits']['total']['value'] > 0:
        reviews = [hit['_source'] for hit in response['hits']['hits']]
        log.info(f"Found {len(reviews)} reviews for user {user_id}.")
        return reviews
    else:
        log.info(f"No reviews given by user {user_id}.")
        return []
    
def reverse_geocode(latitude, longitude,api_key):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={latitude},{longitude}&key={api_key}"
    response = requests.get(url,verify=False)
    if response.status_code == 200:
        result = response.json().get('results', [])
        if result:
            return result[0].get('formatted_address')
        else:
            raise Exception("Coordinates not found.")
    else:
        raise Exception(f"Error in reverse geocoding: {response.content}")
    
def get_reviews_with_restaurant_details(restaurant_id: str, api_key: str):
    log.info(f"Fetching reviews and details for restaurant ID: {restaurant_id}")
    
    # Fetch reviews based on the restaurant ID
    reviews = fetch_reviews_by_restaurant(restaurant_id)
    
    print("reviews fetched for restaurant_id ",reviews)
    if reviews:
        # Fetch restaurant details
        restaurant_details = get_restaurant_details(api_key, restaurant_id)
        
        if restaurant_details:
            # Extract relevant restaurant information
            restaurant_name = restaurant_details.get('name')
            #restaurant_address = restaurant_details.get('formatted_address')
            locality = extract_locality_from_adr_address(restaurant_details.get('adr_address'))
            maps_url = restaurant_details.get('url')
            
            # Combine restaurant information with each review
            enhanced_reviews = [
                {
                    "restaurant_name": restaurant_name,
                    "restaurant_address": locality,
                    "maps_url": maps_url,
                    "review_text": review.get('review_text'),
                    "rating": review.get('rating'),
                    "created_at": review.get('created_at'),
                    "user_id":review.get('user_id'),
                    "author_name":review.get('author_name')
                    #"locality": locality
                }
                for review in reviews
            ]
            return enhanced_reviews
        else:
            log.warning(f"Restaurant details not found for ID: {restaurant_id}")
            return []
    else:
        log.info(f"No reviews found for restaurant ID: {restaurant_id}")
        return []

def get_reviews_with_restaurant_details_for_user_id(user_id: str, api_key: str):
    log.info(f"Fetching reviews for user ID: {user_id}")
    
    # Fetch reviews based on the user ID
    reviews = fetch_reviews_by_user(user_id)
    print("reviews fetched from db",reviews)
    
    if reviews:
        # Get a unique list of restaurant IDs from the reviews
        restaurant_ids = {review['restaurant_id'] for review in reviews}
        enhanced_reviews = []

        for restaurant_id in restaurant_ids:
            # Fetch restaurant details
            restaurant_details = get_restaurant_details(api_key, restaurant_id)
            
            if restaurant_details:
                # Extract relevant restaurant information
                restaurant_name = restaurant_details.get('name')
                restaurant_address = extract_locality_from_adr_address(restaurant_details.get('adr_address'))
                maps_url = restaurant_details.get('url')
                
                # Combine restaurant information with each relevant review
                for review in reviews:
                    if review['restaurant_id'] == restaurant_id:
                        enhanced_reviews.append({
                            "restaurant_name": restaurant_name,
                            "restaurant_address": restaurant_address,
                            "maps_url": maps_url,
                            "review_text": review.get('review_text'),
                            "rating": review.get('rating'),
                            "created_at": review.get('created_at'),
                            "user_id": review.get('user_id'),
                            "author_name":review.get('author_name')
                        })
                        
        return enhanced_reviews
    else:
        log.info(f"No reviews found for user ID: {user_id}")
        return []


def extract_locality_from_adr_address(adr_address):
    if adr_address:
        soup = BeautifulSoup(adr_address, 'html.parser')
        print("soup ->",soup)
        locality = soup.find('span', {'class': 'locality'})
        return locality.text if locality else None
    return None

# Function to remove favorite from Elasticsearch
def remove_user_favorite(favorite_id):
    print("favorite_id",favorite_id)
    # index_name = "user_favorites"
    index_name = constants.USER_FAVORITES
    response = es.delete_by_query(
        index=index_name,
        body = {
            "query": {
                "term": {
                    "favorite_id.keyword": favorite_id  # Use .keyword for exact match
                }
            }
        }

    )
    print("response ",response)
    return response