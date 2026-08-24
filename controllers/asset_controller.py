from typing import Dict
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from utils.redis import r
import json
from schemas.asset_schema import AssetCreate, AssetUpdate
from repository.asset_repository import AssetRepository

class AssetController:
    @staticmethod 
    async def create_asset(asset_data: dict, user_id: int) -> Dict:
        """
        Create a new asset in the database.
        """
        log_info(f"Creating asset with data: {asset_data}")
        try:
            # Add user ID to asset data
            asset_data["createdBy"] = user_id
            print(asset_data)
            
            # Use repository to create asset
            result = await AssetRepository.create(asset_data)
            
            if "error" in result:
                log_error(f"Error creating asset: {result['error']}")
                raise HTTPException(
                    status_code=result.get("status", 500), 
                    detail=result["error"]
                )

            log_info(f"Asset created successfully with ID: {result['asset_id']}")
            return {
                "message": "Asset created successfully", 
                "asset_id": result["asset_id"]
            }
            
        except HTTPException:
            raise
        except IntegrityError as e:
            log_error(f"Integrity error: {str(e)}")
            raise HTTPException(
                status_code=400, 
                detail="Asset creation failed due to data constraints."
            )
        except ValueError as e:
            log_error(f"Validation error: {str(e)}")
            raise HTTPException(
                status_code=422, 
                detail=f"Invalid asset data: {str(e)}"
            )
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail="Internal server error."
            )

    @staticmethod
    async def get_assets(page: int, page_size: int, keyword: str = "", sortBy: str = "", sortByDirection: str = "asc") -> Dict:
        """
        Get paginated list of assets.
        """
        try:
            log_info(f"Fetching assets - page={page}, page_size={page_size}, keyword={keyword}, sortBy={sortBy}, sortByDirection={sortByDirection}")
            
            # Validate pagination parameters
            if page < 0:
                raise HTTPException(status_code=400, detail="Page must be greater than 0")
            if page_size < 10 or page_size > 100:
                raise HTTPException(status_code=400, detail="Page size must be between 1 and 100")

            # Get assets from repository
            result = await AssetRepository.get_assets(
                page=page, 
                page_size=page_size, 
                keyword=keyword,
                sort_by=sortBy,
                sort_by_direction=sortByDirection
            )
            
            if "error" in result:
                log_error(f"Error fetching assets: {result['error']}")
                raise HTTPException(
                    status_code=result.get("status", 500), 
                    detail=result["error"]
                )

            # Prepare response data
            response_data = {
                "data": [asset.model_dump() for asset in result["data"]],
                "count": result["count"],
                "total_count": result["total_count"],
                "page": result["page"],
                "page_size": result["page_size"],
                "total_pages": result["total_pages"]
            }

            log_info(f"Successfully fetched {len(result['data'])} assets")
            return response_data
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Unexpected error while fetching assets: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail="Internal server error while fetching assets."
            )

    @staticmethod
    async def get_asset_by_id(asset_id: int) -> Dict:
        """
        Get a single asset by ID.
        """
        try:
            log_info(f"Fetching asset with ID: {asset_id}")
            
            # Validate asset ID
            if asset_id < 1:
                raise HTTPException(status_code=400, detail="Asset ID must be greater than 0")

            # Try cache first
            cache_key = f"asset:{asset_id}"
            cached_data = r.get(cache_key)
            
            if cached_data:
                log_info(f"Returning cached asset data for ID: {asset_id}")
                return json.loads(cached_data)

            # Get asset from repository
            asset = await AssetRepository.get_by_id(asset_id)
            
            if not asset:
                log_error(f"Asset not found with ID: {asset_id}")
                raise HTTPException(
                    status_code=404, 
                    detail=f"Asset with ID {asset_id} not found"
                )

            # Cache the result for 10 minutes
            asset_data = asset.model_dump()
            r.setex(cache_key, 600, json.dumps(asset_data, default=str))

            log_info(f"Successfully fetched asset with ID: {asset_id}")
            return asset_data
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Unexpected error while fetching asset {asset_id}: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail="Internal server error while fetching asset."
            )

    @staticmethod
    async def update_asset(asset_id: int, update_data: dict, user_id: int) -> Dict:
        """
        Update an existing asset.
        """
        try:
            log_info(f"Updating asset {asset_id} with data: {update_data}")
            
            # Validate asset ID
            if asset_id < 1:
                raise HTTPException(status_code=400, detail="Asset ID must be greater than 0")

            # Add updatedBy user ID
            update_data["updatedBy"] = user_id
            
            # Validate update data
            asset_update = AssetUpdate(**update_data)
            
            # Check if asset exists
            existing_asset = await AssetRepository.get_by_id(asset_id)
            if not existing_asset:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Asset with ID {asset_id} not found"
                )

            # Update asset
            result = await AssetRepository.update(asset_id, asset_update)
            
            if "error" in result:
                log_error(f"Error updating asset {asset_id}: {result['error']}")
                raise HTTPException(
                    status_code=result.get("status", 500), 
                    detail=result["error"]
                )

            # Clear relevant cache entries
            await AssetController._clear_asset_cache(asset_id)
            
            log_info(f"Successfully updated asset with ID: {asset_id}")
            return {"message": "Asset updated successfully"}
            
        except HTTPException:
            raise
        except ValueError as e:
            log_error(f"Validation error updating asset {asset_id}: {str(e)}")
            raise HTTPException(
                status_code=422, 
                detail=f"Invalid update data: {str(e)}"
            )
        except Exception as e:
            log_error(f"Unexpected error updating asset {asset_id}: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail="Internal server error while updating asset."
            )

    @staticmethod
    async def delete_asset(asset_id: int) -> Dict:
        """
        Delete an asset.
        """
        try:
            log_info(f"Deleting asset with ID: {asset_id}")
            
            # Validate asset ID
            if asset_id < 1:
                raise HTTPException(status_code=400, detail="Asset ID must be greater than 0")

            # Check if asset exists
            existing_asset = await AssetRepository.get_by_id(asset_id)
            if not existing_asset:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Asset with ID {asset_id} not found"
                )

            # Delete asset
            result = await AssetRepository.delete(asset_id)
            
            if "error" in result:
                log_error(f"Error deleting asset {asset_id}: {result['error']}")
                raise HTTPException(
                    status_code=result.get("status", 500), 
                    detail=result["error"]
                )

            # Clear relevant cache entries
            await AssetController._clear_asset_cache(asset_id)
            
            log_info(f"Successfully deleted asset with ID: {asset_id}")
            return {"message": "Asset deleted successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Unexpected error deleting asset {asset_id}: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail="Internal server error while deleting asset."
            )

    @staticmethod
    async def search_assets(keyword: str) -> Dict:
        """
        Search assets by keyword.
        """
        try:
            log_info(f"Searching assets with keyword: {keyword}")
            
            assets = await AssetRepository.search_by_keyword(keyword)
            
            return {
                "data": [asset.model_dump() for asset in assets],
                "count": len(assets)
            }
            
        except Exception as e:
            log_error(f"Error searching assets: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail="Internal server error while searching assets."
            )

    @staticmethod
    async def _clear_asset_cache(asset_id: int):
        """
        Clear cache entries related to an asset.
        """
        try:
            # Clear specific asset cache
            r.delete(f"asset:{asset_id}")
            
            # Clear paginated assets cache
            keys = r.keys("assets:page:*")
            if keys:
                r.delete(*keys)
                
        except Exception as e:
            log_error(f"Error clearing cache for asset {asset_id}: {str(e)}")
            # Don't raise exception for cache clearing failures