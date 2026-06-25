"""Common API schemas."""

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str
