import utils.config

from fastapi import FastAPI, HTTPException
from utils.logger_utils import log_info, log_error
from contextlib import asynccontextmanager
from routes.routes import router
from fastapi.middleware.cors import CORSMiddleware
from utils.meilisearch import setup_meilisearch
from utils.database import database

import asyncio

log_info("Testing logger functionality")

# Set the lifespan of the application
@asynccontextmanager
async def lifespan(app: FastAPI):
    log_info("Lifespan function started")  # Debug log
    # Startup logic
    try:
        await database.connect()
        log_info("Database connected successfully!")

        setup_meilisearch()
        log_info("Meilisearch setup completed successfully!")
    except Exception as e:
        log_error(f"Error connecting to database: {e}")
    yield  # This is where the application runs
    # Shutdown logic
    await database.disconnect()
    log_info("Database disconnected successfully!")


# Create an instance of the FastAPI application
app = FastAPI(lifespan=lifespan, redirect_slashes=True)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with specific origins for production
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Include the router
app.include_router(router)

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, workers=1)