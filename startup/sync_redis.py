import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.redis import sync_redis
from utils.database import database
from utils.logger_utils import log_info, log_error
import asyncio

async def main():
    try:
        await database.connect()
        log_info("Database connected successfully!")
        await sync_redis()
        log_info("Redis synchronization completed successfully!")
    except Exception as e:
        log_error(f"Error during Redis synchronization: {e}")
        raise
    finally:
        await database.disconnect()
        log_info("Database disconnected successfully!")

if __name__ == "__main__":
    asyncio.run(main())