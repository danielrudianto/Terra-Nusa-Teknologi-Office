from fastapi import HTTPException, Request
import os
from pyseto import Paseto, Key
from utils.logger_utils import log_error, log_info
import json

SECRET_KEY = os.getenv("SECRET_KEY")
KEY = Key.new(version=4, purpose="local", key=SECRET_KEY)

def validate_token(request: Request):
    log_info("Validating token started")
    token = request.headers["Authorization"].split(" ")[1]

    if not token:
        log_info("Authorization token is missing")
        raise HTTPException(status_code=401, detail="Authorization token is missing.")
    
    try:
        # Validate the token
        decoded = Paseto().decode(KEY, token, deserializer=json)
        payload = decoded.payload
        log_info(f"Token payload: {payload}")
        # Convert the payload to a dictionary
        return payload
    except HTTPException as e:
        log_error(f"Token validation error: {str(e)}")
        return {"error": "Token validation error.", "status": 401}
    except Exception as e:
        log_error(f"Token validation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error.")
    