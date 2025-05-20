import utils.config

from utils.logger_utils import log_info
from utils.database import engine, metadata

import models.user_model  # Import the user model to create the table
import models.purchase_model  # Import the purchase model to create the table
import models.project_model  # Import the project model to create the table
import models.supplier_model  # Import the supplier model to create the table
import models.purchase_order_model  # Import the purchase order model to create the table
import models.client_model  # Import the client model to create the table
import models.reimbursement_model  # Import the reimbursement model to create the table

if __name__ == "__main__":
    metadata.create_all(engine, checkfirst=True)
    log_info("All tables created successfully.")
