from utils.config import load_dotenv
from fastapi import FastAPI, HTTPException
from utils.database import database
from utils.logger_utils import log_info
from contextlib import asynccontextmanager
from routes.routes import router
from fastapi.middleware.cors import CORSMiddleware
from utils.error_handler import handle_error

log_info("Testing logger functionality")

# Set the lifespan of the application
@asynccontextmanager
async def lifespan(app: FastAPI):
    log_info("Lifespan function started")  # Debug log
    # Startup logic
    await database.connect()
    log_info("Database connected successfully!")
    yield  # This is where the application runs
    # Shutdown logic
    await database.disconnect()
    log_info("Database disconnected successfully!")


# Create an instance of the FastAPI application
app = FastAPI(lifespan=lifespan, redirect_slashes=False)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with specific origins for production
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

app.add_exception_handler(HTTPException, handle_error)

# Include the router
app.include_router(router)

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)