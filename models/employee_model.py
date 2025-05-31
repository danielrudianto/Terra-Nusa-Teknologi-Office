from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey, insert, select, func, or_, update
from utils.database import metadata
from datetime import date as d,datetime as dt
from utils.database import database
from utils.logger_utils import log_error
from sqlalchemy.exc import IntegrityError

# Define the Purchase model
class Employee(BaseModel):
    id: Optional[int] = None  # Unique ID for the employee, optional for creation
    name: str  # Name of the employee
    nik: str  # National Identification Number (NIK) of the employee
    birthday: d  # Birth date of the employee
    email: str  # Email of the employee
    phoneNumber: str  # Phone number of the employee
    address: str  # Address of the employee
    position: str  # Position of the employee
    department: str  # Department of the employee
    isDelete: bool = False  # Flag to indicate if the employee is deleted
    taxCategory: str  # Tax category of the employee (Either TK/0, TK/1, TK/2, TK/3, K/0, K/1, K/2, K/3)
    createdAt: dt = Field(default_factory=dt.now)  # Creation date
    createdBy: int | None = None  # ID of the user who created the employee
    updatedAt: Optional[dt] = None  # Update date
    updatedBy: Optional[int] = None  # ID of the user who updated the employee
    deletedAt: Optional[dt] = None  # Deletion date
    deletedBy: Optional[int] = None  # ID of the user who deleted the employee

    #Initialize the model
    def __init__(self, **data):
        super().__init__(**data)
        if not self.createdAt:
            self.createdAt = dt.now()
        if not self.updatedAt:
            self.updatedAt = None
        if not self.deletedAt:
            self.deletedAt = None
        if not self.isDelete:
            self.isDelete = False

    async def create_employee(self) -> dict:
        """
        Create a new employee in the database.
        """
        query = insert(employees_table).values(
            name=self.name,
            nik=self.nik,
            birthday=self.birthday,
            email=self.email,
            phoneNumber=self.phoneNumber,
            address=self.address,
            position=self.position,
            department=self.department,
            isDelete=self.isDelete,
            taxCategory=self.taxCategory,
            createdAt=self.createdAt,
            createdBy=self.createdBy
        )
        try:
            employee_id = await database.execute(query)
            return {"message": "Employee created successfully", "employee_id": employee_id}
        except IntegrityError as e:
            log_error(f"Integrity error while creating employee: {str(e)}")
            return {"error": "Employee with this NIK or email already exists.", "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while creating employee: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
    
    async def update_employee(self) -> dict:
        """
        Update an existing employee in the database.
        """
        query = (
            update(employees_table)
            .where(employees_table.c.id == self.id)
            .values(
                name=self.name,
                nik=self.nik,
                birthday=self.birthday,
                email=self.email,
                phoneNumber=self.phoneNumber,
                address=self.address,
                position=self.position,
                department=self.department,
                isDelete=self.isDelete,
                taxCategory=self.taxCategory,
                updatedAt=dt.now(),
                updatedBy=self.updatedBy
            )
        )
        try:
            await database.execute(query)
            return {"message": "Employee updated successfully", "employee_id": self.id}
        except IntegrityError as e:
            log_error(f"Integrity error while updating employee: {str(e)}")
            return {"error": "Employee with this NIK or email already exists.", "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while updating employee: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_employees(keyword: str, page: int, pageSize: int = 10, sortBy: str = None, sortByDirection: str = "asc"):
        """
        Retrieve a list of employees from the database.
        """
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
            
        
        try:
            offset = (page - 1) * pageSize  # Assuming page size is 10
            query = select(
                employees_table,
                func.count(employees_table.c.id).over().label("total_count")
            ).where(
                or_(
                    employees_table.c.name.ilike(f"%{keyword}%"),
                    employees_table.c.nik.ilike(f"%{keyword}%"),
                    employees_table.c.email.ilike(f"%{keyword}%")
                )
            ).offset(offset).limit(pageSize)

            if sortBy == "name":
                if sortByDirection == "desc":
                    query = query.order_by(employees_table.c.name.desc())
                else:
                    query = query.order_by(employees_table.c.name.asc())
            
            result = await database.fetch_all(query)

            response = []
            for row in result:
                employee_data = Employee(
                    id=row.id,
                    name=row.name,
                    nik=row.nik,
                    birthday=row.birthday,
                    email=row.email,
                    phoneNumber=row.phoneNumber,
                    address=row.address,
                    position=row.position,
                    department=row.department,
                    isDelete=row.isDelete,
                    taxCategory=row.taxCategory,
                    createdAt=row.createdAt,
                    createdBy=row.createdBy,
                    updatedAt=row.updatedAt,
                    updatedBy=row.updatedBy,
                    deletedAt=row.deletedAt,
                    deletedBy=row.deletedBy
                )
                response.append(employee_data)

            # Get the count
            total_count_query = select(func.count(employees_table.c.id)).where(
                or_(
                    employees_table.c.name.ilike(f"%{keyword}%"),
                    employees_table.c.nik.ilike(f"%{keyword}%"),
                    employees_table.c.email.ilike(f"%{keyword}%")
                )
            )
            total_count = await database.fetch_val(total_count_query)

            return {"data": response, "count": total_count}
        except Exception as e:
            log_error(f"Error fetching employees: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_employee_by_id(employee_id: int) -> dict:
        """
        Get an employee by ID from the database.
        """
        try:
            query = select(employees_table).where(employees_table.c.id == employee_id)
            employee = await database.fetch_one(query)

            if not employee:
                return {"error": "Employee not found", "status": 404}

            return Employee(
                id=employee.id,
                name=employee.name,
                nik=employee.nik,
                birthday=employee.birthday,
                email=employee.email,
                phoneNumber=employee.phoneNumber,
                address=employee.address,
                position=employee.position,
                department=employee.department,
                isDelete=employee.isDelete,
                taxCategory=employee.taxCategory,
                createdAt=employee.createdAt,
                createdBy=employee.createdBy,
                updatedAt=employee.updatedAt,
                updatedBy=employee.updatedBy,
                deletedAt=employee.deletedAt,
                deletedBy=employee.deletedBy
            )
        except Exception as e:
            log_error(f"Error fetching employee: {str(e)}")
            return {"error": str(e), "status": 500}

employees_table = Table(
    "employees",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(100), nullable=False),
    Column("nik", String(50), nullable=False, unique=True),
    Column("birthday", Date(), nullable=False),
    Column("email", String(100), nullable=False, unique=True),
    Column("phoneNumber", String(20), nullable=False),
    Column("address", String(255), nullable=False),
    Column("position", String(50), nullable=False),
    Column("department", String(50), nullable=False),
    Column("isDelete", Boolean(), default=False, nullable=False),
    Column("taxCategory", String(10), nullable=False),
    Column("createdAt", DateTime(), default=dt.now, nullable=False),
    Column("createdBy", Integer(), ForeignKey('users.id'), nullable=True),
    Column("updatedAt", DateTime(), nullable=True),
    Column("updatedBy", Integer(), ForeignKey('users.id'), nullable=True),
    Column("deletedAt", DateTime(), nullable=True),
    Column("deletedBy", Integer(), ForeignKey('users.id'), nullable=True)
)