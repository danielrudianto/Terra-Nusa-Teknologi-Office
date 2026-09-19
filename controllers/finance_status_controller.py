import asyncio
from datetime import date as d
from typing import Any, Dict

from repository.finance_status_repository import (
    AMBANG_BAWAAN,
    FinanceStatusRepository,
)
from utils.logger_utils import log_error
from utils.errors import ErrorCode, app_error


#: Level yang boleh melihat angka laba rugi pada halaman ini.
#:
#: Sama dengan gerbang laporan laba rugi itu sendiri. Ditulis SEKALI di sini
#: dan dibaca dari situ, bukan disalin sebagai angka 5 ke beberapa tempat —
#: yang disalin akan berselisih pada perubahan berikutnya, dan yang
#: berselisih di sini berarti angka laba bocor ke halaman yang tidak
#: dimaksudkan.
LEVEL_LIHAT_LABA = 5


def boleh_melihat_laba(user_level: int) -> bool:
    try:
        return int(user_level or 0) >= LEVEL_LIHAT_LABA
    except (TypeError, ValueError):
        return False


def posisi_terhadap_pita(nilai, pita) -> Dict[str, Any]:
    """
    Di mana satu angka berdiri terhadap pitanya, DAN apakah itu kabar baik.

    KENAPA INI ADA

    Versi sebelumnya hanya mencetak angkanya beserta pitanya sebagai tulisan
    kecil, dengan alasan tidak mau memvonis. Akibatnya layar berhenti
    menjawab pertanyaan yang membuat orang membukanya: "2,03 itu bagus atau
    tidak?" Peringatannya lebih panjang dan lebih menonjol daripada
    jawabannya, dan angkanya berdiri telanjang tanpa apa pun yang
    menerangkannya.

    Yang dikembalikan di sini MENILAI ANGKANYA, bukan perusahaannya —
    "di atas acuan" adalah pernyataan tentang letak, dan `baik` mengatakan ke
    mana letak itu condong menurut arah rasionya. Kalimat "apa artinya" dan
    "apa yang menggerakkannya" ditambahkan layar di atas ini. Itu beda
    dengan mencetak kata SEHAT pada perusahaannya, yang membuat orang
    berhenti bertanya.

    `None` bila angkanya belum ada — dan itu BUKAN "di dalam acuan".
    """
    if nilai is None:
        return {"posisi": None, "baik": None}

    pita = pita or {}
    bawah = pita.get("bawah")
    atas = pita.get("atas")
    arah = pita.get("arah") or "pita"

    if bawah is not None and nilai < bawah:
        posisi = "dibawah"
    elif atas is not None and nilai > atas:
        posisi = "diatas"
    else:
        posisi = "didalam"

    if posisi == "didalam":
        baik = True
    elif arah == "naikBaik":
        # Di atas pita pada rasio yang makin tinggi makin baik BUKAN masalah.
        baik = posisi == "diatas"
    elif arah == "naikBuruk":
        baik = posisi == "dibawah"
    else:
        # Dua sisinya sama-sama berarti.
        baik = False

    return {"posisi": posisi, "baik": baik}


class FinanceStatusController:
    #: Sejauh apa ke belakang akurasi rencana boleh diminta, dalam bulan.
    #:
    #: Dua belas menutup satu tahun penuh sehingga pola musiman masih
    #: terlihat, dan menahan agar satu parameter di URL tidak dapat memaksa
    #: pemindaian seluruh riwayat.
    MAKS_MUNDUR = 12

    @staticmethod
    async def get_status(user_level: int = 1) -> Dict[str, Any]:
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
                arus,
                konsentrasi,
                backlog,
                ambang,
            ) = await asyncio.gather(
                FinanceStatusRepository.total_kas(),
                FinanceStatusRepository.piutang(),
                FinanceStatusRepository.utang_usaha(),
                FinanceStatusRepository.pinjaman(),
                FinanceStatusRepository.kewajiban_lain(),
                FinanceStatusRepository.nilai_buku_aset(),
                FinanceStatusRepository.arus_setahun(),
                FinanceStatusRepository.konsentrasi_piutang(),
                FinanceStatusRepository.backlog(),
                FinanceStatusRepository.ambang(),
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

            # ---- PERPUTARAN ----
            #
            # `None` BUKAN nol. Perusahaan yang belum berfaktur setahun
            # terakhir tidak punya DSO — dan "0 hari" pada keadaan itu
            # terbaca sebagai penagihan yang sempurna.
            pendapatan_th = float(arus.get("pendapatan") or 0)
            pembelian_th = float(arus.get("pembelian") or 0)
            hari = int(arus.get("hari") or 365)

            dso = (
                (total_piutang / pendapatan_th * hari)
                if pendapatan_th > 0
                else None
            )
            dpo = (
                (total_utang / pembelian_th * hari)
                if pembelian_th > 0
                else None
            )
            # Tanpa persediaan, siklus modal kerja = DSO - DPO. Inilah berapa
            # hari perusahaan MENALANGI pekerjaannya sendiri.
            siklus = (dso - dpo) if (dso is not None and dpo is not None) else None

            piutang_total = float(piutang.get("total") or 0)
            umur_piutang = piutang.get("umur") or {}
            piutang_tua = (
                (float(umur_piutang.get("90+") or 0) / piutang_total)
                if piutang_total > 0
                else None
            )

            # Penyusun tiap rasio — supaya angkanya dapat DICEK sendiri.
            hitungan: Dict[str, Any] = {
                "quickRatio": {
                    "pembilang": {
                        "label": "kasDanPiutang",
                        "nilai": kas_dipakai + total_piutang,
                        "rincian": [
                            {"kategori": "kas", "nilai": kas_dipakai},
                            {"kategori": "piutang", "nilai": total_piutang},
                        ],
                    },
                    "penyebut": {
                        "label": "kewajibanLancar",
                        "nilai": kewajiban_lancar,
                        "rincian": [
                            {"kategori": "utangUsaha", "nilai": total_utang},
                            {"kategori": "kewajibanLain", "nilai": total_lain},
                        ],
                    },
                },
                "debtToEquity": {
                    "pembilang": {
                        "label": "totalKewajiban",
                        "nilai": kewajiban_lancar + total_pinjaman,
                        "rincian": [
                            {"kategori": "utangUsaha", "nilai": total_utang},
                            {"kategori": "kewajibanLain", "nilai": total_lain},
                            {"kategori": "pinjaman", "nilai": total_pinjaman},
                        ],
                    },
                    "penyebut": {"label": "ekuitas", "nilai": ekuitas},
                },
                "dso": {
                    "pembilang": {"label": "piutang", "nilai": total_piutang},
                    "penyebut": {
                        "label": "pendapatan12Bulan",
                        "nilai": pendapatan_th,
                    },
                    "pengali": {"label": "hari", "nilai": hari},
                },
                "dpo": {
                    "pembilang": {"label": "utangUsaha", "nilai": total_utang},
                    "penyebut": {
                        "label": "pembelian12Bulan",
                        "nilai": pembelian_th,
                    },
                    "pengali": {"label": "hari", "nilai": hari},
                },
                "piutangTua": {
                    "pembilang": {
                        "label": "piutangLewat90",
                        "nilai": float(umur_piutang.get("90+") or 0),
                    },
                    "penyebut": {"label": "piutang", "nilai": piutang_total},
                },
                "konsentrasiPiutang": {
                    "pembilang": {
                        "label": "klienTerbesar",
                        "nilai": float(
                            (konsentrasi.get("terbesar") or {}).get("sisa") or 0
                        ),
                    },
                    "penyebut": {
                        "label": "piutang",
                        "nilai": float(konsentrasi.get("total") or 0),
                    },
                },
            }

            rasio = {
                "dso": dso,
                "dpo": dpo,
                "siklusModalKerja": siklus,
                "piutangTua": piutang_tua,
                "konsentrasiPiutang": konsentrasi.get("bagianTerbesar"),
                # Penyebutnya disebut supaya angkanya dapat ditelusuri, bukan
                # sekadar dipercaya.
                "dasar": {
                    "pendapatan12Bulan": pendapatan_th,
                    "pembelian12Bulan": pembelian_th,
                    "hari": hari,
                    "sejak": arus.get("sejak"),
                },
            }

            # ---- MARJIN & ROE: HANYA LEVEL 5 ----
            #
            # Keduanya angka LABA RUGI, dan laba rugi memang hanya dilayani
            # untuk pemilik usaha. Menggambarnya di halaman level 4 akan
            # melonggarkan batas itu sebagai EFEK SAMPING — bukan sebagai
            # keputusan yang pernah diambil siapa pun.
            #
            # Bloknya TIDAK DIGAMBAR sama sekali untuk level di bawahnya,
            # bukan digambar kosong: kotak bertanda pisah memberi tahu bahwa
            # ada angka yang disembunyikan, dan itu pertanyaan yang berulang.
            if boleh_melihat_laba(user_level):
                laba = await FinanceStatusController._marjin(
                    ekuitas, pendapatan_th
                )
                if laba:
                    # `_hitungan` BUKAN rasio — ia rincian penyusunnya.
                    # Membiarkannya masuk membuat penilaian pita mencoba
                    # menilai sebuah dict, dan layar menggambar kartu rasio
                    # bernama "_hitungan".
                    hitungan.update(laba.pop("_hitungan", {}))
                    rasio.update(laba)

            # Penilaian letak tiap angka terhadap pitanya — SATU tempat,
            # sesudah seluruh rasio terkumpul (termasuk marjin bila
            # levelnya mencukupi), supaya tidak ada rasio yang terlewat
            # dinilai hanya karena ditambahkan belakangan.
            dinilai = {
                "quickRatio": quick_ratio,
                "debtToEquity": dte,
                **{
                    k: v
                    for k, v in rasio.items()
                    if k in AMBANG_BAWAAN and isinstance(v, (int, float))
                },
            }
            penilaian = {
                kode: posisi_terhadap_pita(nilai, ambang.get(kode))
                for kode, nilai in dinilai.items()
            }

            return {
                "kas": kas,
                "kasDikecualikan": kas_dikecualikan,
                "rasio": rasio,
                "hitungan": hitungan,
                "penilaian": penilaian,
                "bolehMelihatLaba": boleh_melihat_laba(user_level),
                "konsentrasi": konsentrasi,
                "backlog": backlog,
                "ambang": ambang,
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
    async def _marjin(ekuitas: float, pendapatan_th: float) -> Dict[str, Any]:
        """
        Marjin kotor/bersih/overhead dan ROE — dari laporan laba rugi.

        Memakai AKUMULASI TAHUN BERJALAN, bukan bulan berjalan: marjin satu
        bulan pada kontraktor melompat mengikuti termin, dan angka yang
        melompat berhenti dipercaya sebelum sempat dipakai.

        Kegagalan di sini mengembalikan `{}` — blok marjinnya tidak digambar,
        dan SISA halamannya tetap utuh. Laba rugi adalah modul lain dengan
        kuerinya sendiri; membiarkannya menjatuhkan angka kas akan membuat
        satu kegagalan di sana menghapus seluruh alasan halaman ini dibuka.
        """
        try:
            from repository.laba_rugi_repository import LabaRugiRepository

            hari_ini = d.today()
            lr = await LabaRugiRepository.laba_rugi(
                hari_ini.month, hari_ini.year
            )
            if not isinstance(lr, dict) or "error" in lr:
                return {}
            ytd = lr.get("ytd") or lr.get("tahunBerjalan") or {}
            if not ytd:
                return {}

            pendapatan = float(ytd.get("pendapatan") or 0)
            if pendapatan <= 0:
                # Tanpa pendapatan, marjin tidak terdefinisi — bukan nol.
                return {}

            laba_kotor = float(ytd.get("labaKotor") or 0)
            beban_usaha = float((ytd.get("bebanUsaha") or {}).get("total") or 0)
            laba_bersih = float(ytd.get("labaSebelumPajak") or 0)

            # RINCIAN penyusun tiap marjin, supaya angkanya dapat DICEK —
            # bukan hanya dipercaya. Rasio yang tidak dapat ditelusuri ke
            # komponennya akan ditanyakan berulang kali, dan yang menjawab
            # harus membuka laporan lain untuk membuktikannya.
            rincian_beban = (ytd.get("bebanUsaha") or {}).get("rincian") or []
            rincian_hpp = (ytd.get("hpp") or {}).get("rincian") or []

            hitungan = {
                "marjinKotor": {
                    "pembilang": {
                        "label": "labaKotor",
                        "nilai": laba_kotor,
                        "rumus": "pendapatan - beban pokok proyek",
                    },
                    "penyebut": {"label": "pendapatan", "nilai": pendapatan},
                    "pengurang": {
                        "label": "hpp",
                        "nilai": float((ytd.get("hpp") or {}).get("total") or 0),
                        "rincian": rincian_hpp,
                    },
                },
                "rasioOverhead": {
                    "pembilang": {
                        "label": "bebanUsaha",
                        "nilai": beban_usaha,
                        # Inilah yang ditanyakan: isinya apa saja.
                        "rincian": rincian_beban,
                    },
                    "penyebut": {"label": "pendapatan", "nilai": pendapatan},
                },
                "marjinBersih": {
                    "pembilang": {
                        "label": "labaSebelumPajak",
                        "nilai": laba_bersih,
                    },
                    "penyebut": {"label": "pendapatan", "nilai": pendapatan},
                },
                "roe": {
                    "pembilang": {
                        "label": "labaSebelumPajak",
                        "nilai": laba_bersih,
                    },
                    "penyebut": {"label": "ekuitas", "nilai": ekuitas},
                },
            }

            return {
                "marjinKotor": laba_kotor / pendapatan,
                "marjinBersih": laba_bersih / pendapatan,
                "rasioOverhead": beban_usaha / pendapatan,
                "_hitungan": hitungan,
                # ROE hanya bermakna pada ekuitas POSITIF. Pada ekuitas minus
                # laba positif menghasilkan ROE minus, yang terbaca sebagai
                # rugi — kebalikan dari keadaannya.
                "roe": (laba_bersih / ekuitas) if ekuitas > 0 else None,
                "dasarLaba": {
                    "pendapatanYtd": pendapatan,
                    "labaBersihYtd": laba_bersih,
                    "basis": "akumulasi tahun berjalan",
                },
            }
        except Exception as e:
            log_error(f"Error menghitung marjin: {str(e)}")
            return {}

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


    @staticmethod
    async def simpan_ambang(
        kode: str, payload: Dict[str, Any], user_id: int
    ) -> Dict[str, Any]:
        """
        Setel satu pita acuan.

        Batas bawah tidak boleh melampaui batas atas: pita terbalik tidak
        menghasilkan galat, ia hanya membuat SETIAP nilai berada di luar
        acuan — seluruh rasio menyala merah sekaligus, dan yang membacanya
        akan mengira perusahaannya yang bermasalah.
        """
        try:
            bawah = payload.get("bawah")
            atas = payload.get("atas")
            bawah = None if bawah in (None, "") else float(bawah)
            atas = None if atas in (None, "") else float(atas)

            if bawah is not None and atas is not None and bawah > atas:
                return app_error(
                    ErrorCode.VALIDATION,
                    "Batas bawah tidak boleh melampaui batas atas.",
                    400,
                )

            hasil = await FinanceStatusRepository.simpan_ambang(
                kode, bawah, atas, user_id
            )
            if "error" in hasil:
                return app_error(
                    ErrorCode.VALIDATION,
                    f"Pita acuan '{kode}' tidak dikenali.",
                    400,
                )
            return {"kode": kode, "bawah": bawah, "atas": atas}
        except (TypeError, ValueError):
            return app_error(
                ErrorCode.VALIDATION, "Nilai pita harus berupa angka.", 400
            )
        except Exception as e:
            log_error(f"Error menyimpan ambang: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def hapus_ambang(kode: str) -> Dict[str, Any]:
        """Kembalikan satu pita ke bawaannya."""
        try:
            hasil = await FinanceStatusRepository.hapus_ambang(kode)
            if "error" in hasil:
                return {"error": "Internal server error.", "status": 500}
            return {"kode": kode, "dikembalikan": True}
        except Exception as e:
            log_error(f"Error menghapus ambang: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
