from typing import List, Optional, Dict, Any
from sqlalchemy import insert, select, update, delete, func
from utils.database import database
from utils.logger_utils import log_error
from sqlalchemy.exc import IntegrityError
from datetime import datetime as dt
from models.supplier_model import suppliers_table
from schemas.supplier_schema import SupplierCreate, SupplierUpdate, SupplierResponse

class SupplierRepository:
    @staticmethod
    async def create(supplier_data: SupplierCreate) -> Dict[str, Any]:
        """
        Create a new supplier in the database.
        """
        try:
            query = insert(suppliers_table).values(
                **supplier_data.model_dump(exclude_none=True),
                createdAt=dt.now().isoformat(),
                isDelete=False
            )
            supplier_id = await database.execute(query)
            return {"message": "Supplier created successfully", "supplier_id": supplier_id}
        except IntegrityError as e:
            log_error(f"Integrity error while creating supplier: {str(e)}")
            return {"error": "Something wrong with your input.", "status": 400}
        except Exception as e:
            log_error(f"Error creating supplier: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update(supplier_id: int, supplier_data: SupplierUpdate) -> Dict[str, Any]:
        """
        Update an existing supplier.
        """
        try:
            update_values = supplier_data.model_dump(exclude_none=True)
            update_values['updatedAt'] = dt.now().isoformat()
            
            query = (
                update(suppliers_table)
                .where(suppliers_table.c.id == supplier_id)
                .values(update_values)
            )
            
            await database.execute(query)
            return {"message": "Supplier updated successfully", "supplier_id": supplier_id}
        except IntegrityError as e:
            log_error(f"Integrity error while updating supplier: {str(e)}")
            return {"error": "Something wrong with your input.", "status": 400}
        except Exception as e:
            log_error(f"Error updating supplier: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_id(supplier_id: int) -> Optional[SupplierResponse]:
        """
        Get a supplier by ID from the database.
        """
        try:
            query = select(suppliers_table).where(
                suppliers_table.c.id == supplier_id,
                suppliers_table.c.isDelete == False
            )
            result = await database.fetch_one(query)
            return SupplierResponse.model_validate(dict(result)) if result else None
        except Exception as e:
            log_error(f"Error fetching supplier by ID: {str(e)}")
            raise

    @staticmethod
    async def get_all(
        skip: int = 0, 
        limit: int = 100,
        keyword: str = None
    ) -> List[SupplierResponse]:
        """
        Get all suppliers with optional pagination and keyword search.
        """
        try:
            query = select(suppliers_table).where(
                suppliers_table.c.isDelete == False
            )
            
            if keyword:
                keyword_filter = f"%{keyword}%"
                query = query.where(
                    suppliers_table.c.name.ilike(keyword_filter) |
                    suppliers_table.c.address.ilike(keyword_filter) |
                    suppliers_table.c.city.ilike(keyword_filter) |
                    suppliers_table.c.province.ilike(keyword_filter) |
                    suppliers_table.c.phoneNumber.ilike(keyword_filter) |
                    suppliers_table.c.email.ilike(keyword_filter) |
                    suppliers_table.c.itemsSold.ilike(keyword_filter) |
                    suppliers_table.c.serviceArea.ilike(keyword_filter)
                )
            
            query = query.offset(skip).limit(limit)
            result = await database.fetch_all(query)
            return [SupplierResponse.model_validate(dict(row)) for row in result]
        except Exception as e:
            log_error(f"Error fetching suppliers: {str(e)}")
            raise

    @staticmethod
    async def get_paginated(
        page: int = 1,
        page_size: int = 10,
        keyword: str = None
    ) -> Dict[str, Any]:
        """
        Get paginated suppliers with total count.
        """
        try:
            # Base query for data
            data_query = select(suppliers_table).where(
                suppliers_table.c.isDelete == False
            )
            
            # Base query for count
            count_query = select(func.count()).select_from(suppliers_table).where(
                suppliers_table.c.isDelete == False
            )
            
            if keyword:
                keyword_filter = f"%{keyword}%"
                where_condition = (
                    suppliers_table.c.name.ilike(keyword_filter) |
                    suppliers_table.c.address.ilike(keyword_filter) |
                    suppliers_table.c.city.ilike(keyword_filter) |
                    suppliers_table.c.province.ilike(keyword_filter) |
                    suppliers_table.c.phoneNumber.ilike(keyword_filter) |
                    suppliers_table.c.email.ilike(keyword_filter) |
                    suppliers_table.c.itemsSold.ilike(keyword_filter) |
                    suppliers_table.c.serviceArea.ilike(keyword_filter)
                )
                data_query = data_query.where(where_condition)
                count_query = count_query.where(where_condition)
            
            # Apply pagination to data query
            offset = (page - 1) * page_size
            data_query = data_query.offset(offset).limit(page_size)
            
            # Execute queries
            suppliers_data = await database.fetch_all(data_query)
            total_count = await database.fetch_val(count_query)
            
            suppliers = [SupplierResponse.model_validate(dict(row)) for row in suppliers_data]
            
            return {
                "data": suppliers,
                "count": len(suppliers),
                "total_count": total_count or 0,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_count + page_size - 1) // page_size if total_count else 0
            }
        except Exception as e:
            log_error(f"Error fetching paginated suppliers: {str(e)}")
            raise

    @staticmethod
    async def soft_delete(supplier_id: int, deleted_by: int) -> Dict[str, Any]:
        """
        Soft delete a supplier by setting isDelete to True.
        """
        try:
            query = (
                update(suppliers_table)
                .where(suppliers_table.c.id == supplier_id)
                .values(
                    isDelete=True,
                    deletedBy=deleted_by,
                    deletedAt=dt.now().isoformat()
                )
            )
            await database.execute(query)
            return {"message": "Supplier deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting supplier: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def search_by_keyword(keyword: str) -> List[SupplierResponse]:
        """
        Search suppliers by keyword across multiple fields.
        """
        try:
            if not keyword:
                return await SupplierRepository.get_all()
                
            keyword_filter = f"%{keyword}%"
            query = select(suppliers_table).where(
                suppliers_table.c.isDelete == False
            ).where(
                suppliers_table.c.name.ilike(keyword_filter) |
                suppliers_table.c.address.ilike(keyword_filter) |
                suppliers_table.c.city.ilike(keyword_filter) |
                suppliers_table.c.province.ilike(keyword_filter) |
                suppliers_table.c.phoneNumber.ilike(keyword_filter) |
                suppliers_table.c.email.ilike(keyword_filter) |
                suppliers_table.c.itemsSold.ilike(keyword_filter) |
                suppliers_table.c.serviceArea.ilike(keyword_filter)
            )
            
            result = await database.fetch_all(query)
            return [SupplierResponse.model_validate(dict(row)) for row in result]
        except Exception as e:
            log_error(f"Error searching suppliers: {str(e)}")
            raise