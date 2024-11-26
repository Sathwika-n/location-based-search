from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from service.user_service import UserService
import server_properties

# Create router
user_controller = APIRouter()

# Pydantic models for input validation
class SignupModel(BaseModel):
    username: str
    password: str
    email: str

class LoginModel(BaseModel):
    email: str
    password: str

class UpdateModel(BaseModel):

    username: Optional[str] = None
    password: Optional[str] = None

class UpdatePasswordModel(BaseModel):
    email : str
    old_password: str
    new_password: str

class ForgotPasswordModel(BaseModel):
    email: str

class SubmitFeedback(BaseModel):
    user_id: str
    feedback: str

class GoogleLoginModel(BaseModel):
    email: str
    sub: str  # Google's unique identifier for the user
    username: str



# Dependency to use the service
user_service = UserService()

@user_controller.post("/signup")
async def signup(user: SignupModel):
    result = user_service.signup(user.username, user.password, user.email)
    if result.get("success"):
        return {"message": "Signup successful", "user-id": result.get("user_id")}
    else:
        raise HTTPException(status_code=400, detail=result.get("error"))

@user_controller.post("/login")
async def login(user: LoginModel):
    result = user_service.login(user.email, user.password)
    if result.get("success"):
        return {"message": "Login successful", "result": result.get('result')}
    else:
        raise HTTPException(status_code=401, detail=result.get("error"))

@user_controller.put("/update")
async def update(user: UpdateModel, user_id: str):
    result = user_service.update_user(user_id, user.username, user.password)
    if result.get("success"):
        return {"message": "User updated successfully"}
    else:
        raise HTTPException(status_code=400, detail=result.get("error"))
    
@user_controller.put("/change-password")
async def update_password(request: UpdatePasswordModel):
    result = user_service.update_password(request.email, request.old_password, request.new_password)
    if result.get("success"):
        return {"message": "Password updated successfully. A confirmation email has been sent."}
    else:
        raise HTTPException(status_code=400, detail=result.get("error"))

@user_controller.post("/forgot-password")
async def forgot_password(request: ForgotPasswordModel):
    result = user_service.forgot_password(request.email)
    if result.get("success"):
        return {"message": result.get("message")}
    else:
        raise HTTPException(status_code=404, detail=result.get("error"))
    
@user_controller.post("/submit-feedback")
async def submit_feedback(request: SubmitFeedback):
    result = user_service.submit_feedback(request.user_id,request.feedback)
    if result.get("success"):
        return {"message": result.get("message")}
    else:
        raise HTTPException(status_code=404, detail=result.get("error"))

@user_controller.post("/google-auth")
async def google_auth(request: GoogleLoginModel):
    """
    Handle Google Login or Signup.
    """
    result = user_service.google_auth(request.email, request.sub, request.username)
    
    if result.get("success"):
        return {
            "message": result.get("message"),
            "result": result.get("result")
        }
    else:
        raise HTTPException(status_code=400, detail=result.get("error"))

@user_controller.get("/get-config")
async def get_config():
    return {
        "google_client_id": server_properties.VITE_GOOGLE_CLIENT_ID,
        "google_api_key": server_properties.GOOGLE_API_KEY
    }

    

