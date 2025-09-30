from models.asset_model import AssetCreate, asset_table, AssetResponse, AssetUpdate
from utils.database import database
from datetime import datetime as dt
from sqlalchemy.exc import IntegrityError
from utils.logger_utils import log_error
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, select, func
from typing import Optional, Annotated

# Database Operations Class
class AssetRepository:
    @staticmethod
    async def create(asset_data: AssetCreate) -> dict:
        """
        Create a new asset in the database.
        """
        try:
            query = asset_table.insert().values(
                **asset_data.model_dump(exclude_none=True),
                createdAt=dt.now()
            )
            result = await database.execute(query)
            return {"message": "Asset created successfully", "asset_id": result}
        except IntegrityError as e:
            log_error(f"Integrity error while creating asset: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while creating asset: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_assets(page: int, page_size: int, keyword: str = "") -> dict:
        """
        Get paginated assets with optional keyword filtering.
        """
        try:
            # Build base query
            query = asset_table.select()
            
            # Add keyword filtering if provided
            if keyword:
                keyword_filter = f"%{keyword}%"
                query = query.where(
                    asset_table.c.name.ilike(keyword_filter) |
                    asset_table.c.description.ilike(keyword_filter) |
                    asset_table.c.brand.ilike(keyword_filter) |
                    asset_table.c.type.ilike(keyword_filter) |
                    asset_table.c.location.ilike(keyword_filter) |
                    asset_table.c.purchaseOrderName.ilike(keyword_filter)
                )
            
            # Add pagination
            query = query.limit(page_size).offset((page - 1) * page_size)
            
            # Execute query
            result = await database.fetch_all(query)
            
            # Convert to Pydantic models
            assets = [AssetResponse.model_validate(dict(row)) for row in result]
            
            # Get total count
            count_query = select(func.count()).select_from(asset_table)
            if keyword:
                count_query = count_query.where(
                    asset_table.c.name.ilike(keyword_filter) |
                    asset_table.c.description.ilike(keyword_filter) |
                    asset_table.c.brand.ilike(keyword_filter) |
                    asset_table.c.type.ilike(keyword_filter) |
                    asset_table.c.location.ilike(keyword_filter) |
                    asset_table.c.purchaseOrderName.ilike(keyword_filter)
                )
            
            count = await database.fetch_val(count_query)
            
            return {
                "data": assets,
                "count": count if count is not None else 0,
                "page": page,
                "page_size": page_size,
                "total_pages": (count + page_size - 1) // page_size if count else 0
            }
            
        except Exception as e:
            log_error(f"Unexpected error while fetching assets: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_by_id(asset_id: int) -> Optional[AssetResponse]:
        """
        Get a single asset by ID.
        """
        try:
            query = asset_table.select().where(asset_table.c.id == asset_id)
            result = await database.fetch_one(query)
            return AssetResponse.model_validate(dict(result)) if result else None
        except Exception as e:
            log_error(f"Error fetching asset {asset_id}: {str(e)}")
            return None

    @staticmethod
    async def update(asset_id: int, update_data: AssetUpdate) -> dict:
        """
        Update an existing asset.
        """
        try:
            update_values = update_data.model_dump(exclude_none=True)
            if update_values:  # Only update if there are changes
                update_values['updatedAt'] = dt.now()
                query = asset_table.update().where(asset_table.c.id == asset_id).values(update_values)
                await database.execute(query)
            
            return {"message": "Asset updated successfully"}
        except Exception as e:
            log_error(f"Error updating asset {asset_id}: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def delete(asset_id: int) -> dict:
        """
        Delete an asset.
        """
        try:
            query = asset_table.delete().where(asset_table.c.id == asset_id)
            await database.execute(query)
            return {"message": "Asset deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting asset {asset_id}: {str(e)}")
            return {"error": "Internal server error.", "status": 500}