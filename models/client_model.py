from pydantic import BaseModel, EmailStr, StringConstraints, Field
from typing import Annotated
from sqlalchemy import Table, Column, DateTime, Integer, String, Boolean, insert, select, or_, func
from utils.database import metadata
from datetime import date
from utils.database import database
from utils.logger_utils import log_error

# Define the Client model
class Client(BaseModel):
    prefix: str # Prefix for client name (e.g., "PT", "CV", "UD", etc.)
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]  # Name must be between 1 and 100 characters
    address: Annotated[str, StringConstraints(min_length=1, max_length=255)]  # Address must be between 1 and 255 characters
    city: Annotated[str, StringConstraints(min_length=1, max_length=100)]  # City must be between 1 and 100 characters
    province: Annotated[str, StringConstraints(min_length=1, max_length=100)]  # Province must be between 1 and 100 characters
    phoneNumber: Annotated[str, StringConstraints(pattern=r"^\+?\d{10,15}$")]  # Phone number must be 10-15 digits, optional "+" at the start
    email: EmailStr | None = None  # Valid email format
    npwp: Annotated[str, StringConstraints(pattern=r"^\d{16}$")] | None = None  # Optional NPWP, must be 15 digits
        
    @staticmethod
    async def create_client(client_data: dict):
        """
        Create a client in the database.
        """
        try:
            if not client_data:
                return {"error": "No client data to create.", "status": 400}
            query = insert(clients_table).values(client_data)
            client_id = await database.execute(query)
            if not client_id:
                return {"error": "Failed to create client.", "status": 500}
    
            return {"message": "Client created successfully", "client_id": client_id}
        except Exception as e:
            log_error(f"Error creating client: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_clients(page: int, pageSize: int = 10, sortBy: str = None, sortByDirection: str = "asc", keyword: str = None):
        """
        Retrieve a list of clients from the database.
        """
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        offset = (page - 1) * pageSize
        conditions = [clients_table.c.isDelete == False]

        or_conditions = []
        if keyword:
            or_conditions.append(clients_table.c.name.ilike(f"%{keyword}%"))
            or_conditions.append(clients_table.c.address.ilike(f"%{keyword}%"))
            or_conditions.append(clients_table.c.city.ilike(f"%{keyword}%"))
            or_conditions.append(clients_table.c.province.ilike(f"%{keyword}%"))
            or_conditions.append(clients_table.c.phoneNumber.ilike(f"%{keyword}%"))
            or_conditions.append(clients_table.c.email.ilike(f"%{keyword}%"))
        
        conditions.append(or_(*or_conditions))

        if sortBy == "name":
            order_by = clients_table.c.name.desc() if sortByDirection == "desc" else clients_table.c.name
        else:
            order_by = clients_table.c.createdAt.desc()  # Default sorting by createdAt

        try:
            query = (
                select(*clients_table.c)
                .where(*conditions)
                .order_by(order_by)
                .offset(offset)
                .limit(pageSize)
            )

            clients = await database.fetch_all(query)

            # Count the total number of clients
            count_query = (
                select(func.count())
                .select_from(clients_table)
                .where(*conditions)
            )
            count = await database.fetch_val(count_query)

            return {"data": clients, "count": count}
        except Exception as e:
            log_error(f"Error retrieving clients: {str(e)}")
            return {"error": str(e), "status": 500}
    
# Define the clients table
clients_table = Table(
    "clients",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("prefix", String(10), nullable=False, default=""),
    Column("name", String(255), nullable=False),
    Column("address", String(255), nullable=False),
    Column("city", String(100), nullable=False),
    Column("province", String(100), nullable=False),
    Column("phoneNumber", String(20), nullable=False),
    Column("email", String(255), nullable=True),
    Column("npwp", String(50), nullable=True),
    Column("createdAt", DateTime(), nullable=False,default=date.today()),
    Column("createdBy", Integer, nullable=False),
    Column("updatedAt", DateTime(), nullable=True,default=None),
    Column("updatedBy", Integer, nullable=True, default=None),
    Column("isDelete", Boolean, nullable=False, default=False),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("deletedBy", Integer, nullable=True, default=None),
)