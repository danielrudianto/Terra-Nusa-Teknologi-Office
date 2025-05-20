import meilisearch
import os
from utils.logger_utils import log_info, log_error
from models.supplier_model import suppliers_table
from utils.database import database
from sqlalchemy import insert, select

# Get master key from environment variable
masterKey = os.getenv("MEILISEARCH_MASTER_KEY")

# Initialize Meilisearch client
client = meilisearch.Client("http://localhost:7700", masterKey)
# Initialize Meilisearch index
index_name = "suppliers"
index = client.index(index_name)
# Initialize Meilisearch settings
settings = {
    "displayedAttributes": ["id", "name", "address", "city", "province", "phone_number", "email", "npwp", "items_sold", "service_area"],
    "searchableAttributes": ["name", "address", "city", "province", "phone_number", "email", "npwp", "items_sold", "service_area"],
    "filterableAttributes": ["is_active"],
}

client.index(index_name).update_settings(settings)
client.index(index_name).update_synonyms({
    "jabodetabek": ["jakarta", "depok", "tangerang", "bekasi", "bogor"],
    "jawa_barat": ["bandung", "cimahi", "bekasi", "bogor"],
    "jawa_tengah": ["semarang", "solo", "salatiga", "magelang"],
    "jawa_timur": ["surabaya", "malang", "kediri", "probolinggo"],
    "bali": ["denpasar", "badung", "tabanan", "klungkung"],
    "sumatera_utara": ["medan", "binjai", "deliserdang", "langkat"],
})


async def setup_meilisearch():
    try:
        client.create_index(index_name, {"primaryKey": "id"})
        log_info(f"Index '{index_name}' created successfully.")

        #Clear all the data
        index.delete_all_documents()
        log_info(f"All documents in index '{index_name}' deleted successfully.")

        # Add existing supplier to the index
        query = select(suppliers_table)
        suppliers = await database.fetch_all(query)
        for supplier in suppliers:
            supplier_dict = dict(supplier)

            #Sold items
            supplier_dict["itemsSold"] = supplier_dict["itemsSold"].split(",") if supplier_dict["itemsSold"] else []
            #Service area
            supplier_dict["serviceArea"] = supplier_dict["serviceArea"].split(",") if supplier_dict["serviceArea"] else []
            
            index.add_documents([supplier_dict])
            log_info(f"Document with ID '{supplier_dict['id']}' added to index '{index_name}' successfully.")

    except Exception as e:
        raise e

    # Apply settings to the index
    index.update_settings(settings)
    log_info(f"Settings applied to index '{index_name}' successfully.")