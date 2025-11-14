from pydantic import BaseModel


class MessageHistory(BaseModel):
    id: int
    recipient: str
    sender: str
    message_text: str
    timestamp: str
    direction: str

    class Config:
        from_attributes = True

