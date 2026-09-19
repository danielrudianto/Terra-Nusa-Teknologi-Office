"""
Kesimpulan dari kesebelas rasio — BACAAN BERPERINGKAT, bukan nilai rapor.

KENAPA BUKAN SATU SKOR

Kesebelas rasio ini berbeda skala, berbeda satuan, dan berbeda pula
KEANDALANNYA. Ekuitas diturunkan, bukan dicatat. Quick ratio tidak memuat
pinjaman karena `loans` tidak menyimpan tenor. Overhead punya catatan
sendiri soal pembelian aset yang dibebankan langsung.

Dirata-rata menjadi satu angka, seluruh peringatan itu hilang dan yang
tersisa kesan presisi yang tidak punya dasar — "72 dari 100" terbaca seperti
hasil ukur padahal ia hasil bobot yang dikarang. Lebih buruk lagi: begitu ada
angka besar di atas, orang berhenti membaca komponennya, dan komponennyalah
satu-satunya yang dapat ditindaklanjuti.

YANG DIKERJAKAN DI SINI

1. Rasio yang berada DI LUAR acuan diurutkan menurut seberapa jauh ia di
   luar DIKALI seberapa berakibat rasio itu. Diambil paling banyak tiga.
2. KOMBINASI dibaca — dan di sinilah nilainya. Marjin yang aman bersama
   siklus modal kerja yang panjang berarti "untung di kertas, belum di kas";
   ROE tinggi bersama utang tinggi berarti ROE-nya terangkat utang. Tidak
   satu pun dari keduanya terlihat dari rasio yang dibaca sendiri-sendiri.
3. Yang TIDAK DAPAT DILIHAT oleh kesimpulan ini disebutkan, sebagai daftar.
   Kesimpulan yang tidak menyebut batasnya akan dipercaya melampaui batas
   itu.

Seluruhnya BERBASIS ATURAN. Tidak ada bobot tersembunyi dan tidak ada model:
tiap kalimat yang keluar dari sini dapat ditelusuri ke satu aturan di bawah
beserta angka yang memicunya, dan itu memang syaratnya — kesimpulan yang
tidak dapat dibantah dengan angkanya sendiri tidak pantas dipercaya.

Bahasa TIDAK disusun di sini. Yang dikembalikan kode beserta angkanya;
layar yang menerjemahkan. Menyusun kalimat di server berarti satu bahasa
saja yang pernah benar.
"""

from typing import Any, Dict, List, Optional

#: Seberapa berakibat sebuah rasio bila ia meleset — untuk mengurutkan.
#:
#: Urutannya mengikuti apa yang benar-benar menjatuhkan kontraktor, bukan
#: seberapa sering rasionya disebut di buku teks:
#:
#:   * tidak mampu membayar yang jatuh tempo — seketika, tidak dapat ditawar;
#:   * piutang yang menua dan piutang yang menumpuk pada satu klien — uang
#:     yang makin lama makin tidak akan datang;
#:   * menalangi pekerjaan sendiri terlalu lama — habis di tengah jalan
#:     walaupun proyeknya untung;
#:   * struktur modal dan marjin — menentukan arah, tetapi memberi waktu;
#:   * ROE paling akhir: ia AKIBAT, bukan sebab. Menindaklanjuti ROE berarti
#:     menindaklanjuti sesuatu yang lain.
BOBOT: Dict[str, float] = {
    "quickRatio": 1.00,
    "piutangTua": 0.90,
    "konsentrasiPiutang": 0.85,
    "siklusModalKerja": 0.80,
    "debtToEquity": 0.70,
    "dso": 0.60,
    "marjinBersih": 0.55,
    "rasioOverhead": 0.50,
    "marjinKotor": 0.45,
    "dpo": 0.30,
    "roe": 0.25,
}

#: Rasio yang menyinggung laba. Digerbang level 5, sama dengan blok marjin.
#:
#: Bukan hanya angkanya yang bocor kalau ini tidak dijaga: kalimat "marjin
#: bersih tipis" MENYATAKAN arah laba perusahaan kepada level yang blok
#: marjinnya sengaja tidak digambar untuknya.
RASIO_LABA = frozenset(
    {"marjinKotor", "marjinBersih", "rasioOverhead", "roe"}
)

#: Paling banyak sekian butir mendesak yang disebut.
#:
#: Tiga, bukan sebelas. Daftar yang memuat segalanya tidak memberi
#: prioritas — dan yang membacanya akan mengerjakan yang paling mudah, bukan
#: yang paling berakibat.
MAKS_MENDESAK = 3


def _jarak_dari_pita(nilai: float, pita: Dict[str, Any]) -> Optional[float]:
    """
    Seberapa jauh di luar pita, sebagai PECAHAN dari batas yang dilanggar.

    Dinormalkan supaya rasio yang satuannya hari (DSO 120 vs batas 95) dapat
    diurutkan bersama rasio yang satuannya pecahan (piutang tua 0,30 vs batas
    0,15). Tanpa normalisasi, yang satuannya besar selalu menang dan DSO akan
    selamanya berada di puncak daftar apa pun keadaannya.

    `None` bila ia tidak di luar pita.
    """
    if nilai is None or not pita:
        return None
    bawah = pita.get("bawah")
    atas = pita.get("atas")

    if atas is not None and nilai > atas:
        # Batas nol tidak dapat menjadi penyebut; pakai selisih apa adanya.
        return (nilai - atas) / abs(atas) if atas else float(nilai)
    if bawah is not None and nilai < bawah:
        return (bawah - nilai) / abs(bawah) if bawah else float(-nilai)
    return None


def _kombinasi(
    r: Dict[str, Any],
    p: Dict[str, Any],
    pinjaman: float,
    boleh_laba: bool,
) -> List[Dict[str, Any]]:
    """
    Temuan yang HANYA muncul dari dua rasio dibaca bersama.

    Inilah bagian yang tidak dapat digantikan dengan membaca petak satu per
    satu, dan alasan kesimpulan ini dibuat sama sekali.
    """

    def letak(kode: str) -> Optional[str]:
        return (p.get(kode) or {}).get("posisi")

    def nilai(kode: str):
        v = r.get(kode)
        return v if isinstance(v, (int, float)) else None

    keluar: List[Dict[str, Any]] = []

    # --- Untung di kertas, belum di kas ---------------------------------
    #
    # Marjin bersih di dalam atau di atas acuan, tetapi siklus modal kerja
    # panjang. Labanya nyata; uangnya belum ada di rekening, dan yang
    # menalanginya perusahaan sendiri.
    if boleh_laba:
        if letak("marjinBersih") in ("didalam", "diatas") and letak(
            "siklusModalKerja"
        ) == "diatas":
            keluar.append(
                {
                    "kode": "untungDiKertas",
                    "angka": {
                        "marjinBersih": nilai("marjinBersih"),
                        "siklusModalKerja": nilai("siklusModalKerja"),
                    },
                }
            )

        # --- ROE terangkat utang ----------------------------------------
        #
        # ROE membagi laba dengan EKUITAS. Ekuitas yang tipis karena utang
        # besar membuat ROE naik tanpa satu rupiah pun laba tambahan. Dibaca
        # sendirian, ROE tinggi terbaca sebagai prestasi.
        #
        # Syaratnya "ROE-nya BAIK", bukan "di atas pita".
        #
        # Pita ROE tidak punya sisi atas (`atas: None`) — makin tinggi makin
        # baik. Jadi `posisi == "diatas"` TIDAK PERNAH benar untuk ROE, dan
        # aturan yang memakainya tidak akan pernah menyala sekali pun.
        # Tertangkap oleh ujinya sendiri; tanpa uji itu, aturan ini akan
        # duduk di sini selamanya tampak masuk akal tanpa pernah berbunyi.
        roe_baik = bool((p.get("roe") or {}).get("baik"))
        if roe_baik and letak("debtToEquity") == "diatas":
            keluar.append(
                {
                    "kode": "roeTerangkatUtang",
                    "angka": {
                        "roe": nilai("roe"),
                        "debtToEquity": nilai("debtToEquity"),
                    },
                }
            )

        # --- Proyeknya sehat, kantornya yang memakan --------------------
        if letak("rasioOverhead") == "diatas" and letak("marjinKotor") in (
            "didalam",
            "diatas",
        ):
            keluar.append(
                {
                    "kode": "kantorYangMemakan",
                    "angka": {
                        "rasioOverhead": nilai("rasioOverhead"),
                        "marjinKotor": nilai("marjinKotor"),
                    },
                }
            )

    # --- Satu klien menentukan kas ---------------------------------------
    if letak("konsentrasiPiutang") == "diatas" and letak("dso") == "diatas":
        keluar.append(
            {
                "kode": "satuKlienMenentukan",
                "angka": {
                    "konsentrasiPiutang": nilai("konsentrasiPiutang"),
                    "dso": nilai("dso"),
                },
            }
        )

    # --- Piutang tua tersamar oleh faktur baru ---------------------------
    #
    # DSO adalah RATA-RATA. Faktur baru yang deras menariknya turun sementara
    # yang tua tetap di tempatnya — jadi DSO yang wajar bersama piutang tua
    # yang besar berarti rata-ratanya menyembunyikan tumpukan itu, bukan
    # meniadakannya.
    if letak("piutangTua") == "diatas" and letak("dso") == "didalam":
        keluar.append(
            {
                "kode": "piutangTuaTersamar",
                "angka": {
                    "piutangTua": nilai("piutangTua"),
                    "dso": nilai("dso"),
                },
            }
        )

    # --- Dibiayai pemasok -------------------------------------------------
    #
    # DPO jauh melampaui DSO TERLIHAT baik pada rasionya — perusahaan memakai
    # uang pemasok, bukan uangnya sendiri. Bersama quick ratio yang di bawah
    # acuan, artinya berbalik: bukan pilihan, melainkan karena kasnya tidak
    # cukup untuk membayar tepat waktu. Yang menanggung pemasok, dan itu
    # tagihan yang jatuh tempo sekaligus begitu mereka berhenti bersabar.
    d_dso, d_dpo = nilai("dso"), nilai("dpo")
    if (
        d_dso is not None
        and d_dpo is not None
        and d_dpo > d_dso
        and letak("quickRatio") == "dibawah"
    ):
        keluar.append(
            {
                "kode": "dibiayaiPemasok",
                "angka": {"dso": d_dso, "dpo": d_dpo},
            }
        )

    # --- Likuiditas yang belum memperhitungkan angsuran -------------------
    if letak("quickRatio") in ("didalam", "diatas") and pinjaman > 0:
        keluar.append(
            {
                "kode": "likuiditasBelumMemuatAngsuran",
                "angka": {
                    "quickRatio": nilai("quickRatio"),
                    "pinjaman": pinjaman,
                },
            }
        )

    return keluar


def susun(
    rasio: Dict[str, Any],
    penilaian: Dict[str, Any],
    ambang: Dict[str, Any],
    *,
    ekuitas: float,
    pinjaman: float,
    boleh_laba: bool,
) -> Dict[str, Any]:
    """
    Bacaan berperingkat atas seluruh rasio yang nilainya ada.

    Yang dikembalikan KODE, bukan kalimat — layar yang menerjemahkan.
    """
    rasio = rasio or {}
    penilaian = penilaian or {}
    ambang = ambang or {}

    dinilai = {
        k: v
        for k, v in rasio.items()
        if isinstance(v, (int, float)) and k in BOBOT
    }
    if not boleh_laba:
        # Digerbang DI SINI, bukan di layar. Menyaringnya di peramban berarti
        # kalimatnya tetap dikirim ke sana dan tinggal dibuka di alat
        # pengembang. Lihat `RASIO_LABA`.
        dinilai = {k: v for k, v in dinilai.items() if k not in RASIO_LABA}

    mendesak: List[Dict[str, Any]] = []
    aman: List[str] = []
    for kode, nilai in dinilai.items():
        letak = (penilaian.get(kode) or {}).get("posisi")
        baik = (penilaian.get(kode) or {}).get("baik")
        if letak is None:
            continue
        if baik:
            aman.append(kode)
            continue
        jarak = _jarak_dari_pita(nilai, ambang.get(kode))
        if jarak is None:
            # Di luar pita menurut penilaian, tetapi jaraknya tidak terhitung
            # (pita tanpa sisi yang dilanggar). Tetap disebut, di urutan
            # paling bawah — bukan dibuang diam-diam.
            jarak = 0.0
        mendesak.append(
            {
                "kode": kode,
                "nilai": nilai,
                "posisi": letak,
                "jarakDariPita": round(jarak, 4),
                "bobot": BOBOT[kode],
                "skor": round(jarak * BOBOT[kode], 4),
            }
        )

    mendesak.sort(key=lambda x: (-x["skor"], x["kode"]))

    kombinasi = _kombinasi(rasio, penilaian, pinjaman, boleh_laba)

    # --- Kalimat pokok ----------------------------------------------------
    #
    # Ekuitas minus mengalahkan segalanya: pada keadaan itu D/E dan ROE tidak
    # bermakna, dan yang perlu dibicarakan bukan rasio mana pun melainkan
    # bahwa kewajiban sudah melampaui aset.
    if ekuitas <= 0:
        pokok = {"kode": "ekuitasMinus", "angka": {"ekuitas": ekuitas}}
    elif mendesak:
        pokok = {
            "kode": "adaYangDiLuarAcuan",
            "angka": {
                "jumlah": len(mendesak),
                "teratas": mendesak[0]["kode"],
            },
        }
    elif kombinasi:
        pokok = {"kode": "semuaDidalamTapiAdaCatatan",
                 "angka": {"jumlah": len(kombinasi)}}
    else:
        pokok = {"kode": "semuaDidalamAcuan", "angka": {"jumlah": len(aman)}}

    # --- Yang tidak terlihat ----------------------------------------------
    #
    # SELALU ADA, dan itu disengaja. Kesimpulan yang kadang menyebut batasnya
    # dan kadang tidak akan dibaca sebagai "kali ini tidak ada batasnya".
    tak_terlihat = ["ekuitasDiturunkanBukanDicatat", "piutangTanpaJatuhTempo"]
    if pinjaman > 0:
        tak_terlihat.insert(0, "pinjamanTanpaTenor")
    if not boleh_laba:
        tak_terlihat.append("marjinTidakIkutDinilai")

    return {
        "pokok": pokok,
        "mendesak": mendesak[:MAKS_MENDESAK],
        "jumlahMendesak": len(mendesak),
        "aman": sorted(aman),
        "kombinasi": kombinasi,
        "takTerlihat": tak_terlihat,
        # Supaya layar dapat menyebut "dinilai dari N rasio" — dan supaya
        # jelas bahwa yang tidak dinilai memang tidak ada nilainya, bukan
        # terlewat.
        "jumlahDinilai": len(dinilai),
    }
