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
            (
                kas,
                piutang,
                utang,
                pinjaman,
                lain,
                aset_tetap,
            ) = await asyncio.gather(
                FinanceStatusRepository.total_kas(),
                FinanceStatusRepository.piutang(),
                FinanceStatusRepository.utang_usaha(),
                FinanceStatusRepository.pinjaman(),
                FinanceStatusRepository.kewajiban_lain(),
                FinanceStatusRepository.nilai_buku_aset(),
            )

            # `total_kas` kini mengembalikan RINCIAN, bukan satu angka:
            # yang dapat dipakai, dan yang dikecualikan (deposit jaminan).
            # Hanya yang dapat dipakai yang boleh masuk rumus.
            kas_dipakai = float(kas.get("total") or 0)
            kas_dikecualikan = float(kas.get("dikecualikan") or 0)

            total_piutang = float(piutang.get("total") or 0)
            total_utang = float(utang.get("total") or 0)
            total_pinjaman = float(pinjaman.get("total") or 0)
            total_lain = float(lain.get("total") or 0)
            nilai_buku = float(aset_tetap.get("nilaiBuku") or 0)

            # ---- KEWAJIBAN LANCAR: pembelian DAN yang selama ini terlewat ----
            #
            # `payments_outgoing` dapat menunjuk lima jenis dokumen, dan empat
            # di antaranya kewajiban kepada pihak luar. Selama hanya pembelian
            # yang dihitung, gaji bulan berjalan yang belum cair tidak muncul
            # sebagai kewajiban sama sekali — dan rasio yang disusun di atasnya
            # tampak lebih baik daripada keadaannya.
            kewajiban_lancar = total_utang + total_lain

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
            if kewajiban_lancar > 0:
                quick_ratio = (kas_dipakai + total_piutang) / kewajiban_lancar
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

            # ---- NERACA RINGKAS & EKUITAS ----
            #
            # Ekuitas TIDAK tercatat di mana pun; ia DITURUNKAN, aset dikurangi
            # kewajiban. Itu sah, dan komponen besarnya memang ada: saldo
            # rekening, faktur yang belum tertagih, nilai buku aset tetap,
            # tagihan yang belum dibayar, dan sisa pinjaman.
            #
            # Tetapi ia PERKIRAAN, bukan angka pembukuan, dan celahnya disebut
            # satu per satu di `neracaCelah` supaya setiap turunannya — D/E,
            # ROE, dan SKN — dapat dibaca bersama batasnya. Yang belum masuk:
            # uang muka dari klien, utang pajak yang belum disetor, dan piutang
            # atau utang lain-lain yang tidak berdokumen di sistem ini.
            #
            # Satu lagi yang harus disebut: sebagian pembelian aset tercatat
            # sebagai beban langsung 5.1.1 alih-alih dikapitalisasi. Pada
            # dokumen seperti itu asetnya muncul di neraca ini SEKALIGUS sudah
            # membebani laba rugi.
            total_aset = kas_dipakai + total_piutang + nilai_buku
            total_kewajiban = kewajiban_lancar + total_pinjaman
            ekuitas = total_aset - total_kewajiban

            # Debt to equity. `None` bila ekuitasnya nol atau minus — bukan
            # nol dan bukan angka besar: pada ekuitas minus rasio ini tidak
            # bermakna, dan mencetak angkanya memberi kesan terukur pada
            # keadaan yang justru paling perlu dibicarakan orang.
            dte = (
                (total_kewajiban / ekuitas) if ekuitas > 0 else None
            )

            neraca = {
                "aset": {
                    "kas": kas_dipakai,
                    "piutang": total_piutang,
                    "asetTetap": nilai_buku,
                    "total": total_aset,
                },
                "kewajiban": {
                    "utangUsaha": total_utang,
                    "kewajibanLain": total_lain,
                    "pinjaman": total_pinjaman,
                    "total": total_kewajiban,
                },
                "ekuitas": ekuitas,
                "debtToEquity": dte,
                "asetTetapRincian": aset_tetap,
                # Disebut sebagai DAFTAR, bukan satu kalimat: yang membaca
                # angkanya perlu tahu persis apa yang tidak ada di dalamnya.
                "celah": [
                    "uangMukaKlien",
                    "utangPajakBelumDisetor",
                    "piutangUtangLainLain",
                    "pembelianAsetYangDibebankanLangsung",
                ],
            }

            return {
                "kas": kas,
                "kasDikecualikan": kas_dikecualikan,
                "kewajibanLain": lain,
                "kewajibanLancar": kewajiban_lancar,
                "neraca": neraca,
                "likuiditas30": likuiditas,
                "piutang": piutang,
                "utangUsaha": utang,
                "pinjaman": pinjaman,
                "quickRatio": quick_ratio,
                "modalKerjaBersih": (
                    kas_dipakai + total_piutang - kewajiban_lancar
                ),
                # Dikirim agar layar tidak perlu menyusun ulang rumusnya dan
                # berisiko berbeda dari yang dihitung di sini.
                "rumus": "(kas + piutang usaha) / kewajiban lancar",
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
                    # Rasio di atas kini memakai kewajiban LANCAR yang
                    # lengkap, bukan pembelian saja. Layar menyebutnya supaya
                    # siapa pun yang sempat mencatat angka lama tahu mengapa
                    # rasionya turun — dan tidak mengira ada yang rusak.
                    "kewajibanLengkapSejakVersiIni": True,
                    "ekuitasDiturunkanBukanDicatat": True,
                },
                # Selisih terhadap hitungan LAMA (pembelian saja), supaya
                # perubahannya dapat dijelaskan alih-alih ditemukan sendiri.
                "selisihVersiLama": {
                    "utangUsahaSaja": total_utang,
                    "kewajibanLancarSekarang": kewajiban_lancar,
                    "tambahan": total_lain,
                    "quickRatioVersiLama": (
                        (kas_dipakai + total_piutang) / total_utang
                        if total_utang > 0
                        else None
                    ),
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
