import meilisearch
import os
from utils.logger_utils import log_info, log_error
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

def setup_meilisearch():
    try:
        client.create_index(index_name, {"primaryKey": "id"})
        log_info(f"Index '{index_name}' created successfully.")
    except meilisearch.errors.MeiliSearchApiError as e:
        if e.error_code == "index_already_exists":
            log_info(f"Index '{index_name}' already exists.")
        else:
            raise e

    # Apply settings to the index
    index.update_settings(settings)
    log_info(f"Settings applied to index '{index_name}' successfully.")