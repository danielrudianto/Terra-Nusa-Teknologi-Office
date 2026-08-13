import asyncio
from typing import Any, Dict

from repository.finance_status_repository import FinanceStatusRepository
from utils.logger_utils import log_error


class FinanceStatusController:
    @staticmethod
    async def get_status() -> Dict[str, Any]:
        """
        Posisi keuangan hari ini.

        Keempat sumber diambil bersamaan; tidak ada yang bergantung pada
        hasil yang lain.
        """
        try:
            kas, piutang, utang, pinjaman = await asyncio.gather(
                FinanceStatusRepository.total_kas(),
                FinanceStatusRepository.piutang(),
                FinanceStatusRepository.utang_usaha(),
                FinanceStatusRepository.pinjaman(),
            )

            total_piutang = float(piutang.get("total") or 0)
            total_utang = float(utang.get("total") or 0)
            total_pinjaman = float(pinjaman.get("total") or 0)

            """
            Quick ratio = (kas + piutang usaha) / utang usaha.

            Persediaan tidak dikurangkan karena memang tidak ada: master item
            hanya katalog, tanpa kuantitas maupun nilai stok. Untuk perusahaan
            ini quick ratio dan current ratio menghasilkan angka yang sama,
            dan itu justru membuat angkanya tidak mengandung penilaian
            tentang seberapa cepat stok dapat dicairkan.

            Pinjaman TIDAK masuk penyebut. `loans` tidak menyimpan tenor
            maupun jadwal angsuran, sehingga porsi yang jatuh tempo dalam
            setahun tidak dapat dipisahkan dari yang jangka panjang. Menebak
            pemisahannya menghasilkan rasio yang tampak pasti padahal
            dasarnya karangan.

            Konsekuensinya disebutkan apa adanya: bila ada pinjaman yang
            jatuh tempo dalam waktu dekat, rasio ini lebih baik daripada
            keadaan sebenarnya. Karena itu saldo pinjaman dikembalikan juga
            dan ditampilkan di sisi rasionya.
            """
            if total_utang > 0:
                quick_ratio = (kas + total_piutang) / total_utang
            else:
                # Tanpa utang usaha, rasionya tak terhingga — bukan nol.
                # Mengembalikan 0 akan terbaca sebagai keadaan terburuk,
                # padahal justru sebaliknya.
                quick_ratio = None

            return {
                "kas": kas,
                "piutang": piutang,
                "utangUsaha": utang,
                "pinjaman": pinjaman,
                "quickRatio": quick_ratio,
                "modalKerjaBersih": kas + total_piutang - total_utang,
                # Dikirim agar layar tidak perlu menyusun ulang rumusnya dan
                # berisiko berbeda dari yang dihitung di sini.
                "rumus": "(kas + piutang usaha) / utang usaha",
                "catatan": {
                    "pinjamanDiluarRasio": total_pinjaman > 0,
                    "piutangDiumurkanDariTanggalFaktur": True,
                },
            }
        except Exception as e:
            log_error(f"Error menyusun posisi keuangan: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
