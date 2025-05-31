from sqlalchemy import func, insert, select, update, delete, or_
from utils.database import database
from models.payment_model import payments_table
from models.purchase_model import purchases_table
from utils.logger_utils import log_error, log_info
from datetime import datetime

class PaymentController:
    @staticmethod
    async def create_payment(payment_data: dict, userID: int):
        """
        Create a new payment in the database.
        
        Args:
            payment_data (dict): The data of the payment to create.
            userID (int): The ID of the user creating the payment.
        
        Returns:
            dict: A success message with the created payment ID.
        """
        payment_data["createdBy"] = userID
        payment_data["createdAt"] = datetime.now()
        log_info(f"Creating payment with data: {payment_data}")
        
        try:
            query = insert(payments_table).values(**payment_data)
            payment_id = await database.execute(query)
            
            log_info(f"Payment created successfully with ID: {payment_id}")

            # Update the payment status
            if payment_data["purchaseID"] is not None:
                #Get the purchase data
                purchase_query = select(purchases_table).where(
                    purchases_table.c.id == payment_data["purchaseID"]
                )
                purchase_data = await database.fetch_one(purchase_query)

                #Total payments for the purchase
                total_payments_query = select(func.sum(payments_table.c.amount)).where(
                    payments_table.c.purchaseID == payment_data["purchaseID"]
                )
                total_payments = await database.fetch_val(total_payments_query) or 0
                log_info(f"Total payments for purchase {payment_data['purchaseID']}: {total_payments}")

                #Check if the total payments is greater than or equal to the purchase amount
                dpp = purchase_data["dpp"] if purchase_data["dpp"] is not None else 0
                ppnPercentage = purchase_data["ppn"] if purchase_data["ppn"] is not None else 0
                otherValue = purchase_data["otherValue"] if purchase_data["otherValue"] is not None else 0
                pbbkb = purchase_data["pbbkb"] if purchase_data["pbbkb"] is not None else 0

                totalAmount = dpp + (dpp * (ppnPercentage / 100)) + otherValue + pbbkb
                log_info(f"Total amount for purchase {payment_data['purchaseID']}: {totalAmount}")

                if total_payments == totalAmount:
                    log_info(f"Purchase {payment_data['purchaseID']} is now paid.")
                    # Update the purchase status to paid
                    await database.execute(
                        purchases_table.update().where(
                            purchases_table.c.id == payment_data["purchaseID"]
                        ).values(
                            updatedBy=userID,
                            updatedAt=datetime.now(),
                            isPaid=True
                        )
                    )
                else:
                    log_info(f"Purchase {payment_data['purchaseID']} is not yet fully paid.")
                    # Update the purchase status to unpaid

                purchases_table.update().where(
                    purchases_table.c.id == payment_data["purchaseID"]
                ).values(
                    updatedBy=userID,
                    updatedAt=datetime.now(),
                    isPaid=True
                )

            return {"message": "Payment created successfully", "payment_id": payment_id}
        except Exception as e:
            log_error(f"Error creating payment: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_payments_by_purchase_id(purchase_id: int):
        """
        Get payments by purchase ID.
        
        Args:
            purchase_id (int): The ID of the purchase.
        
        Returns:
            list: A list of payments for the specified purchase.
        """
        log_info(f"Retrieving payments for purchase ID: {purchase_id}")
        
        try:
            query = select(payments_table).where(payments_table.c.purchaseID == purchase_id)
            payments = await database.fetch_all(query)
            
            if not payments:
                log_info(f"No payments found for purchase ID: {purchase_id}")
                return {"message": "No payments found", "payments": []}
            
            log_info(f"Retrieved {len(payments)} payments for purchase ID: {purchase_id}")
            return {"payments": payments}
        except Exception as e:
            log_error(f"Error retrieving payments: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def delete_payment_by_id(id: int):
        """
        Delete a payment by ID.
        
        Args:
            id (int): The ID of the payment to delete.
        
        Returns:
            dict: A success message or an error message.
        """
        log_info(f"Deleting payment with ID: {id}")
        
        try:
            query = delete(payments_table).where(payments_table.c.id == id)
            result = await database.execute(query)
            
            if result == 0:
                log_info(f"No payment found with ID: {id}")
                return {"error": "No payment found to delete", "status": 404}
            
            log_info(f"Payment with ID: {id} deleted successfully")
            return {"message": "Payment deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting payment: {str(e)}")
            return {"error": str(e), "status": 500}