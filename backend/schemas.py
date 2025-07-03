from typing import Optional
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    first_name: Optional[str] = None   # now optional
    last_name: Optional[str] = None    # now optional
    phone_number: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):               #What data is needed to log in
    email: EmailStr
    password: str


class UserResponse(BaseModel):            #What data we send back to frontend after registration
    id: int
    first_name: str 
    last_name: str
    phone_number: str
    email: EmailStr
    message: str = "jondo created succesfully"
 

    class Config:
        from_attributes = True

class Token(BaseModel):                         #What we send after login
    access_token: str
    token_type: str

class StandardResponse(BaseModel):                    #registration response 
    isSuccess: bool
    data: Optional[UserResponse] = None
    errorCode: int
    errorMessage: str

class StandardTokenResponse(BaseModel):             #login response 
    isSuccess: bool
    data: Optional[Token] = None
    errorCode: int
    errorMessage: str
    