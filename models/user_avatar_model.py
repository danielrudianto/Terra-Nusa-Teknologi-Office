from sqlalchemy import Table, Column, Integer, String, DateTime
from utils.database import metadata
from datetime import datetime as dt

# Component-based avatar: instead of storing an uploaded image we store the
# ids of the parts the user picked. The frontend renders these as SVG, so the
# payload stays tiny and can be cached in Redis cheaply.
user_avatars_table = Table(
    "user_avatars",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("userID", Integer(), nullable=False, unique=True, index=True),
    # part ids -> resolved to SVG shapes on the client
    Column("faceID", String(30), nullable=False, default="face-01"),
    Column("hairID", String(30), nullable=False, default="hair-01"),
    Column("eyesID", String(30), nullable=False, default="eyes-01"),
    Column("mouthID", String(30), nullable=False, default="mouth-01"),
    Column("topID", String(30), nullable=False, default="top-01"),
    Column("accessoryID", String(30), nullable=True, default=None),
    # colours are stored as palette keys, not raw hex, so a palette change
    # updates every avatar at once
    Column("skinTone", String(20), nullable=False, default="tone-03"),
    Column("hairColor", String(20), nullable=False, default="hair-brown"),
    Column("topColor", String(20), nullable=False, default="top-blue"),
    Column("backgroundColor", String(20), nullable=False, default="bg-blue"),
    Column("createdAt", DateTime(), default=dt.now, nullable=False),
    Column("updatedAt", DateTime(), default=None, onupdate=dt.now, nullable=True),
)