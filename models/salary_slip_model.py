from pydantic import BaseModel
from datetime import datetime as dt, date as d
from utils.database import metadata, database
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, ForeignKey, Float, select, func, update
from utils.logger_utils import log_error
from models.employee_model import employees_table

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
    bankName: str  # Name of the bank
    bankAccountName: str  # Name of the bank account
    bankAccountNumber: str  # Bank account number
    paymentMethod: str  # Payment method
    createdAt: dt = dt.now()  # Creation date and time of the salary slip in ISO format
    updatedAt: dt | None = None  # Last update date and time of the salary slip in ISO format
    createdBy: int | None = None  # ID of the user who created the salary slip
    updatedBy: int | None = None  # ID of the user who last updated the salary slip, can be None if not updated
    isDelete: bool = False  # Whether the salary slip is deleted or not
    deletedAt: dt | None = None  # Deletion date and time of the salary slip in ISO format, can be None if not deleted
    deletedBy: int | None = None  # ID of the user who deleted the salary slip, can be None if not deleted
    taxCategory: str # Category of tax applied to the salary slip, e.g., "TK/0", "TK/1", etc.
    position: str # Position of the employee
    department: str # Department of the employee

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
    async def create(self):
        """
        Create a new salary slip in the database.
        
        Returns:
            dict: A success message with the created salary slip ID.
        """
        query = salary_slips_table.insert().values(
            userID=self.userID,
            month=self.month,
            year=self.year,
            basicSalary=self.basicSalary,
            mealAllowanceQuantity=self.mealAllowanceQuantity,
            mealAllowanceRate=self.mealAllowanceRate,
            transportationAllowanceQuantity=self.transportationAllowanceQuantity,
            transportationAllowanceRate=self.transportationAllowanceRate,
            overtimeQuantity=self.overtimeQuantity,
            overtimeRate=self.overtimeRate,
            taxAmount=self.taxAmount,
            createdAt=self.createdAt,
            updatedAt=self.updatedAt,
            createdBy=self.createdBy,
            isPaid=self.isPaid,
            isDelete=self.isDelete,
            taxCategory=self.taxCategory,
            position=self.position,
            department=self.department,
            bankAccountName=self.bankAccountName,
            bankAccountNumber=self.bankAccountNumber,
            bankName=self.bankName,
            paymentMethod=self.paymentMethod
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

    @staticmethod
    async def fetch(page: int, pageSize: int, keyword: str):
        allowance_subq = (
            select(
                salary_slips_allowance_table.c.salarySlipID,
                func.coalesce(func.sum(salary_slips_allowance_table.c.amount), 0).label("allowance")
            )
            .group_by(salary_slips_allowance_table.c.salarySlipID)
        ).subquery()

        # Deduction subquery
        deduction_subq = (
            select(
                salary_slips_deduction_table.c.salarySlipID,
                func.coalesce(func.sum(salary_slips_deduction_table.c.amount), 0).label("deduction")
            )
            .group_by(salary_slips_deduction_table.c.salarySlipID)
        ).subquery()
        
        query = select(
            salary_slips_table.c.id,
            salary_slips_table.c.userID,
            salary_slips_table.c.month,
            salary_slips_table.c.year,
            salary_slips_table.c.taxCategory,
            salary_slips_table.c.position,
            salary_slips_table.c.department,
            salary_slips_table.c.basicSalary,
            (salary_slips_table.c.transportationAllowanceRate * salary_slips_table.c.transportationAllowanceQuantity).label("transportation"),
            (salary_slips_table.c.mealAllowanceRate * salary_slips_table.c.mealAllowanceQuantity).label("meal"),
            (salary_slips_table.c.overtimeRate * salary_slips_table.c.overtimeQuantity).label("overtime"),
            allowance_subq.c.allowance,
            deduction_subq.c.deduction,
            salary_slips_table.c.taxAmount,
            salary_slips_table.c.isDelete,
            salary_slips_table.c.isPaid,
            employees_table.c.name,
        ).join(
            employees_table, salary_slips_table.c.userID == employees_table.c.id
        ).outerjoin(
            allowance_subq, salary_slips_table.c.id == allowance_subq.c.salarySlipID
        ).outerjoin(
            deduction_subq, salary_slips_table.c.id == deduction_subq.c.salarySlipID
        ).where(
            employees_table.c.name.ilike(f"%{keyword}%")
        ).order_by(
            salary_slips_table.c.year.desc(), salary_slips_table.c.month.desc(), employees_table.c.name.asc()
        ).offset((page - 1) * pageSize).limit(pageSize)
        
        try:
            result = await database.fetch_all(query)
        
            countQuery = select(func.count()).select_from(
                salary_slips_table
            )
            
            count = await database.fetch_one(countQuery)

            for row in result:
                print(dict(row))
            
            return {
                "data": [dict(row) for row in result],
                "count": count[0] if count else 0,
            }
        except Exception as e:
            log_error(f"Error fetching salary slips: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_salary_slip_by_id(id: int):
        try:
            query = select(
                salary_slips_table.c.id,
                salary_slips_table.c.userID,
                salary_slips_table.c.month,
                salary_slips_table.c.year,
                salary_slips_table.c.taxCategory,
                salary_slips_table.c.position,
                salary_slips_table.c.department,
                salary_slips_table.c.basicSalary,
                salary_slips_table.c.transportationAllowanceRate,
                salary_slips_table.c.transportationAllowanceQuantity,
                salary_slips_table.c.mealAllowanceRate,
                salary_slips_table.c.mealAllowanceQuantity,
                salary_slips_table.c.overtimeRate,
                salary_slips_table.c.overtimeQuantity,
                salary_slips_table.c.taxAmount,
                salary_slips_table.c.isDelete,
                salary_slips_table.c.bankName,
                salary_slips_table.c.bankAccountName,
                salary_slips_table.c.bankAccountNumber,
                salary_slips_table.c.paymentMethod,
                employees_table.c.name,
            ).join(
                employees_table, salary_slips_table.c.userID == employees_table.c.id
            ).where(
                salary_slips_table.c.id == id
            )
            result = await database.fetch_one(query)
            result = dict(result)

            allowanceQuery = select(salary_slips_allowance_table).where(salary_slips_allowance_table.c.salarySlipID == id)
            allowances = await database.fetch_all(allowanceQuery)

            deductionQuery = select(salary_slips_deduction_table).where(salary_slips_deduction_table.c.salarySlipID == id)
            deductions = await database.fetch_all(deductionQuery)

            result['otherAllowances'] = allowances
            result['otherDeductions'] = deductions

            return result
        except Exception as e:
            log_error(f"Error fetching salary slips: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def deleteByID(id: int, userID: int):
        query = (
            update(salary_slips_table)
            .where(salary_slips_table.c.id == id)
            .values({
                "isDelete": True,
                "deletedBy": userID,
                'deletedAt': dt.now()
            })
        )

        result = await database.execute(query)
        if result == 0:  # Check if any rows were affected
            return {"error": "Update failed or salary slip not found", "status": 404}
        
        return {"message": "Salary slip updated successfully"}

    @staticmethod
    async def update_payment_status(id: int, isPaid: bool, userID: int):
        query = (
            update(salary_slips_table)
            .where(salary_slips_table.c.id == id)
            .values({
                "isPaid": isPaid,
                "updatedBy": userID,
                "updatedAt": dt.now()
            })
        )

        print(query)

        result = await database.execute(query)
        print(result)
        if result == 0:  # Check if any rows were affected
            return {"error": "Update failed or salary slip not found", "status": 404}
        
        return {"message": "Salary slip updated successfully"}

    @staticmethod
    async def get_pph_report(month: int, year: int):
        query = select(
            salary_slips_table.c.id,
            salary_slips_table.c.userID,
            salary_slips_table.c.month,
            salary_slips_table.c.year,
            salary_slips_table.c.taxCategory,
            salary_slips_table.c.position,
            salary_slips_table.c.department,
            salary_slips_table.c.basicSalary,
            salary_slips_table.c.transportationAllowanceRate, 
            salary_slips_table.c.transportationAllowanceQuantity,
            salary_slips_table.c.mealAllowanceRate, 
            salary_slips_table.c.mealAllowanceQuantity,
            salary_slips_table.c.overtimeRate, 
            salary_slips_table.c.overtimeQuantity,
            salary_slips_table.c.taxAmount,
            salary_slips_table.c.isDelete,
            salary_slips_table.c.isPaid,
            employees_table.c.name,
            employees_table.c.nik,
        ).join(
            employees_table, salary_slips_table.c.userID == employees_table.c.id
        ).where(
            salary_slips_table.c.month == month, salary_slips_table.c.year == year, salary_slips_table.c.isDelete == False 
        ).order_by(
           employees_table.c.name.asc()
        )
        
        allowance_query = (
            select(*salary_slips_allowance_table.c)
            .join(
                salary_slips_table, salary_slips_table.c.id == salary_slips_allowance_table.c.salarySlipID
            )
            .where(
                salary_slips_table.c.month == month, salary_slips_table.c.year == year
            )
        )

        deduction_query = (
            select(*salary_slips_deduction_table.c)
            .join(
                salary_slips_table, salary_slips_table.c.id == salary_slips_deduction_table.c.salarySlipID
            )
            .where(
                salary_slips_table.c.month == month, salary_slips_table.c.year == year
            )
        )
        try:
            result = await database.fetch_all(query)
            allowances = await database.fetch_all(allowance_query)
            deductions = await database.fetch_all(deduction_query)
            
            
            # Convert to list of dicts for easier manipulation
            result_data = [dict(row) for row in result]
            allowances_data = [dict(a) for a in allowances]
            deductions_data = [dict(d) for d in deductions]

            from collections import defaultdict
            
            allowance_map = defaultdict(list)
            for a in allowances_data:
                allowance_map[a['salarySlipID']].append(a)

            deduction_map = defaultdict(list)
            for d in deductions_data:
                deduction_map[d['salarySlipID']].append(d)

            # Attach to each row
            for row in result_data:
                row_id = row['id']
                row['allowances'] = allowance_map.get(row_id, [])
                row['deductions'] = deduction_map.get(row_id, [])

            return {
                "data": result_data,
            }

        except Exception as e:
            log_error(f"Error fetching salary slips: {str(e)}")
            return {"error": str(e), "status": 500}

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
    Column("userID", Integer, ForeignKey("employee.id"), nullable=False),
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
    Column("bankName", String(100), nullable=False),
    Column("bankAccountName", String(100), nullable=False),
    Column("bankAccountNumber", String(100), nullable=False),
    Column("paymentMethod", String(100), nullable=False),
    Column("createdAt", DateTime, default=dt.utcnow, nullable=False),
    Column("updatedAt", DateTime, default=dt.utcnow, onupdate=dt.utcnow, nullable=True),
    Column("createdBy", Integer, nullable=False),
    Column("updatedBy", Integer, nullable=True),
    Column("isDelete", Boolean, default=False, nullable=False),
    Column("deletedAt", DateTime, nullable=True),
    Column("deletedBy", Integer, nullable=True),
    Column("position", String(50), nullable=False),
    Column("department", String(50), nullable=False),
    
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
                "name": allowance['name'],
                "description": allowance['description'],
                "amount": allowance['amount']
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
                "name": deduction['name'],
                "description": deduction['description'],
                "amount": deduction['amount']
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