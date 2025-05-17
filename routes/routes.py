from fastapi import APIRouter

from routes.client_routes import router as client_router
from routes.auth_routes import router as auth_router
from routes.supplier_routes import router as supplier_router
from routes.purchase_routes import router as purchase_router

# Create a router instance
router = APIRouter()

# Include client routes
router.include_router(client_router, prefix="/clients", tags=["Clients"])
router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(supplier_router, prefix="/suppliers", tags=["Suppliers"])
router.include_router(purchase_router, prefix="/purchases", tags=["Purchases"])