from pydantic import BaseModel
from datetime import datetime as dt, date as d
from utils.database import metadata, database
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, ForeignKey, Float
from utils.logger_utils import log_error

class SalarySlip(BaseModel):
    userID: int  # ID of the user
    month: int  # Month of the salary slip
    year: int  # Year of the salary slip
    isPaid: bool = False  # Whether the salary slip is paid or not
    basicSalary: float  # Basic salary amount
    transportationAllowanceQuantity: float = 0.0  # Quantity of transportation allowance
    transportationAllowanceRate: float = 0.0  # Rate of transportation allowance
    mealAllowanceQuantity: float = 0.0  # Quantity of meal allowance
    mealAllowanceRate: float = 0.0  # Rate of meal allowance
    overtimeQuantity: float = 0.0  # Quantity of overtime
    overtimeRate: float = 0.0  # Rate of overtime
    taxAmount: float = 0.0  # Amount of tax deducted
    createdAt: dt = dt.now()  # Creation date and time of the salary slip in ISO format
    updatedAt: dt | None = None  # Last update date and time of the salary slip in ISO format
    createdBy: int | None = None  # ID of the user who created the salary slip
    updatedBy: int | None = None  # ID of the user who last updated the salary slip, can be None if not updated
    isDelete: bool = False  # Whether the salary slip is deleted or not
    deletedAt: dt | None = None  # Deletion date and time of the salary slip in ISO format, can be None if not deleted
    deletedBy: int | None = None  # ID of the user who deleted the salary slip, can be None if not deleted
    taxCategory: str # Category of tax applied to the salary slip, e.g., "TK/0", "TK/1", etc.

    #Constructor
    def __init__(self, **data):
        super().__init__(**data)
        self.createdAt = dt.now()
        self.updatedAt = dt.now()
        self.isDelete = False
        self.deletedAt = None
        self.deletedBy = None

    # String representation for better readability
    def __str__(self):
        return f"SalarySlipModel(userID={self.userID}, month={self.month}, year={self.year}, date={self.date}, isPaid={self.isPaid}, amount={self.amount}, createdAt={self.createdAt}, updatedAt={self.updatedAt}, createdBy={self.createdBy}, updatedBy={self.updatedBy}, isDelete={self.isDelete}, deletedAt={self.deletedAt}, deletedBy={self.deletedBy})"
    
    # Representation method for better debugging and logging
    def __repr__(self):
        return f"SalarySlipModel(userID={self.userID}, month={self.month}, year={self.year}, date={self.date}, isPaid={self.isPaid}, amount={self.amount}, createdAt={self.createdAt}, updatedAt={self.updatedAt}, createdBy={self.createdBy}, updatedBy={self.updatedBy}, isDelete={self.isDelete}, deletedAt={self.deletedAt}, deletedBy={self.deletedBy})"
    
    # Create
    @staticmethod
    async def create(data: dict):
        """
        Create a new salary slip in the database.
        
        Returns:
            dict: A success message with the created salary slip ID.
        """
        query = salary_slips_table.insert().values(
            userID=data.userID,
            month=data.month,
            year=data.year,
            basicSalary=data.basicSalary,
            mealAllowanceQuantity=data.mealAllowanceQuantity,
            mealAllowanceRate=data.mealAllowanceRate,
            transportationAllowanceQuantity=data.transportationAllowanceQuantity,
            transportationAllowanceRate=data.transportationAllowanceRate,
            overtimeQuantity=data.overtimeQuantity,
            overtimeRate=data.overtimeRate,
            taxAmount=data.taxAmount,
            createdAt=data.createdAt,
            updatedAt=data.updatedAt,
            createdBy=data.createdBy,
            isPaid=data.isPaid,
            isDelete=data.isDelete,
            taxCategory=data.taxCategory,
        )

        try:
            result = await database.execute(query)
            return result  # Return the ID of the created salary slip
        except Exception as e:
            log_error(f"Error creating salary slip: {str(e)}")
            return {"error": str(e), "status": 500}
    
    @staticmethod
    async def validate(userID: int, month: int, year: int):
        """
        Validate the salary slip data.
        
        Args:
            userID (int): ID of the user.
            month (int): Month of the salary slip.
            year (int): Year of the salary slip.
        
        Raises:
            ValueError: If validation fails.
        """
        #Check from salary_slips_table if the salary slip already exists
        query = salary_slips_table.select().where(
            (salary_slips_table.c.userID == userID) &
            (salary_slips_table.c.month == month) &
            (salary_slips_table.c.year == year) &
            (salary_slips_table.c.isDelete == False)
        )
        existing_slip = await database.fetch_one(query)
        if existing_slip:
            return {"error": "Salary slip already exists for this user, month, and year.", "status": 400}

        return {"message": "Validation successful."}

class SalarySlipCheck(BaseModel):
    userID: int  # ID of the user
    month: int  # Month of the salary slip
    year: int  # Year of the salary slip

    # String representation for better readability
    def __str__(self):
        return f"SalarySlipCheck(userID={self.userID}, month={self.month}, year={self.year})"
    
    # Representation method for better debugging and logging
    def __repr__(self):
        return f"SalarySlipCheck(userID={self.userID}, month={self.month}, year={self.year})"
    
    #Constructor
    def __init__(self, **data):
        super().__init__(**data)
    
    def check(self):
        """
        Check if a salary slip exists for the given user, month, and year.
        
        Returns:
            dict: A message indicating whether the salary slip exists or not.
        """
        query = salary_slips_table.select().where(
            (salary_slips_table.c.userID == self.userID) &
            (salary_slips_table.c.month == self.month) &
            (salary_slips_table.c.year == self.year) &
            (salary_slips_table.c.isDelete == False)
        )
        
        existing_slip = database.fetch_one(query)
        if existing_slip:
            return {"error": "Salary slip already exists for this user, month, and year.", "status": 404}
        else:
            return {"message": "No salary slip found for this user, month, and year."}

salary_slips_table = Table(
    "salary_slips",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("userID", Integer, ForeignKey("users.id"), nullable=False),
    Column("month", Integer, nullable=False),
    Column("year", Integer, nullable=False),
    Column("isPaid", Boolean, default=False, nullable=False),
    Column("basicSalary", Float, nullable=False),
    Column("transportationAllowanceQuantity", Float, default=0, nullable=False),
    Column("transportationAllowanceRate", Float, default=0.0, nullable=False),
    Column("mealAllowanceQuantity", Float, default=0, nullable=False),
    Column("mealAllowanceRate", Float, default=0.0, nullable=False),
    Column("overtimeQuantity", Float, default=0, nullable=False),
    Column("overtimeRate", Float, default=0.0, nullable=False),
    Column("taxAmount", Float, default=0.0, nullable=False),
    Column("taxCategory", String(50), nullable=False),  # Default tax category
    Column("createdAt", DateTime, default=dt.utcnow, nullable=False),
    Column("updatedAt", DateTime, default=dt.utcnow, onupdate=dt.utcnow, nullable=True),
    Column("createdBy", Integer, nullable=False),
    Column("updatedBy", Integer, nullable=True),
    Column("isDelete", Boolean, default=False, nullable=False),
    Column("deletedAt", DateTime, nullable=True),
    Column("deletedBy", Integer, nullable=True),
    
)

class SalarySlipAllowance(BaseModel):
    salarySlipID: int  # ID of the salary slip
    name: str  # Name of the allowance
    description: str  # Description of the allowance
    amount: float  # Amount of the allowance

    # String representation for better readability
    def __str__(self):
        return f"SalarySlipAllowance(salarySlipID={self.salarySlipID}, name={self.name}, description={self.description}, amount={self.amount})"
    
    # Representation method for better debugging and logging
    def __repr__(self):
        return f"SalarySlipAllowance(salarySlipID={self.salarySlipID}, name={self.name}, description={self.description}, amount={self.amount})"
    
    #Constructor
    def __init__(self, **data):
        super().__init__(**data)

    @staticmethod
    async def create_allowances(salarySlipID: int, allowances: list):
        """
        Create a new salary slip allowance in the database.
        
        Returns:
            dict: A success message with the created allowance ID.
        """
        if not allowances:
            return {"message": "No allowances to create."}
        
        #Create many
        query = salary_slips_allowance_table.insert().values([
            {
                "salarySlipID": salarySlipID,
                "name": allowance.name,
                "description": allowance.description,
                "amount": allowance.amount
            } for allowance in allowances
        ])

        try:
            await database.execute(query)
            return {"message": "Salary slip allowances created successfully."}
        except Exception as e:
            log_error(f"Error creating salary slip allowance: {str(e)}")
            return {"error": str(e), "status": 500}
        
class SalarySlipDeduction(BaseModel):
    salarySlipID: int  # ID of the salary slip
    name: str  # Name of the deduction
    description: str  # Description of the deduction
    amount: float  # Amount of the deduction

    # String representation for better readability
    def __str__(self):
        return f"SalarySlipDeduction(salarySlipID={self.salarySlipID}, name={self.name}, description={self.description}, amount={self.amount})"
    
    # Representation method for better debugging and logging
    def __repr__(self):
        return f"SalarySlipDeduction(salarySlipID={self.salarySlipID}, name={self.name}, description={self.description}, amount={self.amount})"
    
    #Constructor
    def __init__(self, **data):
        super().__init__(**data)

    
    @staticmethod
    async def create_deductions(salarySlipID: int, deductions: list):
        """
        Create a new salary slip deduction in the database.
        
        Returns:
            dict: A success message with the created deduction ID.
        """
        if not deductions:
            return {"message": "No deductions to create."}
        
        #Create many
        query = salary_slips_deduction_table.insert().values([
            {
                "salarySlipID": salarySlipID,
                "name": deduction.name,
                "description": deduction.description,
                "amount": deduction.amount
            } for deduction in deductions
        ])

        try:
            await database.execute(query)
            return {"message": "Salary slip deductions created successfully."}
        except Exception as e:
            log_error(f"Error creating salary slip deduction: {str(e)}")
            return {"error": str(e), "status": 500}

salary_slips_allowance_table = Table(
    "salary_slips_allowances",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("salarySlipID", Integer, ForeignKey("salary_slips.id"), nullable=False),
    Column("name", String(100), nullable=False),
    Column("description", String(255), nullable=False),
    Column("amount", Integer, nullable=False),
)

salary_slips_deduction_table = Table(
    "salary_slips_deductions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("salarySlipID", Integer, ForeignKey("salary_slips.id"), nullable=False),
    Column("name", String(100), nullable=False),
    Column("description", String(255), nullable=False),
    Column("amount", Integer, nullable=False),
)