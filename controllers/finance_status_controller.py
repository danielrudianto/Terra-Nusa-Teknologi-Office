import asyncio
from typing import Any, Dict

from repository.finance_status_repository import FinanceStatusRepository
from utils.logger_utils import log_error


class FinanceStatusController:
    #: Sejauh apa ke belakang akurasi rencana boleh diminta, dalam bulan.
    #:
    #: Dua belas menutup satu tahun penuh sehingga pola musiman masih
    #: terlihat, dan menahan agar satu parameter di URL tidak dapat memaksa
    #: pemindaian seluruh riwayat.
    MAKS_MUNDUR = 12

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

            # `total_kas` kini mengembalikan RINCIAN, bukan satu angka:
            # yang dapat dipakai, dan yang dikecualikan (deposit jaminan).
            # Hanya yang dapat dipakai yang boleh masuk rumus.
            kas_dipakai = float(kas.get("total") or 0)
            kas_dikecualikan = float(kas.get("dikecualikan") or 0)

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
                quick_ratio = (kas_dipakai + total_piutang) / total_utang
            else:
                # Tanpa utang usaha, rasionya tak terhingga — bukan nol.
                # Mengembalikan 0 akan terbaca sebagai keadaan terburuk,
                # padahal justru sebaliknya.
                quick_ratio = None

            # ---- Likuiditas 30 hari ----
            #
            # KEWAJIBAN SAJA YANG DIKURANGKAN, bukan rencana kas.
            #
            # Godaannya menyusun satu angka "sisa kas akhir bulan" dari kas +
            # rencana masuk - rencana keluar - utang jatuh tempo. Itu
            # MENGHITUNG DUA KALI: sebuah rencana kas berjenis keluar kerap
            # dibuat untuk pembelian yang juga tercatat sebagai utang usaha,
            # dan tidak ada satu pun kolom yang menghubungkan keduanya
            # sehingga tumpangnya tidak dapat dikenali, apalagi dikurangkan.
            # Angka gabungan itu akan lebih pesimistis daripada keadaan
            # sebenarnya, dengan selisih yang tidak dapat dijelaskan kepada
            # siapa pun yang menanyakannya.
            #
            # Yang dipakai di sini hanya yang dapat ditelusuri ke dokumennya:
            # saldo rekening, dikurangi tagihan pemasok yang tenggatnya jatuh
            # dalam 30 hari — termasuk yang sudah lewat.
            #
            # PIUTANG TIDAK DITAMBAHKAN. `sales_invoices` tidak menyimpan
            # jatuh tempo, jadi tidak ada dasar untuk mengatakan sebuah faktur
            # akan tertagih dalam 30 hari. Ia tetap dikirim sebagai
            # KETERANGAN di sebelah angkanya, bukan sebagai suku penjumlahan.
            tempo = utang.get("tempo") or {}
            jatuh_tempo_lewat = float(tempo.get("lewat") or 0)
            jatuh_tempo_30 = jatuh_tempo_lewat + float(tempo.get("0-30") or 0)

            umur = piutang.get("umur") or {}
            piutang_muda = float(umur.get("0-30") or 0)

            likuiditas = {
                "kas": kas_dipakai,
                "kewajiban30": jatuh_tempo_30,
                "kewajibanLewat": jatuh_tempo_lewat,
                "setelahKewajiban": kas_dipakai - jatuh_tempo_30,
                # Keterangan, BUKAN suku. Lihat alasannya di atas.
                "piutangTermuda": piutang_muda,
            }

            return {
                "kas": kas,
                "kasDikecualikan": kas_dikecualikan,
                "likuiditas30": likuiditas,
                "piutang": piutang,
                "utangUsaha": utang,
                "pinjaman": pinjaman,
                "quickRatio": quick_ratio,
                "modalKerjaBersih": kas_dipakai + total_piutang - total_utang,
                # Dikirim agar layar tidak perlu menyusun ulang rumusnya dan
                # berisiko berbeda dari yang dihitung di sini.
                "rumus": "(kas + piutang usaha) / utang usaha",
                "catatan": {
                    "pinjamanDiluarRasio": total_pinjaman > 0,
                    "piutangDiumurkanDariTanggalFaktur": True,
                    # Layar harus dapat MENGATAKAN kenapa piutang tidak ikut
                    # ditambahkan pada likuiditas 30 hari. Batasan yang hanya
                    # ditulis di komentar kode tidak pernah sampai ke yang
                    # membaca angkanya.
                    "piutangTanpaJatuhTempo": True,
                    "rencanaKasTidakDijumlahkan": True,
                    "kasTanpaRekeningDikecualikan": kas_dikecualikan > 0,
                },
            }
        except Exception as e:
            log_error(f"Error menyusun posisi keuangan: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def akurasi_rencana(mundur: int = 5) -> Dict[str, Any]:
        """
        Rencana kas dibanding yang benar-benar terjadi.

        Jalan keluar TERSENDIRI, bukan bidang tambahan pada `get_status`.
        Keduanya menjawab pertanyaan yang berbeda dan dibaca pada saat yang
        berbeda; menggabungkannya berarti setiap pembukaan halaman posisi
        keuangan ikut membayar empat kueri agregasi enam bulan — dan sebuah
        kegagalan di sana akan menjatuhkan seluruh halamannya, termasuk angka
        kas yang tidak ada hubungannya.
        """
        try:
            # Dibatasi di sini, sekali. `?mundur=999` akan memindai seluruh
            # riwayat dan membuat layarnya diam tanpa pesan apa pun.
            mundur = max(0, min(int(mundur), FinanceStatusController.MAKS_MUNDUR))
            return await FinanceStatusRepository.akurasi_rencana(mundur)
        except Exception as e:
            log_error(f"Error menyusun akurasi rencana: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
