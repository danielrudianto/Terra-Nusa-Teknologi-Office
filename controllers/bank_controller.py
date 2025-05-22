from sqlalchemy import insert, select, update, delete, func
from utils.database import database
from models.bank_model import bank_accounts_table
from typing import Dict, List, Optional
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from datetime import datetime

class BankController:
    @staticmethod 
    async def create_bank_account(bank_data: Dict, userID: int) -> Dict:
        """
        Create a new bank account in the database.
        
        Args:
            bank_data (Dict): The data of the bank account to create.
        
        Returns:
            Dict: A success message with the created bank account ID.
        """
        log_info(userID)
        log_info(f"Creating bank account with data: {bank_data}")
        try:
            bank_data["createdAt"] = datetime.now()
            bank_data["createdBy"] = userID

            query = insert(bank_accounts_table).values(**bank_data)
            bank_id = await database.execute(query)
            log_info(f"Bank account created successfully with ID: {bank_id}")
            return {"message": "Bank account created successfully", "bank_id": bank_id}
        except IntegrityError as e:
            log_error(f"Integrity error: {str(e)}")
            raise HTTPException(status_code=400, detail="Bank account already exists.")
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def get_bank_accounts(page: int) -> Dict:
        """
        Retrieve all bank accounts from the database.
        
        Args:
            page (int): The page number for pagination.
        
        Returns:
            Dict: A list of all bank accounts.
        """
        log_info(f"Getting all bank accounts for page: {page}")
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            offset = (page - 1) * 10
            query = select(bank_accounts_table).offset(offset).limit(10)
            bank_accounts = await database.fetch_all(query)

            # Count the total number of bank accounts
            count_query = select(func.count()).select_from(bank_accounts_table)
            count = await database.fetch_val(count_query)

            return {"data": bank_accounts, "count": count}
        except Exception as e:
            log_error(f"Error retrieving bank accounts: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_bank_account_by_id(bank_id: int) -> Optional[Dict]:
        """
        Retrieve a bank account by its ID.
        
        Args:
            bank_id (int): The ID of the bank account to retrieve.
        
        Returns:
            Optional[Dict]: The bank account data if found, otherwise None.
        """
        log_info(f"Getting bank account with ID: {bank_id}")
        try:
            query = select(bank_accounts_table).where(bank_accounts_table.c.id == bank_id)
            bank_account = await database.fetch_one(query)
            return bank_account
        except Exception as e:
            log_error(f"Error retrieving bank account with ID {bank_id}: {str(e)}")
            return None
        
    @staticmethod
    async def update_bank_account(bank_data: Dict, bank_id: int, userID: int) -> Dict:
        """
        Update a bank account in the database.
        
        Args:
            bank_data (Dict): The updated data of the bank account.
            bank_id (int): The ID of the bank account to update.
        
        Returns:
            Dict: A success message if the update was successful.
        """
        log_info(f"Updating bank account with ID: {bank_id} and data: {bank_data}")
        #Check if there is any bank account with the same number but different ID
        
        
        try:
            existing_account_query = (
                select(bank_accounts_table)
                .where(bank_accounts_table.c.bankAccountNumber == bank_data["bankAccountNumber"])
                .where(bank_accounts_table.c.id != bank_id)
            )
            existing_account = await database.fetch_one(existing_account_query)
            if existing_account:
                log_error(f"Bank account with the same number already exists: {bank_data['bankAccountNumber']}")
                return {"error": "Bank account with the same number already exists", "status": 404}
        
            update_fields = bank_data.copy()
            update_fields.pop("id", None)
            update_fields["updatedAt"] = datetime.now()
            update_fields["updatedBy"] = userID

            query = (
                update(bank_accounts_table)
                .where(bank_accounts_table.c.id == bank_id)
                .values(**update_fields)
            )
            result = await database.execute(query)
            if result == 0:  # Check if any rows were affected
                return {"error": "Update failed or bank account not found", "status": 404}
            return {"message": "Bank account updated successfully"}
        except Exception as e:
            log_error(f"Error updating bank account with ID {bank_id}: {str(e)}")
            return {"error": str(e), "status": 500}