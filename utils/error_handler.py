from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from utils.logger_utils import log_error

def handle_error(request: Request, exc: HTTPException):
    """
    Utility function to handle errors and raise HTTPException with a consistent response format.
    """
    log_error(f"Error occurred: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": exc.status_code, "message": exc.detail},
    )