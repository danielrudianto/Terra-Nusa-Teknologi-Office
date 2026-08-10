from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, or_
from utils.database import database
from sqlalchemy.exc import IntegrityError
from datetime import datetime as dt
from utils.logger_utils import log_error
from schemas.asset_schema import AssetCreate, AssetUpdate, AssetResponse

# Import the table directly to avoid circular imports
from models.asset_model import asset_table

class AssetRepository:
    @staticmethod
    async def create(asset_data: AssetCreate) -> Dict[str, Any]:
        """
        Create a new asset in the database.
        """
        try:
            query = asset_table.insert().values(
                **asset_data,
                createdAt=dt.now()
            )
            result = await database.execute(query)
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="assets",
                entityID=result,
                action="create",
            )
            return {"message": "Asset created successfully", "asset_id": result}
        except IntegrityError as e:
            log_error(f"Integrity error while creating asset: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while creating asset: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_assets(
        page: int = 1, 
        page_size: int = 10, 
        keyword: str = "",
        sort_by: str = "",
        sort_by_direction: str = "asc"
    ) -> Dict[str, Any]:
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
            query = query.limit(page_size).offset(page * page_size)

            # Add sorting if provided
            if sort_by and sort_by_direction:
                query = query.order_by(getattr(asset_table.c, sort_by).asc() if sort_by_direction == "asc" else getattr(asset_table.c, sort_by).desc())
            
            # Execute query
            result = await database.fetch_all(query)
            
            # Convert to Pydantic models
            assets = [AssetResponse.model_validate(dict(row)) for row in result]
            
            # Get total count
            count_query = select(func.count()).select_from(asset_table)
            if keyword:
                keyword_filter = f"%{keyword}%"
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
                "count": len(assets),
                "total_count": count or 0,
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
    async def update(asset_id: int, update_data: AssetUpdate) -> Dict[str, Any]:
        """
        Update an existing asset.
        """
        try:
            # Keadaan sebelum & sesudah dibandingkan agar nilai lama ikut
            # terekam; tanpa ini audit hanya tahu "diubah", bukan "dari apa".
            _sebelum = await database.fetch_one(
                select(asset_table).where(asset_table.c.id == asset_id)
            )
            update_values = update_data.model_dump(exclude_none=True)
            if update_values:  # Only update if there are changes
                update_values['updatedAt'] = dt.now()
                query = asset_table.update().where(asset_table.c.id == asset_id).values(update_values)
                result = await database.execute(query)
                if result == 0:
                    return {"error": "Asset not found", "status": 404}
            
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="assets",
                entityID=asset_id,
                action="update",
                changes=AuditLogRepository.diff(
                    dict(_sebelum) if _sebelum else {},
                    dict(
                        await database.fetch_one(
                            select(asset_table).where(
                                asset_table.c.id == asset_id
                            )
                        )
                        or {}
                    ),
                ),
            )

            return {"message": "Asset updated successfully"}
        except IntegrityError as e:
            log_error(f"Integrity error while updating asset: {str(e)}")
            return {"error": "Asset update failed due to data constraints", "status": 400}
        except Exception as e:
            log_error(f"Error updating asset {asset_id}: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def delete(asset_id: int) -> Dict[str, Any]:
        """
        Delete an asset.
        """
        try:
            query = asset_table.delete().where(asset_table.c.id == asset_id)
            result = await database.execute(query)
            if result == 0:
                return {"error": "Asset not found", "status": 404}
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="assets",
                entityID=asset_id,
                action="delete",
            )
            
            return {"message": "Asset deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting asset {asset_id}: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def search_by_keyword(keyword: str) -> List[AssetResponse]:
        """
        Search assets by keyword across multiple fields.
        """
        try:
            if not keyword:
                query = asset_table.select()
            else:
                keyword_filter = f"%{keyword}%"
                query = asset_table.select().where(
                    asset_table.c.name.ilike(keyword_filter) |
                    asset_table.c.description.ilike(keyword_filter) |
                    asset_table.c.brand.ilike(keyword_filter) |
                    asset_table.c.type.ilike(keyword_filter) |
                    asset_table.c.location.ilike(keyword_filter) |
                    asset_table.c.purchaseOrderName.ilike(keyword_filter)
                )
            
            result = await database.fetch_all(query)
            return [AssetResponse.model_validate(dict(row)) for row in result]
        except Exception as e:
            log_error(f"Error searching assets: {str(e)}")
            raise

    @staticmethod
    async def exists(asset_id: int) -> bool:
        """
        Check if an asset exists.
        """
        try:
            query = select(asset_table.c.id).where(asset_table.c.id == asset_id)
            result = await database.fetch_val(query)
            return result is not None
        except Exception as e:
            log_error(f"Error checking asset existence: {str(e)}")
            return False

    @staticmethod
    async def get_monthly_asset(month: int, year: int):
        """
        Get list of assets that are aquired before the end of the month and year
        """
        try:
            if month == 12:
                end_date = dt(year + 1, 1, 1)
            else:
                end_date = dt(year, month + 1, 1)
            
            query = select(asset_table).where(asset_table.c.purchaseDate <= end_date).order_by(asset_table.c.purchaseDate.asc())

            results = await database.fetch_all(query)

            if not results:
                return []

            # Convert ke Pydantic model
            assets = [dict(row) for row in results]
            return assets

        except Exception as e:
            log_error(f"Error fetching monthly assets for {month}/{year}: {str(e)}")
            return []