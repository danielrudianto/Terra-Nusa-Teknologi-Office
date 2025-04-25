from fastapi import APIRouter

from routes.client_routes import router as client_router
from routes.auth_routes import router as auth_router

# Create a router instance
router = APIRouter()

# Include client routes
router.include_router(client_router, prefix="/clients", tags=["Clients"])
router.include_router(auth_router, prefix="/auth", tags=["Auth"])