"""
TAUTAN PEMBELIAN LAMA KE CoP — ALAT SEMENTARA.

Dipakai saat merapikan data historis: pembelian yang sudah terbit sebelum
jalur CoP ada dihubungkan ke CoP-nya, alih-alih dihapus lalu dibuat ulang.

DIBUAT UNTUK DICOPOT. Seluruh isinya ada di berkas ini, rutenya di
`routes/tautan_pembelian_routes.py`, dan layarnya satu dialog tersendiri.
Menghapus fitur = hapus dua berkas itu, satu baris `include_router`, dan satu
tombol di layar CoP. TIDAK ada kolom baru, TIDAK ada tabel baru, dan
—atas permintaan pemilik— TIDAK ada pencatatan audit.

Yang tertinggal setelah dicopot: nilai `purchases.certificateOfPaymentID`
yang sudah telanjur diisi. Itu memang tujuannya, dan kolom itu kolom yang
sama yang diisi pembelian yang dibuat dari CoP — jadi datanya tidak dapat
dibedakan dari yang dibuat lewat jalur biasa, dan tidak ada yang perlu
dibersihkan.
"""

from typing import Any, Dict, List

from utils.database import database
from utils.logger_utils import log_error


class TautanPembelianRepository:
    @staticmethod
    async def calon(cop_id: int, supplier_id: int, kata: str = "", batas: int = 20) -> List[Dict[str, Any]]:
        """
        Pembelian yang MASIH BOLEH ditautkan ke CoP ini.

        Tiga syarat: pemasoknya sama, belum tertaut ke CoP mana pun, dan
        belum dihapus. Pemasok disyaratkan karena tautan ini menentukan
        tagihan siapa yang dianggap lunas oleh CoP — menautkan pembelian
        pemasok lain berarti menyatakan orang yang salah sudah ditagih.
        """
        try:
            syarat = [
                "p.isDelete = 0",
                "p.supplierID = :pemasok",
                "p.certificateOfPaymentID IS NULL",
            ]
            params: Dict[str, Any] = {
                "pemasok": int(supplier_id),
                "limit": max(1, min(int(batas), 50)),
            }
            if kata:
                syarat.append(
                    "(p.invoiceName LIKE :kata OR p.purchaseOrderName LIKE :kata"
                    " OR p.projectName LIKE :kata)"
                )
                params["kata"] = f"%{kata}%"
            return [
                dict(b)
                for b in await database.fetch_all(
                    "SELECT p.id, p.invoiceName, p.date, p.dpp, p.projectName, "
                    "       p.purchaseOrderName, p.lastStatus, p.isPaid "
                    "FROM purchases p WHERE " + " AND ".join(syarat) + " "
                    "ORDER BY p.date DESC, p.id DESC LIMIT :limit",
                    params,
                )
            ]
        except Exception as e:  # noqa: BLE001
            log_error(f"Gagal membaca calon tautan pembelian: {e}")
            return []

    @staticmethod
    async def pemasok_cop(cop: Dict[str, Any]) -> int | None:
        """
        Id pemasok CoP ini.

        `certificate_of_payments.supplierID` BOLEH KOSONG pada baris lama
        yang belum ikut backfill — dan baris lama itu justru yang sedang
        dirapikan dengan fitur ini. Kalau kosong, dibaca dari SPK-nya.
        """
        nilai = cop.get("supplierID")
        if nilai:
            return int(nilai)
        baris = await database.fetch_one(
            "SELECT supplierID FROM purchase_orders WHERE id = :id",
            {"id": int(cop["purchaseOrderID"])},
        )
        return int(baris["supplierID"]) if baris and baris["supplierID"] else None

    @staticmethod
    async def pembelian(purchase_id: int) -> Dict[str, Any] | None:
        baris = await database.fetch_one(
            "SELECT id, invoiceName, supplierID, dpp, certificateOfPaymentID, "
            "       isDelete FROM purchases WHERE id = :id",
            {"id": int(purchase_id)},
        )
        return dict(baris) if baris else None

    @staticmethod
    async def tautkan(purchase_id: int, cop_id: int) -> int:
        """
        Pasang tautannya.

        Syarat `certificateOfPaymentID IS NULL` ikut di dalam WHERE, bukan
        hanya diperiksa lebih dahulu: dua orang yang menautkan pembelian yang
        sama pada saat bersamaan tidak boleh sama-sama berhasil.
        """
        return await database.execute(
            "UPDATE purchases SET certificateOfPaymentID = :cop "
            "WHERE id = :id AND isDelete = 0 AND certificateOfPaymentID IS NULL",
            {"cop": int(cop_id), "id": int(purchase_id)},
        )

    @staticmethod
    async def lepas(purchase_id: int, cop_id: int) -> int:
        """Lepas tautan — hanya bila pembelian itu memang tertaut ke CoP ini."""
        return await database.execute(
            "UPDATE purchases SET certificateOfPaymentID = NULL "
            "WHERE id = :id AND isDelete = 0 AND certificateOfPaymentID = :cop",
            {"cop": int(cop_id), "id": int(purchase_id)},
        )


class TautanPembelianController:
    """
    Aturan penautan. Ditaruh sekelas berkas dengan repositorinya, sekali lagi
    karena seluruh fitur ini memang disusun untuk dihapus dalam satu langkah.
    """

    @staticmethod
    async def calon(cop_id: int, kata: str = "") -> Dict[str, Any]:
        from controllers.certificate_of_payment_controller import (
            CertificateOfPaymentController,
        )
        from repository.certificate_of_payment_repository import (
            CertificateOfPaymentRepository,
        )

        cop = await CertificateOfPaymentRepository.get_by_id(cop_id)
        if cop is None:
            return {"error": "Certificate of payment tidak ditemukan.", "status": 404}
        if isinstance(cop, dict) and "error" in cop:
            return cop

        # Syarat yang sama dengan membuat pembelian dari CoP: sudah disetujui
        # dan belum ditagihkan. Dipanggil, bukan disalin.
        galat = await CertificateOfPaymentController.periksa_boleh_ditagih(cop_id)
        if galat:
            return galat

        pemasok = await TautanPembelianRepository.pemasok_cop(cop)
        if not pemasok:
            return {
                "error": "CoP ini tidak menyebut pemasok, jadi calon tautannya tidak dapat dicari.",
                "status": 409,
            }
        return {
            "nilaiBersih": float(cop.get("netAmount") or 0),
            "data": await TautanPembelianRepository.calon(cop_id, pemasok, kata),
        }

    @staticmethod
    async def tautkan(cop_id: int, purchase_id: int) -> Dict[str, Any]:
        from controllers.certificate_of_payment_controller import (
            CertificateOfPaymentController,
        )
        from repository.certificate_of_payment_repository import (
            CertificateOfPaymentRepository,
        )

        cop = await CertificateOfPaymentRepository.get_by_id(cop_id)
        if cop is None:
            return {"error": "Certificate of payment tidak ditemukan.", "status": 404}
        if isinstance(cop, dict) and "error" in cop:
            return cop

        galat = await CertificateOfPaymentController.periksa_boleh_ditagih(cop_id)
        if galat:
            return galat

        beli = await TautanPembelianRepository.pembelian(purchase_id)
        if beli is None or beli["isDelete"]:
            return {"error": "Pembelian tidak ditemukan.", "status": 404}
        if beli["certificateOfPaymentID"]:
            return {
                "error": (
                    "Pembelian ini sudah tertaut ke certificate of payment "
                    "lain. Lepas tautannya lebih dahulu."
                ),
                "status": 409,
            }
        pemasok = await TautanPembelianRepository.pemasok_cop(cop)
        if not pemasok or int(beli["supplierID"]) != pemasok:
            return {
                "error": (
                    "Pemasok pembelian berbeda dengan pemasok CoP, jadi "
                    "tidak dapat ditautkan."
                ),
                "status": 409,
            }

        if not await TautanPembelianRepository.tautkan(purchase_id, cop_id):
            # Kalah cepat dari permintaan lain yang menautkan pembelian ini.
            return {
                "error": "Pembelian ini baru saja tertaut ke CoP lain.",
                "status": 409,
            }

        # SELISIH DILAPORKAN, TIDAK MENOLAK. Data historis memang kerap tidak
        # bulat; yang menautkan melihat angkanya sebelum menekan tombol.
        return {
            "tertaut": True,
            "selisih": round(
                float(beli["dpp"] or 0) - float(cop.get("netAmount") or 0), 2
            ),
        }

    @staticmethod
    async def lepas(cop_id: int, purchase_id: int) -> Dict[str, Any]:
        if not await TautanPembelianRepository.lepas(purchase_id, cop_id):
            return {
                "error": (
                    "Pembelian itu tidak tertaut ke certificate of payment ini."
                ),
                "status": 409,
            }
        return {"terlepas": True}
