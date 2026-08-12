from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from controllers.loan_controller import LoanController
from schemas.loan_schema import LoanCreate, LoanUpdate, CreateLoanResponse, UpdateLoanResponse, LoanListResponse, LoanPaymentsResponse
from utils.auth_utils import get_current_user, User
from utils.permission import require

router = APIRouter()

@router.post("/", response_model=CreateLoanResponse)
async def create_loan(loan_data: LoanCreate, current_user: Annotated[User, Depends(require("loan", "create"))]):
    """Create a new loan."""
    try:
        user_id = current_user["id"]
        result = await LoanController.create_loan(loan_data.dict(), user_id)
        return result
    except HTTPException as e:
        raise e

@router.put("/{loan_id}", response_model=UpdateLoanResponse)
async def update_loan(
    loan_id: int,
    loan_data: LoanUpdate,
    current_user: Annotated[User, Depends(require("loan", "update"))],
):
    """
    Perbarui data pinjaman.

    Terbatas pada data kreditur dan rekening; nilai pinjaman serta sisa utang
    tidak dapat diubah karena sudah menjadi dasar pencatatan pembayaran.
    """
    try:
        return await LoanController.update_loan(
            loan_id, loan_data.dict(exclude_unset=True), current_user["id"]
        )
    except HTTPException as e:
        raise e


@router.get("/payments/{loan_id}", response_model=LoanPaymentsResponse)
async def get_loan_payments(loan_id: int, current_user: Annotated[User, Depends(require("loan", "read"))]):
    """Get loan details with its payments."""
    try:
        user_id = current_user["id"]
        loan = await LoanController.get_loan_by_id(loan_id)

        # Pinjaman yang tidak ada dijawab dengan galat, bukan objek kosong.
        #
        # Objek kosong tetap dianggap berhasil oleh layar, sehingga yang
        # tampil adalah halaman berisi "NaN%" dan nilai kosong — pengguna
        # melihat tampilan rusak, bukan keterangan bahwa datanya tidak ada.
        if not loan:
            raise HTTPException(status_code=404, detail="Pinjaman tidak ditemukan")

        payments = await LoanController.get_payments_by_loan_id(loan_id)

        return {
            "loan": dict(loan),
            "payments": payments or [],
        }
    except HTTPException as e:
        raise e

@router.get("/", response_model=LoanListResponse)
async def get_loans(
    page: int, 
    pageSize: int, 
    isPaid: bool, 
    isUnpaid: bool, 
    sortBy: str, 
    current_user: Annotated[User, Depends(require("loan", "read"))],
    sortByDirection: str, 
    keyword: str | None = None, 
):
    """Get paginated list of loans with filtering and sorting."""
    try:
        user_id = current_user["id"]
        result = await LoanController.get_loans(page, pageSize, isPaid, isUnpaid, sortBy, sortByDirection, keyword)
        return result
    except HTTPException as e:
        raise e