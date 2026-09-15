"""
Arus kas proyek — perakitan jawabannya.

SUMBER YANG KOSONG BUKAN GALAT.

Aturan yang sama sudah ditegakkan pada laporan pembelian proyek, dan
alasannya dicatat panjang di sana: proyek KBPDP punya penjualan Rp 240 juta
dan belum punya pembelian sama sekali, lalu seluruh laporannya gugur menjadi
spanduk merah "No purchases found" — termasuk angka penjualannya, satu-satunya
angka yang ada.

Di sini keadaan itu bahkan lebih biasa. Proyek yang baru berjalan hampir
selalu punya kas keluar tanpa satu pun kas masuk; proyek dengan uang muka
punya kebalikannya. Keduanya normal, dan keduanya harus tergambar.

Yang benar-benar galat — sambungan putus, kueri gagal — tetap dilemparkan.
Menampilkannya sebagai daftar kosong berarti melaporkan proyek yang tidak
punya arus kas, dan itu tidak dapat dibedakan dari proyek yang memang belum
bergerak.
"""

from typing import Any, Dict

from repository.project_cashflow_repository import ProjectCashflowRepository
from utils.logger_utils import log_error


def _gagal(hasil: Any) -> bool:
    """Repository mengembalikan dict bergalat, bukan melempar."""
    return isinstance(hasil, dict) and "error" in hasil


class ProjectCashflowController:
    @staticmethod
    async def arus_kas(project_name: str) -> Dict[str, Any]:
        if not project_name or not project_name.strip():
            return {"error": "Project name is required", "status": 400}

        keluar = await ProjectCashflowRepository.kas_keluar(project_name)
        if _gagal(keluar):
            log_error(f"Project cashflow: outflow failed for {project_name}")
            return keluar

        masuk = await ProjectCashflowRepository.kas_masuk(project_name)
        if _gagal(masuk):
            log_error(f"Project cashflow: inflow failed for {project_name}")
            return masuk

        return {
            "outgoing": keluar,
            "incoming": masuk,
            # Disebutkan di JAWABANNYA, bukan hanya di layar.
            #
            # `expenses` dan `salary_slips` tidak punya kolom proyek, jadi kas
            # keluar di sini adalah batas bawah. Menaruh keterangan itu di
            # template saja berarti pemakai berikutnya — berkas unduhan, layar
            # lain, integrasi — mewarisi angkanya tanpa mewarisi batasannya.
            "cakupanKeluar": ["pembelian", "reimbursement"],
        }
