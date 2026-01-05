import meilisearch
import os
from utils.logger_utils import log_info, log_error
from models.supplier_model import suppliers_table
from utils.database import database
from sqlalchemy import insert, select
from datetime import datetime

# Get master key from environment variable
masterKey = os.getenv("MEILISEARCH_MASTER_KEY")

# Initialize Meilisearch client
client = meilisearch.Client("http://localhost:7700", masterKey)
# Initialize Meilisearch index
index_name = "suppliers"
index = client.index(index_name)
# Initialize Meilisearch settings
# Improved Meilisearch settings
settings = {
    "displayedAttributes": [
        "id", "prefix", "name", "address", "city", "province", 
        "phone_number", "email", "npwp", "items_sold", "service_area"
    ],
    "searchableAttributes": [
        "name", "prefix", "items_sold", "service_area", "city", 
        "province", "address", "email"
    ],
    "filterableAttributes": [
        "city", "province", "service_area", "items_sold", "is_active",
        "created_by", "prefix"
    ],
    "sortableAttributes": ["name", "city", "province"],
    "rankingRules": [
        "words",
        "typo",
        "proximity",
        "attribute",
        "sort",
        "exactness"
    ],
    "stopWords": ["pt", "cv", "ud", "tbk", "lainnya", "pribadi"],
    "nonSeparatorTokens": [".", ",", "-"],
    "separatorTokens": ["/", "\\", "&"]
}

client.index(index_name).update_settings(settings)
# Enhanced synonyms mapping
expanded_synonyms = {
    "jabodetabek": ["jakarta", "depok", "tangerang", "bekasi", "bogor", "jabodetabek"],
    "bekasi": ["cikarang", "kabupaten bekasi"],
    "jawa barat": ["bandung", "cimahi", "bekasi", "bogor", "jabar", "west java"],
    "jawa tengah": ["semarang", "solo", "salatiga", "magelang", "surakarta", "jateng", "central java"],
    "jawa timur": ["surabaya", "malang", "kediri", "probolinggo", "sidoarjo", "mojokerto", "jatim", "east java"],
    "bali": ["denpasar", "badung", "tabanan", "klungkung", "kuta", "ubud"],
    "sumatera utara": ["medan", "binjai", "deliserdang", "langkat", "sumut", "north sumatra"],
    "dki jakarta": ["jakarta pusat", "jakarta selatan", "jakarta timur", "jakarta utara", "jakarta barat"],
    "sewa": ["rental", "penyewaan"],
    "forklift": ["alat angkat", "material handling"],
    "excavator": ["backhoe", "beko"],
    "genset": ["generator", "generator set"],
    "selfloader": ["truk angkut", "truk muat sendiri"],
    "trailer": ["kereta gandeng", "truk gandeng"],
    "tronton": ["truk besar", "truk 3 sumbu"]
}

client.index(index_name).update_synonyms(expanded_synonyms)

typo_settings = {
    "minWordSizeForTypos": {
        "oneTypo": 4,
        "twoTypos": 8
    },
    "disableOnWords": [],
    "disableOnAttributes": ["id", "npwp"]
}

client.index(index_name).update_typo_tolerance(typo_settings)

async def sync_meilisearch():
    try:
        client.create_index(index_name, {"primaryKey": "id"})
        print(f"Index '{index_name}' created successfully.")

        # Clear all the data
        index.delete_all_documents()
        print(f"All documents in index '{index_name}' deleted successfully.")

        # Add existing supplier to the index
        query = select(suppliers_table)
        suppliers = await database.fetch_all(query)
        for supplier in suppliers:
            supplier_dict = dict(supplier)

            supplier_dict["phone_number"] = supplier_dict["phoneNumber"]
            supplier_dict["name"] = supplier_dict["name"] + ", " + supplier_dict["prefix"]

            #Sold items
            supplier_dict["items_sold"] = supplier_dict["itemsSold"].split(",") if supplier_dict["itemsSold"] else []
            #Service area
            supplier_dict["service_area"] = supplier_dict["serviceArea"].split(",") if supplier_dict["serviceArea"] else []
            
            # Remove unnecessary fields
            for key, value in supplier_dict.items():
                if isinstance(value, datetime):
                    supplier_dict[key] = value.isoformat()  # Convert datetime to ISO format
                elif value is None:
                    supplier_dict[key] = ""

            index.add_documents([supplier_dict])
            print(f"Document with ID '{supplier_dict['id']}' added to index '{index_name}' successfully.")

    except Exception as e:
        raise e


async def setup_meilisearch():
    # Apply settings to the index
    index.update_settings(settings)
    log_info(f"Settings applied to index '{index_name}' successfully.")