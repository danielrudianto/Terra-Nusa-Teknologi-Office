from sqlalchemy import insert, select, update, delete, func
from utils.database import database
from typing import Dict, List, Optional
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from datetime import datetime
from utils.redis import r
import json
from models.asset_model import Asset

class AssetController:
    @staticmethod 
    async def create_asset(asset_data: dict, userID: int) -> Dict:
        """
        Create a new asset in the database.
        
        Args:
            asset_data (Dict): The data of the asset to create.
        
        Returns:
            Dict: A success message with the created asset ID.
        """
        log_info(f"Creating asset with data: {asset_data}")
        try:
            # Create new Bank model

            asset_data["createdAt"] = datetime.now()
            asset_data["createdBy"] = userID

            asset = Asset(**asset_data)
            result = await asset.create()
            if "error" in result:
                log_error(f"Error creating asset: {result['error']}")
                raise HTTPException(status_code=result.get("status", 500), detail=result["error"])

            log_info(f"Asset created successfully with ID: {result}")
            return {"message": "Asset created successfully", "asset_id": result}
        except IntegrityError as e:
            log_error(f"Integrity error: {str(e)}")
            raise HTTPException(status_code=400, detail="Asset already exists.")
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")