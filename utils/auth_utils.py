from fastapi import HTTPException, Request
import os
from datetime import datetime
from pyseto import Paseto, Key

SECRET_KEY = os.getenv("SECRET_KEY")
KEY = Key.new(version=4, purpose="local", key=SECRET_KEY.encode())

def validate_token(request: Request):
    token = request.headers.get("Authorization")
    
    if not token:
        raise HTTPException(status_code=401, detail="Authorization token is missing.")
    
    try:
        # Validate the token
        payload = validate_token(token)
        return payload  # Return the user payload if valid
    except HTTPException as e:
        raise e  # Re-raise the exception if token validation fails