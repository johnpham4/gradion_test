from pydantic import BaseModel, EmailStr, ConfigDict
from typing import List
from datetime import datetime


class User(BaseModel):
    email: str
    name: str
    projects: List[str] = []  # List of project IDs


class UserCreate(BaseModel):
    email: EmailStr
    name: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    email: str
    name: str
    projects: List[str]