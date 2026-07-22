import utils.config

from fastapi import FastAPI, HTTPException
from utils.logger_utils import log_info, log_error
from contextlib import asynccontextmanager
from routes.routes import router
from fastapi.middleware.cors import CORSMiddleware
from utils.meilisearch import setup_meilisearch, sync_meilisearch
from utils.meilisearch_item import setup_master_item_meilisearch, sync_master_item_meilisearch
from utils.redis import sync_redis
from utils.database import database
from utils.redis import sync_redis
import sqlalchemy

log_info("Testing logger functionality")

log_info(f"Currently using {sqlalchemy.__version__}")

# Set the lifespan of the application
@asynccontextmanager
async def lifespan(app: FastAPI):
    log_info("Lifespan function started")  # Debug log
    # Startup logic
    try:
        await database.connect()
        log_info("Database connected successfully!")
    except Exception as e:
        log_error(f"Error connecting to database: {e}")
        
    try:
        await setup_meilisearch()
        log_info("Meilisearch setup completed successfully!")
    except Exception as e:
        log_error(f"Error connecting to meilisearch: {e}")

    try:
        await sync_meilisearch()
        await sync_master_item_meilisearch()
        log_info("Master item Meilisearch setup & sync completed successfully!")
    except Exception as e:
        log_error(f"Error setting up master item meilisearch: {e}")
        
    try:
        await sync_redis()
        log_info("Redis setup completed successfully!")
    except Exception as e:
        log_error(f"Error connecting to redis: {e}")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=7500, reload=True, workers=1)