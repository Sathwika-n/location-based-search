import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from flask import jsonify, request
from pydantic import BaseModel
from service import maps_service
import server_properties
import logger
from datetime import timedelta


log = logger.get_logger()

api_key = server_properties.GOOGLE_API_KEY
log.info(f"api key loaded successfully")
maps_controller = APIRouter(prefix="/maps")

# Request body models
class LocationRequest(BaseModel):
    location: str
    radius: int = 5000
    keyword: str = "restaurant"

class CoordinatesRequest(BaseModel):
    latitude: float
    longitude: float

class ReviewRequest(BaseModel):
    user_id: str
    restaurant_id: str
    rating: float
    review_text: str

class FavoriteRequest(BaseModel):
    user_id: str
    restaurant_id: str

# Request body model for user review
class ReviewRequest(BaseModel):
    user_id: str
    restaurant_id: str
    rating: float
    review_text: str

# Request body model for querying user reviews
class ReviewQueryRequest(BaseModel):
    restaurant_id: str

@maps_controller.post("/nearby_restaurants")
async def nearby_restaurants(request: Request, data: LocationRequest):
    log.info(f"Finding restaurants near {data.location}...")
    if not data.location:
        raise HTTPException(status_code=400, detail="Location is required.")
    
    # Fetch new nearby restaurants from Google API
    restaurants = maps_service.find_nearby_restaurants(api_key, data.location, data.radius, data.keyword)
    
    if restaurants:
        return restaurants
    else:
        return {"message": "No restaurants found."}

@maps_controller.get("/restaurant_details/{restaurant_id}")
async def restaurant_details(restaurant_id: str):
    log.info(f"Fetching details for restaurant ID: {restaurant_id}...")
    
    # Fetch restaurant details from the service
    details = maps_service.get_restaurant_details(api_key, restaurant_id)
    
    return {'details': details}
@maps_controller.get("/restaurant_reviews/{restaurant_id}")
async def restaurant_reviews(restaurant_id: str):
    log.info(f"Fetching reviews for restaurant ID: {restaurant_id}...")
    
    # Fetch restaurant details from the service
    details = maps_service.fetch_restaurant_reviews(api_key, restaurant_id)
    
    return {'details': details}

@maps_controller.post("/add_favorite")
async def add_favorite(data: FavoriteRequest):
    log.info(f"Adding restaurant {data.restaurant_id} to favorites for user {data.user_id}...")
    
    # Create favorite data
    favorite_data = {
        "favorite_id": f"{data.user_id}_{data.restaurant_id}",
        "user_id": data.user_id,
        "restaurant_id": data.restaurant_id,
        "added_at": datetime.datetime.utcnow().isoformat()
    }
    
    # Store favorite in Elasticsearch
    response = maps_service.store_user_favorite(favorite_data)
    
    return {"message": "Favorite added successfully", "response": response}

@maps_controller.get("/user_favorites/{user_id}")
async def user_favorites(user_id: str):
    log.info(f"Fetching favorites for user ID: {user_id}...")
    favorites = maps_service.fetch_user_favorites(user_id)
    return {'favorites': favorites}

@maps_controller.post("/add_review")
async def add_review(data: ReviewRequest):
    log.info(f"Adding review for restaurant {data.restaurant_id} by user {data.user_id}...")
    
    # Validate rating
    if data.rating < 1 or data.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5.")
    
    # Validate review text (optional field, but can be useful)
    if not data.review_text:
        raise HTTPException(status_code=400, detail="Review text is required.")
    
    # Create review data structure
    review_data = {
        "review_id": f"{data.user_id}_{data.restaurant_id}",
        "user_id": data.user_id,
        "restaurant_id": data.restaurant_id,
        "rating": data.rating,
        "review_text": data.review_text,
        "created_at": datetime.datetime.utcnow().isoformat(),
    }
    
    # Store review in Elasticsearch
    try:
        response = maps_service.store_user_review(review_data)
        return {"message": "Review added successfully", "response": response}
    except Exception as e:
        log.error(f"Error storing review: {str(e)}")
        raise HTTPException(status_code=500, detail="Error storing review in database.")
    
@maps_controller.get("/user_reviews")
async def get_user_reviews(query: ReviewQueryRequest):
    log.info("Fetching user reviews...")

    # Validate input: at least one of user_id or restaurant_id should be provided
    if not query.restaurant_id:
        raise HTTPException(status_code=400, detail="Either user_id or restaurant_id is required.")

    # Fetch user reviews based on user_id or restaurant_id
    try:
        if query.restaurant_id:
            reviews = maps_service.fetch_reviews_given_by_users(query.restaurant_id)

        if reviews:
            return {"reviews": reviews}
        else:
            return {"message": "No reviews found."}
    except Exception as e:
        log.error(f"Error fetching reviews: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching reviews from database.")
    
@maps_controller.post("/reverse_geocode")
async def reverse_geocode(request: Request):
    log.info("Performing reverse geocoding...")

    try:
        data = await request.json()
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        if not latitude or not longitude:
            raise HTTPException(status_code=400, detail="Latitude and longitude are required.")

        # Perform reverse geocoding with your maps service
        location = maps_service.reverse_geocode(latitude, longitude,api_key)
        
        # Return JSON response
        return JSONResponse(content={"location": location})
    except Exception as e:
        log.error(f"Error in reverse geocoding: {e}")
        raise HTTPException(status_code=500, detail="Failed to find location for the specified coordinates.")