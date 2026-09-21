import asyncio
from datetime import date as d, timedelta
from typing import Any, Dict

from controllers import kesimpulan_keuangan
from repository.finance_status_repository import (
    AMBANG_BAWAAN,
    TOLERANSI_LUNAS,
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

    #: Berapa bulan riwayat dihitung berbarengan.
    #:
    #: Tiap bulan melepas tujuh kueri. Empat bulan = dua puluh delapan kueri
    #: beredar — cukup untuk membuat kolam koneksi sibuk, belum cukup untuk
    #: membuatnya mengantre. Dinaikkan lagi, yang bertambah bukan kecepatan
    #: melainkan waktu tunggu di dalam kolam, dan pada kolam yang kecil ia
    #: berubah menjadi timeout yang tampak sebagai halaman gagal dimuat.
    BULAN_SERENTAK = 4

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
            # Porsi pinjaman BERJADWAL yang jatuh tempo dalam 12 bulan, dan
            # sisa pinjaman TANPA jadwal. Bila penanda porsinya tidak ada
            # (jalur galat repository), seluruh pinjaman dianggap tanpa
            # jadwal — perilaku lama, bukan nol yang membuat rasio membaik.
            pinjaman_lancar = float(pinjaman.get("lancar") or 0)
            pinjaman_tanpa_tenor = float(
                pinjaman.get("tanpaTenor", total_pinjaman) or 0
            )
            total_lain = float(lain.get("total") or 0)
            nilai_buku = float(aset_tetap.get("nilaiBuku") or 0)

            # ---- KEWAJIBAN LANCAR: pembelian DAN yang selama ini terlewat ----
            #
            # `payments_outgoing` dapat menunjuk lima jenis dokumen, dan empat
            # di antaranya kewajiban kepada pihak luar. Selama hanya pembelian
            # yang dihitung, gaji bulan berjalan yang belum cair tidak muncul
            # sebagai kewajiban sama sekali — dan rasio yang disusun di atasnya
            # tampak lebih baik daripada keadaannya.
            kewajiban_lancar = total_utang + total_lain + pinjaman_lancar

            """
            Quick ratio = (kas + piutang usaha) / kewajiban lancar.

            Persediaan tidak dikurangkan karena memang tidak ada: master item
            hanya katalog, tanpa kuantitas maupun nilai stok. Untuk perusahaan
            ini quick ratio dan current ratio menghasilkan angka yang sama,
            dan itu justru membuat angkanya tidak mengandung penilaian
            tentang seberapa cepat stok dapat dicairkan.

            Pinjaman BERJADWAL (bertenor) masuk penyebut sebesar porsi yang
            jatuh tempo dalam 12 bulan — lihat `porsi_lancar()`. Pinjaman
            TANPA jadwal (mis. pinjaman pribadi) tetap di luar: porsinya tidak
            dapat dipisahkan, dan menebaknya menghasilkan rasio yang tampak
            pasti padahal dasarnya karangan.

            Konsekuensinya disebutkan apa adanya: bila pinjaman tanpa jadwal
            itu jatuh tempo dalam waktu dekat, rasio ini lebih baik daripada
            keadaan sebenarnya. Karena itu sisanya dikembalikan juga dan
            ditampilkan di sisi rasionya.
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
            # dalam 30 hari — termasuk yang sudah lewat — dan angsuran
            # pinjaman bertenor yang jatuh tempo dalam 30 hari.
            #
            # PIUTANG TIDAK DITAMBAHKAN. `sales_invoices` tidak menyimpan
            # jatuh tempo, jadi tidak ada dasar untuk mengatakan sebuah faktur
            # akan tertagih dalam 30 hari. Ia tetap dikirim sebagai
            # KETERANGAN di sebelah angkanya, bukan sebagai suku penjumlahan.
            tempo = utang.get("tempo") or {}
            jatuh_tempo_lewat = float(tempo.get("lewat") or 0)
            jatuh_tempo_utang_30 = jatuh_tempo_lewat + float(tempo.get("0-30") or 0)
            # Angsuran pinjaman BERJADWAL yang jatuh tempo dalam 30 hari
            # (termasuk tunggakan). Pinjaman tanpa tenor tidak ikut — jadwalnya
            # tidak diketahui.
            angsuran_30 = float(pinjaman.get("jatuhTempo30") or 0)
            jatuh_tempo_30 = jatuh_tempo_utang_30 + angsuran_30

            umur = piutang.get("umur") or {}
            piutang_muda = float(umur.get("0-30") or 0)

            likuiditas = {
                "kas": kas_dipakai,
                "kewajiban30": jatuh_tempo_30,
                "kewajibanLewat": jatuh_tempo_lewat,
                "utang30": jatuh_tempo_utang_30,
                "angsuranPinjaman30": angsuran_30,
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
            # Porsi lancar pinjaman SUDAH ada di `kewajiban_lancar`; yang
            # ditambahkan di sini hanya sisanya, supaya tidak terhitung dua kali.
            total_kewajiban = kewajiban_lancar + (total_pinjaman - pinjaman_lancar)
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
                        ]
                        + (
                            [{"kategori": "pinjamanLancar", "nilai": pinjaman_lancar}]
                            if pinjaman_lancar > 0
                            else []
                        ),
                    },
                },
                "debtToEquity": {
                    "pembilang": {
                        "label": "totalKewajiban",
                        "nilai": total_kewajiban,
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

            # Kesimpulan disusun SESUDAH seluruh rasio dan penilaiannya
            # terkumpul — termasuk marjin bila levelnya mencukupi. Disusun
            # lebih awal, ia akan menyimpulkan dari sebagian rasio dan tidak
            # ada apa pun di jawabannya yang menyebut bahwa ada yang
            # terlewat.
            #
            # `dinilai`, BUKAN `rasio` — dan selisihnya bukan sepele.
            #
            # `rasio` tidak memuat quick ratio maupun D/E; keduanya masuk ke
            # `dinilai` secara terpisah beberapa baris di atas. Diserahkan
            # `rasio`, kesimpulan ini akan menjatuhkan quick ratio —
            # satu-satunya rasio berbobot tertinggi di sana, yang artinya
            # "tidak mampu membayar yang jatuh tempo" tidak akan pernah muncul
            # sebagai butir mendesak. Tidak ada galat: daftarnya hanya lebih
            # pendek, dan yang membacanya menyimpulkan tidak ada masalah
            # likuiditas.
            kesimpulan = kesimpulan_keuangan.susun(
                dinilai,
                penilaian,
                ambang,
                ekuitas=ekuitas,
                # Hanya yang TANPA jadwal: pinjaman berjadwal sudah masuk
                # quick ratio lewat porsi lancarnya, jadi peringatan "rasio
                # belum memuat angsuran" tidak berlaku untuknya.
                pinjaman=pinjaman_tanpa_tenor,
                boleh_laba=boleh_melihat_laba(user_level),
            )

            return {
                "kas": kas,
                "kasDikecualikan": kas_dikecualikan,
                "rasio": rasio,
                "hitungan": hitungan,
                "penilaian": penilaian,
                "kesimpulan": kesimpulan,
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
                    # Hanya pinjaman TANPA jadwal yang di luar rasio; yang
                    # berjadwal sudah masuk lewat porsi lancarnya.
                    "pinjamanDiluarRasio": pinjaman_tanpa_tenor > TOLERANSI_LUNAS,
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
                    "tambahan": total_lain + pinjaman_lancar,
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

    #: Rasio yang ditarik mundur. SENGAJA hanya likuiditas dan penagihan.
    #:
    #: Marjin TIDAK ada di sini. Marjin butuh laba rugi per periode, dan
    #: laba rugi disusun dari beban yang dicatat menurut tanggal DOKUMEN —
    #: bukan tanggal kejadiannya. Menariknya mundur akan menghasilkan marjin
    #: masa lalu yang berubah setiap kali sebuah nota lama diinput hari ini,
    #: dan garis yang berubah sendiri tanpa ada yang mengubah apa pun adalah
    #: garis yang berhenti dipercaya.
    RASIO_RIWAYAT = (
        "quickRatio",
        "debtToEquity",
        "dso",
        "dpo",
        "siklusModalKerja",
        "piutangTua",
        "konsentrasiPiutang",
    )

    @staticmethod
    def _titik_bulan(mundur: int) -> list:
        """
        Tanggal potret untuk tiap bulan, dari yang terlama ke hari ini.

        Potretnya diambil pada AKHIR bulan, kecuali bulan berjalan yang
        diambil pada hari ini — akhir bulan berjalan belum terjadi, dan
        memakainya berarti membandingkan posisi hari ini dengan tanggal yang
        belum ada dokumennya.
        """
        hari_ini = d.today()
        titik: list = []
        t, b = hari_ini.year, hari_ini.month

        # Mundur dulu ke bulan terlama, lalu maju supaya urutannya kronologis.
        b -= mundur - 1
        while b <= 0:
            b += 12
            t -= 1

        for _ in range(mundur):
            if t == hari_ini.year and b == hari_ini.month:
                titik.append(hari_ini)
            else:
                # Akhir bulan = sehari sebelum awal bulan berikutnya. Ditulis
                # begini, bukan dengan tabel 28/30/31, supaya tahun kabisat
                # tidak perlu diurus sendiri.
                if b == 12:
                    awal_depan = d(t + 1, 1, 1)
                else:
                    awal_depan = d(t, b + 1, 1)
                titik.append(awal_depan - timedelta(days=1))
            b += 1
            if b > 12:
                b = 1
                t += 1
        return titik

    @staticmethod
    async def _potret(
        pada: d, siap: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Rasio likuiditas dan penagihan PADA satu tanggal.

        Rumusnya SAMA PERSIS dengan `get_status`; yang berbeda hanya
        tanggalnya. Kalau rumus di sini disalin lalu menyimpang seujung pun,
        titik terakhir grafik tidak akan sama dengan angka besar yang
        tercetak di atasnya — dan yang melihatnya akan mengira salah satunya
        rusak tanpa tahu yang mana.
        """
        # KAS DIAMBIL DI LUAR, sekali untuk seluruh bulan.
        #
        # `total_kas(pada)` memindai view `mutation` dengan kunci hitung yang
        # tidak dapat memakai indeks; memanggilnya per bulan berarti dua belas
        # pemindaian penuh atas seluruh riwayat transaksi perusahaan. Lihat
        # `kas_per_bulan` untuk rinciannya. Bila pemanggil tidak menyediakan,
        # jalur lama tetap dipakai — supaya fungsi ini tetap benar sendirian.
        # SUMBER YANG SUDAH DIAMBIL SEKALIGUS diteruskan pemanggil.
        #
        # Empat di antaranya — kas, aset, pinjaman, arus — diambil SEKALI
        # untuk seluruh bulan lalu disusun di Python. Lihat catatan pada
        # `kas_per_bulan` dan `aset_per_tanggal` di repositori: yang mahal
        # bukan hitungannya melainkan perjalanan bolak-baliknya, dan
        # perjalanan itu dikali dua belas.
        #
        # Yang TIDAK disediakan pemanggil tetap diambil sendiri, supaya
        # fungsi ini tetap benar bila dipanggil sendirian.
        siap = siap or {}
        kas = siap.get("kas")
        if kas is None:
            kas = await FinanceStatusRepository.total_kas(pada)

        perlu = []
        aset_siap = siap.get("aset")
        pinjaman_siap = siap.get("pinjaman")
        arus_siap = siap.get("arus")

        perlu.append(FinanceStatusRepository.piutang(pada))
        perlu.append(FinanceStatusRepository.utang_usaha(pada))
        perlu.append(FinanceStatusRepository.kewajiban_lain(pada))
        perlu.append(FinanceStatusRepository.konsentrasi_piutang(pada))
        if aset_siap is None:
            perlu.append(FinanceStatusRepository.nilai_buku_aset(pada))
        if pinjaman_siap is None:
            perlu.append(FinanceStatusRepository.pinjaman(pada))
        if arus_siap is None:
            perlu.append(FinanceStatusRepository.arus_setahun(pada))

        hasil = list(await asyncio.gather(*perlu))
        piutang = hasil.pop(0)
        utang = hasil.pop(0)
        lain = hasil.pop(0)
        konsentrasi = hasil.pop(0)
        aset_tetap = aset_siap if aset_siap is not None else hasil.pop(0)
        pinjaman = pinjaman_siap if pinjaman_siap is not None else hasil.pop(0)
        arus = arus_siap if arus_siap is not None else hasil.pop(0)

        # KAS YANG TIDAK TERBACA BUKAN KAS NOL.
        #
        # Saldo lampau disusun ulang dari view `mutation`. Bila view itu
        # tidak ada — atau kuerinya gagal — `total_kas` mengembalikan nol
        # beserta penanda `gagal`. Tanpa memeriksa penanda itu, titik
        # bersangkutan tergambar sebagai bulan tanpa kas sama sekali:
        # quick ratio jatuh, ekuitas minus, dan grafiknya menceritakan
        # kebangkrutan yang tidak pernah terjadi.
        kas_gagal = bool(kas.get("gagal"))
        kas_dipakai = float(kas.get("total") or 0)
        total_piutang = float(piutang.get("total") or 0)
        total_utang = float(utang.get("total") or 0)
        total_pinjaman = float(pinjaman.get("total") or 0)
        # SAMA dengan halaman "hari ini" — riwayat dan titik terakhirnya
        # harus menyebut angka yang sama (`integrasi_riwayat_setara_test`).
        pinjaman_lancar = float(pinjaman.get("lancar") or 0)
        total_lain = float(lain.get("total") or 0)
        nilai_buku = float(aset_tetap.get("nilaiBuku") or 0)

        kewajiban_lancar = total_utang + total_lain + pinjaman_lancar
        total_aset = kas_dipakai + total_piutang + nilai_buku
        total_kewajiban = kewajiban_lancar + (total_pinjaman - pinjaman_lancar)
        ekuitas = total_aset - total_kewajiban

        quick = (
            (kas_dipakai + total_piutang) / kewajiban_lancar
            if kewajiban_lancar > 0
            else None
        )
        dte = (total_kewajiban / ekuitas) if ekuitas > 0 else None

        pendapatan_th = float(arus.get("pendapatan") or 0)
        pembelian_th = float(arus.get("pembelian") or 0)
        hari = int(arus.get("hari") or 365)

        dso = (
            (total_piutang / pendapatan_th * hari) if pendapatan_th > 0 else None
        )
        dpo = (
            (total_utang / pembelian_th * hari) if pembelian_th > 0 else None
        )
        siklus = (dso - dpo) if (dso is not None and dpo is not None) else None

        umur = piutang.get("umur") or {}
        piutang_tua = (
            (float(umur.get("90+") or 0) / total_piutang)
            if total_piutang > 0
            else None
        )

        kon_total = float(konsentrasi.get("total") or 0)
        kon_terbesar = float((konsentrasi.get("terbesar") or {}).get("sisa") or 0)
        kon = (kon_terbesar / kon_total) if kon_total > 0 else None

        if kas_gagal:
            # Yang bergantung pada kas DIKOSONGKAN seluruhnya. Yang tidak —
            # DSO, DPO, piutang tua, konsentrasi — tetap sah dan tetap
            # digambar; membuang semuanya akan menghapus informasi yang
            # benar karena satu sumber yang gagal.
            quick = None
            dte = None

        return {
            "tanggal": pada.isoformat(),
            # Penanda per TITIK, bukan per jawaban: satu bulan yang gagal
            # tidak boleh membuat sebelas bulan lainnya ikut dicurigai.
            "kasTidakTerbaca": kas_gagal,
            "quickRatio": quick,
            "debtToEquity": dte,
            "dso": dso,
            "dpo": dpo,
            "siklusModalKerja": siklus,
            "piutangTua": piutang_tua,
            "konsentrasiPiutang": kon,
            # Angka mentahnya ikut: grafik rasio tanpa angka di baliknya
            # tidak dapat dicek oleh siapa pun yang mencurigainya.
            "kas": None if kas_gagal else kas_dipakai,
            "piutang": total_piutang,
            "utangUsaha": total_utang,
            "kewajibanLain": total_lain,
            "pinjaman": total_pinjaman,
            "asetTetap": nilai_buku,
            "ekuitas": None if kas_gagal else ekuitas,
            # Ekuitas minus membuat D/E kosong. Tanpa penanda ini, layar
            # hanya melihat `null` dan tidak dapat membedakan "tidak ada
            # datanya" dari "keadaannya memang begitu".
            "ekuitasMinus": (not kas_gagal) and ekuitas <= 0,
        }

    @staticmethod
    async def riwayat(mundur: int = 12) -> Dict[str, Any]:
        """
        Rasio likuiditas dan penagihan, ditarik mundur per bulan.

        DIHITUNG ULANG DARI DOKUMEN, bukan dibaca dari tabel potret. Tidak
        ada tabel potret di sistem ini, dan membuatnya berarti angka masa
        lalu berhenti ikut terkoreksi ketika sebuah faktur lama diperbaiki.

        Harganya jujur disebut: delapan kueri per bulan. Karena itu ia rute
        TERSENDIRI dan tidak ikut terbawa setiap kali halaman posisi keuangan
        dibuka, dan bulannya dibatasi.

        SATU BATASAN YANG HARUS DIBACA BERSAMA ANGKANYA: saldo kas masa lalu
        DIREKONSTRUKSI dari mutasi rekening, bukan dibaca dari saldo yang
        tercatat — karena yang tercatat hanya saldo hari ini. Bila ada
        mutasi yang tidak terekam, kas bulan-bulan lampau akan meleset, dan
        melesetnya ikut ke quick ratio dan ekuitas pada titik itu. Titik
        terakhir tidak terkena: ia memakai saldo yang tercatat, sama dengan
        angka besar di halaman utama.
        """
        try:
            mundur = max(1, min(int(mundur), FinanceStatusController.MAKS_MUNDUR))

            tanggal = FinanceStatusController._titik_bulan(mundur)

            # ---- KAS: SATU kueri untuk seluruh bulan ----
            #
            # Inilah perbaikan yang paling terasa. `total_kas(pada)` memindai
            # view `mutation` lewat kunci hitung yang tidak dapat memakai
            # indeks; dipanggil per bulan, ia dua belas kali menyusun ulang
            # seluruh riwayat transaksi perusahaan. Halaman riwayat terasa
            # menggantung bukan karena banyaknya kueri, melainkan karena
            # biaya SATU di antaranya dikalikan dua belas.
            #
            # Titik TERAKHIR dikecualikan dan memakai saldo TERCATAT, bukan
            # rekonstruksi. Dua alasan, dan keduanya penting:
            #
            #   1. Ia tanggal hari ini, bukan akhir bulan — pengelompokan per
            #      bulan akan memberinya saldo akhir bulan yang belum terjadi.
            #   2. Titik terakhir itulah yang sejajar dengan angka besar di
            #      kepala halaman. Menyusunnya ulang dari mutasi berarti dua
            #      angka untuk hari yang sama, dan selisih sekecil apa pun di
            #      antara keduanya tidak akan dapat dijelaskan kepada siapa
            #      pun yang menanyakannya.
            #
            # Catatan dokumentasi sebelumnya sudah menjanjikan perilaku ini;
            # kodenya yang belum mengikutinya.
            bulan_penuh = tanggal[:-1]
            (
                kas_terakhir,
                kas_bulanan,
                peta_aset,
                peta_pinjaman,
                peta_arus,
            ) = await asyncio.gather(
                FinanceStatusRepository.total_kas(),
                FinanceStatusRepository.kas_per_bulan(bulan_penuh),
                FinanceStatusRepository.aset_per_tanggal(tanggal),
                FinanceStatusRepository.pinjaman_per_tanggal(tanggal),
                FinanceStatusRepository.arus_per_tanggal(tanggal),
            )
            peta_kas = dict(kas_bulanan)
            peta_kas[tanggal[-1].isoformat()] = kas_terakhir

            # ---- Bulan dikerjakan BERBARENGAN, tetapi dibatasi ----
            #
            # Sebelumnya berurutan: dua belas perjalanan bolak-balik yang
            # saling menunggu padahal tidak saling bergantung. Sekaligus
            # semuanya juga salah — tujuh kueri kali dua belas bulan dilepas
            # serentak ke kolam koneksi yang jauh lebih kecil, dan yang
            # terjadi bukan lebih cepat melainkan antrean, lalu timeout.
            #
            # Empat bulan sekaligus: dua puluh delapan kueri beredar, cukup
            # untuk membuat kolam sibuk tanpa membuatnya mengantre.
            batas = asyncio.Semaphore(FinanceStatusController.BULAN_SERENTAK)

            async def satu(t: d) -> Dict[str, Any]:
                async with batas:
                    k = t.isoformat()
                    return await FinanceStatusController._potret(
                        t,
                        {
                            "kas": peta_kas.get(k),
                            "aset": peta_aset.get(k),
                            "pinjaman": peta_pinjaman.get(k),
                            "arus": peta_arus.get(k),
                        },
                    )

            titik, ambang = await asyncio.gather(
                asyncio.gather(*(satu(t) for t in tanggal)),
                FinanceStatusRepository.ambang(),
            )
            titik = list(titik)

            return {
                "mundur": mundur,
                "rasio": list(FinanceStatusController.RASIO_RIWAYAT),
                "titik": titik,
                "ambang": ambang,
                "catatan": {
                    "kasLampauDirekonstruksiDariMutasi": True,
                    "titikTerakhirAdalahHariIni": True,
                    "marjinTidakDitarikMundur": True,
                },
            }
        except Exception as e:
            log_error(f"Error menyusun riwayat rasio: {str(e)}")
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
