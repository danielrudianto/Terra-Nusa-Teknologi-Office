from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.meilisearch import sync_meilisearch
from utils.database import database
from utils.logger_utils import log_info, log_error
import asyncio

async def main():
    print("Masuk")
    try:
        await database.connect()
        print("Database connected successfully!")
        await sync_meilisearch()
        print("Meilisearch synchronization completed successfully!")
    except Exception as e:
        print(f"Error during Meilisearch synchronization: {e}")
        raise
    finally:
        await database.disconnect()
        print("Database disconnected successfully!")

if __name__ == "__main__":
    asyncio.run(main())