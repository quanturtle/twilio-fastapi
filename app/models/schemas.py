from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class MessageHistory(BaseModel):
    id: int
    recipient: str
    sender: str
    message_text: str
    timestamp: str
    direction: str
    user_id: Optional[int] = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    phone_number: str = Field(..., description="Phone number with country code (e.g., +595XXXXXXXXX)")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    address: Optional[str] = None


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    address: Optional[str] = None


class User(BaseModel):
    id: int
    phone_number: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    address: Optional[str] = None
    openai_conversation_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

