from pydantic import BaseModel, Field
from typing import Optional, Annotated
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey, or_, select, func, insert, update
from utils.database import metadata
from datetime import datetime as d
from utils.logger_utils import log_error, log_info
from models.supplier_model import suppliers_table
from utils.database import database
from utils.errors import internal_error

# Define the Purchase model
class PurchaseDraft(BaseModel):
    id: int | None = None
    supplierID: int  # ID of the supplier
    date: d  # Date of the purchase
    purchaseOrderName: str  # Name of the purchase order
    projectName: str  # Name of the project
    purchaseType: str
    dpp: Annotated[float, Field(ge=0)]  # DPP value (greater than or equal to 0)
    ppn: Annotated[float, Field(ge=0)]  # PPN value (optional)
    pbbkb: Annotated[float, Field(ge=0)]  # PBBKB value (optional)
    description: str | None = None

    @staticmethod
    async def create_purchase_draft(purchase_data: dict):
        """
        Create a new purchase in the database.
        """
        try:
            query = insert(purchase_draft_table).values(**purchase_data)
            purchase_id = await database.execute(query)
            return purchase_id
        except Exception as e:
            log_error(f"Error creating purchase: {str(e)}")
            return internal_error()
        
    @staticmethod
    async def delete_purcase_draft(purchase_data_id: int, userID: int):
        try:
            query = purchase_draft_table.update().where(purchase_draft_table.c.id == purchase_data_id).values(isDelete = True, deletedBy = userID, deletedAt = d.now())
            await database.execute(query)
            return True
        except Exception as e:
            log_error(f"Error deleting purchase: {str(e)}")
            return internal_error()
    
    @staticmethod
    async def get_purchase_draft(page: int, pageSize: int, isPending: bool, isApproved: bool,sortBy: str, sortByDirection: str, keyword: str):
        offset = (page - 1) * pageSize
        supplier_columns = [
            suppliers_table.c.id.label("supplier_id"),
            suppliers_table.c.name.label("supplier_name"),
            suppliers_table.c.address.label("supplier_address"),
            suppliers_table.c.city.label("supplier_city"),
            suppliers_table.c.province.label("supplier_province"),
            suppliers_table.c.prefix.label("supplier_prefix"),
        ]

        conditions = []

        or_conditions = []
        if(keyword is not None and keyword != ""):
            or_conditions.append(purchase_draft_table.c.purchaseOrderName.ilike(f"%{keyword}%"))
            or_conditions.append(suppliers_table.c.name.ilike(f"%{keyword}%"))
            or_conditions.append(purchase_draft_table.c.description.ilike(f"%{keyword}%"))
        conditions.append(or_(*or_conditions))

        status_conditions = []
        if isPending:
            or_conditions.append(purchase_draft_table.c.isDelete == False)

        if isApproved:
            or_conditions.append(purchase_draft_table.c.isDelete == True)

        conditions.append(or_(*or_conditions))
        conditions.append(or_(*status_conditions))

        # Draft yang sudah menjadi pembelian tidak lagi menunggu apa pun,
        # jadi tidak ditampilkan di daftar tertunda. Tanpa ini, draft yang
        # sudah dikonversi tetap duduk di daftar dan mengundang konversi
        # kedua — yang kini ditolak server, tetapi tetap membingungkan.
        #
        # Ditambahkan sebagai syarat AND tersendiri, bukan disisipkan ke
        # rangkaian OR di atas, agar tidak ikut melonggarkan penyaring lain.
        if isPending:
            conditions.append(purchase_draft_table.c.convertedAt.is_(None))

        # Sort by, using switch case
        if sortBy == "date":
            order_by = purchase_draft_table.c.date.desc() if sortByDirection == "desc" else purchase_draft_table.c.date
        elif sortBy == "purchaseOrderName":
            order_by = purchase_draft_table.c.purchaseOrderName.desc() if sortByDirection == "desc" else purchase_draft_table.c.purchaseOrderName
        elif sortBy == "total":
            order_by = (purchase_draft_table.c.ppn + purchase_draft_table.c.dpp).desc() if sortByDirection == "desc" else (purchase_draft_table.c.ppn + purchase_draft_table.c.dpp)
        elif sortBy == "supplier":
            order_by = suppliers_table.c.name.desc() if sortByDirection == "desc" else suppliers_table.c.name.asc()
        elif sortBy == "project":
            order_by = purchase_draft_table.c.projectName.desc() if sortByDirection == "desc" else purchase_draft_table.c.projectName.asc()
        else:
            order_by = purchase_draft_table.c.date.desc()
            
        
        try:
            query = (
                select(*purchase_draft_table.c, *supplier_columns)
                .join(suppliers_table, purchase_draft_table.c.supplierID == suppliers_table.c.id)
                .where(*conditions)
                .order_by(order_by)
                .offset(offset)
                .limit(pageSize)
            )
            purchases = await database.fetch_all(query)

            #Count the total number of purchases
            count_query = (
                    select(func.count())
                .select_from(purchase_draft_table.join(suppliers_table, purchase_draft_table.c.supplierID == suppliers_table.c.id))
                .where(*conditions)
            )
            count = await database.fetch_val(count_query)

            #Convert the result
            purchase_result = []
            for purchase in purchases:
                purchase_dict = dict(purchase)
                purchase_dict["id"] = purchase_dict.pop("id")
                purchase_dict["createdAt"] = purchase_dict.pop("createdAt")
                purchase_dict["deletedAt"] = purchase_dict.pop("deletedAt")
                purchase_dict["createdBy"] = purchase_dict.pop("createdBy")
                purchase_dict["supplierID"] = purchase_dict.pop("supplierID")
                purchase_dict["supplier"] = {
                    "id": purchase_dict.pop("supplier_id"),
                    "name": purchase_dict.pop("supplier_name"),
                    "address": purchase_dict.pop("supplier_address"),
                    "city": purchase_dict.pop("supplier_city"),
                    "province": purchase_dict.pop("supplier_province"),
                    "prefix": purchase_dict.pop("supplier_prefix"),
                }
                purchase_result.append(purchase_dict)
            
            return {"data": purchase_result, "count": count}
        except Exception as e:
            log_error(f"Error fetching purchases: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_by_project(projectName: str):
        supplier_columns = [
            suppliers_table.c.id.label("supplier_id"),
            suppliers_table.c.name.label("supplier_name"),
            suppliers_table.c.address.label("supplier_address"),
            suppliers_table.c.city.label("supplier_city"),
            suppliers_table.c.province.label("supplier_province"),
            suppliers_table.c.prefix.label("supplier_prefix"),
        ]

        query = (
            select(*purchase_draft_table.c, *supplier_columns)
            .join(suppliers_table, purchase_draft_table.c.supplierID == suppliers_table.c.id)
            .where(purchase_draft_table.c.projectName == projectName, purchase_draft_table.c.isDelete == False)
        )
        purchases = await database.fetch_all(query)
        purchase_result = []
        for purchase in purchases:
            purchase_dict = dict(purchase)
            purchase_dict["id"] = purchase_dict.pop("id")
            purchase_dict["createdAt"] = purchase_dict.pop("createdAt")
            purchase_dict["deletedAt"] = purchase_dict.pop("deletedAt")
            purchase_dict["createdBy"] = purchase_dict.pop("createdBy")
            purchase_dict["supplierID"] = purchase_dict.pop("supplierID")
            purchase_dict["supplier"] = {
                "id": purchase_dict.pop("supplier_id"),
                "name": purchase_dict.pop("supplier_name"),
                "address": purchase_dict.pop("supplier_address"),
                "city": purchase_dict.pop("supplier_city"),
                "province": purchase_dict.pop("supplier_province"),
                "prefix": purchase_dict.pop("supplier_prefix"),
            }
            purchase_result.append(purchase_dict)
            
        return purchase_result

    @staticmethod
    async def get_purchase_draft_by_id(id: int):
        supplier_columns = [
            suppliers_table.c.id.label("supplier_id"),
            suppliers_table.c.name.label("supplier_name"),
            suppliers_table.c.address.label("supplier_address"),
            suppliers_table.c.city.label("supplier_city"),
            suppliers_table.c.province.label("supplier_province"),
            suppliers_table.c.prefix.label("supplier_prefix"),
        ]

        query = (
            select(*purchase_draft_table.c, *supplier_columns)
            .join(suppliers_table, purchase_draft_table.c.supplierID == suppliers_table.c.id)
            .where(purchase_draft_table.c.id == id)
        )

        purchases = await database.fetch_one(query)
        return purchases

    @staticmethod
    async def tandai_terkonversi(draft_id: int, purchase_id: int, user_id: int):
        """
        Tandai draft sudah menjadi pembelian.

        Penandaannya BERSYARAT: hanya mengenai baris yang belum terkonversi
        dan belum dihapus. Bila dua permintaan tiba bersamaan, hanya satu
        yang mengubah baris — yang kedua mendapat 0 dan konversinya ditolak.
        Memeriksa lebih dulu lalu menulis belakangan tidak cukup, karena di
        antara keduanya masih ada celah.
        """
        nilai = {"convertedAt": d.now(), "convertedBy": user_id}
        if purchase_id is not None:
            nilai["purchaseID"] = purchase_id

        return await database.execute(
            update(purchase_draft_table)
            .where(
                purchase_draft_table.c.id == draft_id,
                purchase_draft_table.c.isDelete == False,  # noqa: E712
                purchase_draft_table.c.convertedAt.is_(None),
            )
            .values(**nilai)
        )

    @staticmethod
    async def catat_purchase_id(draft_id: int, purchase_id: int):
        """Lengkapi tautan ke pembelian setelah nomornya diketahui."""
        return await database.execute(
            update(purchase_draft_table)
            .where(purchase_draft_table.c.id == draft_id)
            .values(purchaseID=purchase_id)
        )

    @staticmethod
    async def batalkan_konversi(draft_id: int):
        """
        Cabut penandaan konversi.

        Dipakai bila pembelian gagal dibuat setelah draftnya ditandai —
        tanpa ini draft itu terkunci selamanya: tidak bisa dikonversi lagi,
        padahal pembeliannya tidak pernah jadi.
        """
        return await database.execute(
            update(purchase_draft_table)
            .where(purchase_draft_table.c.id == draft_id)
            .values(convertedAt=None, convertedBy=None, purchaseID=None)
        )

# Define the SQLAlchemy table
purchase_draft_table = Table(
    "purchase_draft",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("supplierID", Integer, ForeignKey("suppliers.id"), nullable=False),
    Column("description", String(100), nullable=False),
    Column("date", Date(), nullable=False),
    Column("purchaseOrderName", String(100), nullable=False),
    Column("projectName", String(100), nullable=False),
    Column("purchaseType", String(100), nullable=False),
    Column("dpp", Float(), nullable=False),
    Column("ppn", Float(), nullable=False),
    Column("pbbkb", Float(), nullable=False),
    Column("isDelete", Boolean(), nullable=False, default=False),
    Column("createdAt", DateTime(), nullable=False, default=d.now()),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
    #
    # Penanda draft yang sudah menjadi pembelian.
    #
    # Sebelum ini, konversi hanya membuat pembelian baru dan draftnya tetap
    # utuh di daftar tanpa tanda apa pun — sehingga draft yang sama bisa
    # dikonversi berkali-kali dan menghasilkan pembelian ganda. Kekeliruan
    # semacam itu baru ketahuan saat rekonsiliasi, ketika tagihan yang sama
    # sudah terhitung dua kali.
    #
    # Menyimpan `purchaseID` sekaligus membuat jejaknya dapat ditelusuri:
    # draft ini menjadi pembelian yang mana.
    Column("convertedAt", DateTime(), nullable=True, default=None),
    Column("convertedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("purchaseID", Integer, nullable=True, default=None),
)