from fastapi import FastAPI
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from controller.maps_controller import maps_controller  # Make sure this import is compatible with FastAPI
from controller.user_controller import user_controller

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can specify allowed origins here
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the maps controller router
app.include_router(maps_controller)
app.include_router(user_controller)

if __name__ == '__main__':
   
    uvicorn.run(app, host='0.0.0.0', port=8080)
