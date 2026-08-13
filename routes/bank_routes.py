from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from controllers.bank_controller import BankController
from repository.bank_account_repository import BankAccount
from utils.auth_utils import get_current_user
from utils.permission import require
from utils.auth_utils import User

router = APIRouter()

@router.post("/")
async def create_bank_account(bank:BankAccount, current_user: Annotated[User, Depends(require("bank", "create"))]):
    try:
        userID = current_user["id"]
        result = await BankController.create_bank_account(bank.model_dump(), userID)
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e  # Re-raise to return the HTTPException response
    
@router.get("/", dependencies=[Depends(require("bank", "read"))])
async def get_bank_accounts(request: Request, current_user: Annotated[User, Depends(require("bank", "read"))], sortBy: str = Query(None), sortByDirection: str = Query("asc")):
    # keyword = request.query_params.get("keyword")
    page = int(request.query_params.get("page", 1))
    try:
        result = await BankController.get_bank_accounts(
            page, sortBy, sortByDirection
        )
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e
    
@router.get("/all", dependencies=[Depends(require("bank", "read"))])
async def get_all_bank_accounts(current_user: Annotated[User, Depends(require("bank", "read"))]):
    try:
        result = await BankController.get_all_bank_accounts()
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e
    
@router.get("/{bank_id}", dependencies=[Depends(require("bank", "read"))])
async def get_bank_account(bank_id: int, current_user: Annotated[User, Depends(require("bank", "read"))]):
    try:
        result = await BankController.get_bank_account_by_id(bank_id)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e
    
@router.put("/{bank_id}")
async def update_bank_account(bank_id: int, bank: BankAccount, current_user: Annotated[User, Depends(require("bank", "update"))]):
    try:
        userID = current_user["id"]
        result = await BankController.update_bank_account(bank.model_dump(), bank_id, userID)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e

@router.delete("/{bank_id}")
async def delete_bank_account(bank_id: int, current_user: Annotated[User, Depends(require("bank", "delete"))]):
    try:
        userID = current_user["id"]
        result = await BankController.delete_bank_account(bank_id, userID)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e

@router.post("/mutation/download")
async def download_mutation_data(
    data: dict,
    # `read`, bukan `create`.
    #
    # Rutenya POST hanya karena parameternya (id rekening dan periode)
    # dikirim di body, bukan karena ada yang dibuat. Mengikuti kata kerja
    # HTTP-nya menutup mutasi bagi semua orang di bawah level 5 — padahal
    # justru bagian keuanganlah yang memakainya untuk mencocokkan rekening
    # koran.
    current_user: Annotated[User, Depends(require("bank", "read"))],
):
    try:
        bankAccountID = data["bankAccountID"]
        month = data["month"]
        year = data["year"]

        result = await BankController.download_mutation(bankAccountID, month, year)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e

@router.post("/mutation")
async def get_mutation_data(
    data: dict,
    # `read`: kueri ini hanya membaca. Lihat keterangan pada rute unduh.
    current_user: Annotated[User, Depends(require("bank", "read"))],
):
    try:
        bankAccountID = data["bankAccountID"]
        page=data["page"]
        pageSize=data['pageSize']
        startDate=data['startDate']
        endDate=data['endDate'] 
        result = await BankController.fetch_mutation(bankAccountID, page, pageSize, startDate, endDate)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        raise e