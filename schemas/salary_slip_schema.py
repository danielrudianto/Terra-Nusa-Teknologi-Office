from pydantic import BaseModel
from datetime import datetime as dt
from typing import Optional, List

class SalarySlipBase(BaseModel):
    userID: int
    month: int
    year: int
    isPaid: bool = False
    basicSalary: float
    transportationAllowanceQuantity: float = 0.0
    transportationAllowanceRate: float = 0.0
    mealAllowanceQuantity: float = 0.0
    mealAllowanceRate: float = 0.0
    overtimeQuantity: float = 0.0
    overtimeRate: float = 0.0
    taxAmount: float = 0.0
    bankName: str
    bankAccountName: str
    bankAccountNumber: str
    paymentMethod: str
    taxCategory: str
    position: str
    department: str

class SalarySlipCreate(SalarySlipBase):
    pass

class SalarySlipUpdate(BaseModel):
    isPaid: Optional[bool] = None
    updatedBy: Optional[int] = None

class SalarySlipResponse(SalarySlipBase):
    id: int
    createdAt: dt
    updatedAt: Optional[dt] = None
    createdBy: Optional[int] = None
    updatedBy: Optional[int] = None
    isDelete: bool = False
    deletedAt: Optional[dt] = None
    deletedBy: Optional[int] = None
    name: Optional[str] = None

    class Config:
        from_attributes = True

class SalarySlipCheck(BaseModel):
    userID: int
    month: int
    year: int

class SalarySlipAllowanceBase(BaseModel):
    name: str
    description: str
    amount: float

class SalarySlipAllowanceCreate(SalarySlipAllowanceBase):
    salarySlipID: int

class SalarySlipAllowanceResponse(SalarySlipAllowanceBase):
    id: int
    salarySlipID: int

    class Config:
        from_attributes = True

class SalarySlipDeductionBase(BaseModel):
    name: str
    description: str
    amount: float

class SalarySlipDeductionCreate(SalarySlipDeductionBase):
    salarySlipID: int

class SalarySlipDeductionResponse(SalarySlipDeductionBase):
    id: int
    salarySlipID: int

    class Config:
        from_attributes = True

class SalarySlipDetailResponse(SalarySlipResponse):
    otherAllowances: List[SalarySlipAllowanceResponse] = []
    otherDeductions: List[SalarySlipDeductionResponse] = []

class SalarySlipListResponse(BaseModel):
    data: List[SalarySlipResponse]
    count: int