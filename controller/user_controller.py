from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from service.user_service import UserService

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
