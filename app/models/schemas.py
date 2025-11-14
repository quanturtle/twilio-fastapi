from pydantic import BaseModel


class ChatInput(BaseModel):
    recipient: str
    message: str


class ChatResponse(BaseModel):
    recipient: str
    sender: str
    message: str


class MessageHistory(BaseModel):
    id: int
    recipient: str
    sender: str
    message_text: str
    timestamp: str
    direction: str

    class Config:
        from_attributes = True

