import redis
from models.bank_model import bank_accounts_table
from utils.database import database
import json
from sqlalchemy import select
from utils.logger_utils import log_error

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

async def sync_redis():
    """
    Synchronize the Redis connection.
    This function is a placeholder for any future synchronization logic.
    """
    # Clear "bank_account" list in Redis
    r.delete("bank_account")

    # Fetch all bank accounts from the database
    query = select(
        bank_accounts_table.c.id,
        bank_accounts_table.c.bankName,
        bank_accounts_table.c.bankAccountName,
        bank_accounts_table.c.bankAccountNumber
    ).where(bank_accounts_table.c.isDelete == False)
    
    try:
        result = await database.fetch_all(query)

        # Check if result is empty
        if not result:
            print("No bank accounts found.")
            return {"message": "No bank accounts to synchronize."}

        # Iterate through the results and push each bank account to Redis
        for bank in result:
            r.rpush("bank_account", json.dumps(dict(bank)))
        
        return {"message": "Redis synchronized with bank accounts."}
    
    except Exception as e:
        log_error(f"Error during synchronization: {e}")
        return {"error": str(e)}
