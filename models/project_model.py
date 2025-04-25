from pydantic import BaseModel, EmailStr, StringConstraints
from typing import Annotated
from sqlalchemy import Table, Column, Integer, String, Boolean
from utils.database import metadata

