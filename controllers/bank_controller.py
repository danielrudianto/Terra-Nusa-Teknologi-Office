from sqlalchemy import insert, select, update, delete, func
from utils.database import database
from models.bank_model import BankAccount
from typing import Dict, List, Optional
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from datetime import datetime
from utils.redis import r
import json

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
            # Create new Bank model

            bank_data["createdAt"] = datetime.now()
            bank_data["createdBy"] = userID

            bank = BankAccount(**bank_data)
            result = await bank.create()
            if "error" in result:
                log_error(f"Error creating bank account: {result['error']}")
                raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
            
            bank_id = result['bank_account_id']            

            # Add to redis
            r.rpush("bank_account", json.dumps({
                "id": bank_id,
                "bankAccountNumber": bank_data["bankAccountNumber"],
                "bankAccountName": bank_data["bankAccountName"],
                "bankName": bank_data["bankName"],
            }))

            log_info(f"Bank account created successfully with ID: {result['bank_account_id']}")
            return {"message": "Bank account created successfully", "bank_id": result['bank_account_id']}
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
            result = await BankAccount.get_banks(page=page, pageSize = 10)
            if "error" in result:
                log_error(f"Error retrieving bank accounts: {result['error']}")
                return {"error": result["error"], "status": result["status"]}

            return result
        except Exception as e:
            log_error(f"Error retrieving bank accounts: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_all_bank_accounts() -> List[Dict]:
        """
        Retrieve the top bank accounts from the database.
        
        Returns:
            List[Dict]: A list of top bank accounts.
        """
        log_info("Getting top bank accounts")
        try:
            bank_accounts = r.lrange("bank_account", 0, -1)
            return [json.loads(account) for account in bank_accounts]
        except Exception as e:
            log_error(f"Error retrieving top bank accounts: {str(e)}")
            return []

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
            bank_account = await BankAccount.get_bank_account_by_id(bank_id)
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
        
    @staticmethod
    async def delete_bank_account(bankID: int, userID: int):
        """
        Delete a bank account from the database.
        
        Args:
            bankID (int): The ID of the bank account to delete.
            userID (int): The ID of the user performing the deletion.
        
        Returns:
            Dict: A success message if the deletion was successful.
        """
        log_info(f"Deleting bank account with ID: {bankID}")
        try:
            result = await BankAccount.delete_bank_account(bankID, userID)
            if result == 0:  # Check if any rows were affected
                return {"error": "Deletion failed or bank account not found", "status": 404}
            # Remove from redis
            bank_accounts = r.lrange("bank_account", 0, -1)
            for account in bank_accounts:
                account_data = json.loads(account)
                if account_data["id"] == bankID:
                    r.lrem("bank_account", 0, json.dumps(account_data))
                    break
            return {"message": "Bank account deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting bank account with ID {bankID}: {str(e)}")
            return {"error": str(e), "status": 500}