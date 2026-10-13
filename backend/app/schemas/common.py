from pydantic import BaseModel


class PlaceholderResponse(BaseModel):
    message: str
