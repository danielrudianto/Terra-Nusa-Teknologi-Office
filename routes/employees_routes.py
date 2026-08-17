from typing import Annotated, Optional
from utils.errors import error_detail
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from utils.logger_utils import log_error, log_info
from utils.auth_utils import get_current_user
from utils.permission import require
from models.employee_model import Employee
from controllers.employee_controller import EmployeeController
from utils.auth_utils import User

router = APIRouter()

@router.post("/")
async def create_employee(employee: Employee, user: Annotated[dict, Depends(require("employees", "create"))]):
    """
    Create a new payment. Requires a valid token.
    """
    userID = user["id"]
    result = await EmployeeController.create_employee(employee.model_dump(), userID)
    
    if "error" in result:
        log_error(f"Error creating payment: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result


@router.get("/pilihan-pic")
async def pilihan_pic(
    current_user: Annotated[
        User, Depends(require("purchase_order", "create"))
    ],
    keyword: Optional[str] = Query(None, description="Cari nama"),
):
    """
    Nama dan telepon karyawan AKTIF, untuk pemilih penanggung jawab pada
    purchase order.

    Dijaga `purchase_order:create`, BUKAN `employees:read` — dan itu
    disengaja. Modul `employees` termasuk `MODUL_WILAYAH_MUTLAK`: isinya
    susunan keluarga, riwayat kesehatan, dan gaji, yang hanya terbuka bagi
    HRD. Yang membuat purchase order tidak perlu melihat semua itu.

    Karena itu rute ini mengembalikan DUA KOLOM saja. Membuka `employees`
    untuk keperluan ini berarti membuka seluruh isinya kepada procurement.

    CATATAN URUTAN — jangan memindahkan ke bawah `/{employee_id}`.
    FastAPI mencocokkan rute berurutan dan menjalankan dependensinya sebelum
    memeriksa tipe jalurnya; "pilihan-pic" akan tertangkap sebagai id dan
    ditolak sebelum sempat diketahui bahwa ia bukan angka.
    """
    hasil = await EmployeeController.pilihan_pic(keyword)
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(
            status_code=hasil.get("status", 500), detail=error_detail(hasil)
        )
    return hasil


@router.get("/{employee_id}")
async def get_employee(employee_id: int, user: Annotated[dict, Depends(require("employees", "read"))]):
    """
    Get an employee by ID. Requires a valid token.
    """
    result = await EmployeeController.get_employee_by_id(employee_id)
    
    if "error" in result:
        log_error(f"Error fetching employee: {result['error']}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    
    return result

@router.get("/")
async def get_employees(
    request: Request,
    user: Annotated[dict, Depends(require("employees", "read"))]
):
    """
    Get a list of employees. Requires a valid token.
    """
    keyword = request.query_params.get("keyword")
    page = int(request.query_params.get("page", 1))
    pageSize = int(request.query_params.get("pageSize", 10))
    sortBy = request.query_params.get("sortBy")
    sortByDirection = request.query_params.get("sortByDirection")
    status = request.query_params.get("status")

    try:
        result = await EmployeeController.get_employees(keyword, page, pageSize, sortBy, sortByDirection, status)
        if "error" in result:
            raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e
    
@router.put("/")
async def update_employee(employee: Employee, user: Annotated[dict, Depends(require("employees", "update"))]):
    """
    Update an existing employee. Requires a valid token.
    """
    userID = user["id"]
    result = await EmployeeController.update_employee(employee.model_dump(), userID)
    
    if "error" in result:
        log_error(f"Error updating employee: {result['error']}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    
    return result