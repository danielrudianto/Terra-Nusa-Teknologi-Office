from pydantic import BaseModel
from typing import Optional


class UserAvatarUpdate(BaseModel):
    faceID: Optional[str] = None
    hairID: Optional[str] = None
    eyesID: Optional[str] = None
    mouthID: Optional[str] = None
    topID: Optional[str] = None
    accessoryID: Optional[str] = None
    skinTone: Optional[str] = None
    hairColor: Optional[str] = None
    topColor: Optional[str] = None
    backgroundColor: Optional[str] = None