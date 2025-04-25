from fastapi import HTTPException
from utils.error_handler import handle_error
import os
from datetime import datetime
from pyseto import Paseto, Key



SECRET_KEY = os.getenv("SECRET_KEY")
KEY = Key.new(version=4, purpose="local", key=SECRET_KEY.encode())

def validate_token(token: str):
    try:
        # Decrypt and validate the token
        payload = Paseto.new(version=4, purpose="local").decrypt(KEY, token)
        
        # Check expiration
        exp = datetime.fromisoformat(payload["exp"])
        if datetime.utcnow() > exp:
            raise HTTPException(status_code=401, detail="Token has expired")
        
        return payload  # Return the payload for use in the route
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")