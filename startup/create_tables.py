import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utils.config

from utils.logger_utils import log_info
from utils.database import engine, metadata

import models.user_model  # Import the user model to create the table
import models.purchase_model  # Import the purchase model to create the table
import models.supplier_model  # Import the supplier model to create the table
import models.purchase_order_model  # Import the purchase order model to create the table
import models.client_model  # Import the client model to create the table
import models.reimbursement_model  # Import the reimbursement model to create the table
import models.bank_model # Import the bank model to create the table
import models.expense_model # Import the expense model to create the table
import models.payment_model  # Import the payment model to create the table
import models.employee_model  # Import the employee model to create the table
import models.expense_opponent_model  # Import the expense opponent model to create the table

if __name__ == "__main__":
    metadata.create_all(engine, checkfirst=True)
    log_info("All tables created successfully.")
