"""
KPI perusahaan dan papan antrean.

DUA BAGIAN, DUA PERTANYAAN

  * Kinerja — "usaha ini sedang ke mana", dari laporan laba rugi per bulan.
  * Antrean — "pekerjaan tertahan di mana", dari tahap-tahap dokumen.

Keduanya di satu layar karena dibaca bersamaan pada saat yang sama: laba
turun dan antrean pemeriksaan menumpuk adalah dua gejala yang sering satu
sebab.

KENAPA MARJIN MEMAKAI JENDELA 12 BULAN, BUKAN BULAN BERJALAN

Ini keputusan yang sudah diambil di `finance_status_controller._marjin`,
dengan alasan yang ditulis di sana: *"marjin satu bulan pada kontraktor
melompat mengikuti termin, dan angka yang melompat berhenti dipercaya
sebelum sempat dipakai."*

Itu benar untuk usaha ini. Pendapatan datang bergelombang mengikuti termin
penagihan, sementara gaji, sewa, dan penyusutan jalan rata setiap bulan.
Marjin bulan penagihan karena itu melonjak dan bulan berikutnya minus,
padahal proyek dan biayanya sama saja.

Jadi:

  * angka RUPIAH ditampilkan per bulan — itu kejadian nyata, dan naik
    turunnya memang informasi;
  * angka PERSEN memakai jendela dua belas bulan berjalan — sama seperti
    DSO dan DPO di halaman rasio, yang menolak penyebut satu bulan dengan
    alasan yang sama persis.

Konsekuensinya disebut terang-terangan di layar, bukan disembunyikan:
titik marjin pertama baru terbentuk setelah dua belas bulan data ada.
"""

from typing import Any, Dict, List

from repository.kpi_repository import KpiRepository
from utils.logger_utils import log_error

#: Panjang jendela marjin, dalam bulan.
JENDELA = 12

#: Bulan tambahan yang ikut ditarik di belakang rentang yang diminta.
#:
#: `JENDELA - 1` untuk membentuk titik marjin pertama, ditambah satu lagi
#: untuk pembanding "bulan yang sama tahun lalu" pada titik paling awal.
#: Tidak menambah kueri sama sekali — pengelompokannya di basis data.
MUNDUR_TAMBAHAN = JENDELA

#: Bidang rupiah yang dibandingkan antar-periode.
BIDANG_RUPIAH = (
    "pendapatan",
    "hpp",
    "labaKotor",
    "bebanUsaha",
    "labaUsaha",
    "labaSebelumPajak",
)


def _bagi(atas: float, bawah: float):
    """
    Rasio, atau None bila penyebutnya nol.

    None, BUKAN nol. Marjin 0% berarti pendapatan habis dimakan biaya;
    tidak ada pendapatan sama sekali adalah keadaan lain, dan menggambar
    keduanya sebagai titik di garis nol menyamakan dua hal yang berbeda.
    """
    return (atas / bawah) if bawah else None


class KpiController:
    @staticmethod
    async def perusahaan(mundur: int = 12) -> Dict[str, Any]:
        """
        Angka bulanan, marjin jendela 12 bulan, dan pembandingnya.
        """
        try:
            mundur = max(1, min(int(mundur or 12), 36))
            hasil = await KpiRepository.laba_per_bulan(
                mundur + MUNDUR_TAMBAHAN
            )
            if hasil.get("gagal"):
                # Diteruskan apa adanya. Layar harus dapat mengatakan
                # "angkanya tidak terbaca" — deret kosong akan digambar
                # sebagai perusahaan tanpa pendapatan.
                return {"bulan": [], "gagal": True}

            deret: List[Dict[str, Any]] = hasil.get("bulan") or []
            if not deret:
                return {"bulan": []}

            indeks = {(x["tahun"], x["bulan"]): i for i, x in enumerate(deret)}
            keluaran: List[Dict[str, Any]] = []

            # Hanya `mundur` bulan TERAKHIR yang dikembalikan; sisanya ditarik
            # semata-mata sebagai bahan jendela dan pembanding.
            for i in range(len(deret) - mundur, len(deret)):
                titik = deret[i]
                baris: Dict[str, Any] = {
                    k: titik[k]
                    for k in ("tahun", "bulan", *BIDANG_RUPIAH, "bebanLain")
                }

                # Jendela 12 bulan: bulan ini dan sebelas sebelumnya.
                if i + 1 >= JENDELA:
                    jendela = deret[i + 1 - JENDELA : i + 1]
                    pendapatan = sum(x["pendapatan"] for x in jendela)
                    baris["jendela"] = {
                        "bulan": JENDELA,
                        "pendapatan": round(pendapatan, 2),
                        "marjinKotor": _bagi(
                            sum(x["labaKotor"] for x in jendela), pendapatan
                        ),
                        "marjinBersih": _bagi(
                            sum(x["labaSebelumPajak"] for x in jendela),
                            pendapatan,
                        ),
                        "rasioOverhead": _bagi(
                            sum(x["bebanUsaha"] for x in jendela), pendapatan
                        ),
                    }
                else:
                    # DISEBUT, bukan dihilangkan diam-diam. Tanpa penanda ini
                    # layar tidak dapat membedakan "marjinnya nol" dari
                    # "datanya belum cukup panjang".
                    baris["jendela"] = {"bulan": JENDELA, "belumCukup": True}

                sebelumnya = deret[i - 1] if i >= 1 else None
                kunci_tahun_lalu = (titik["tahun"] - 1, titik["bulan"])
                tahun_lalu = (
                    deret[indeks[kunci_tahun_lalu]]
                    if kunci_tahun_lalu in indeks
                    else None
                )

                baris["banding"] = {
                    "bulanLalu": {
                        k: round(titik[k] - sebelumnya[k], 2)
                        for k in BIDANG_RUPIAH
                    }
                    if sebelumnya
                    else None,
                    "tahunLalu": {
                        k: round(titik[k] - tahun_lalu[k], 2)
                        for k in BIDANG_RUPIAH
                    }
                    if tahun_lalu
                    else None,
                }
                keluaran.append(baris)

            return {"bulan": keluaran, "jendelaBulan": JENDELA}
        except Exception as e:  # noqa: BLE001
            log_error(f"KPI perusahaan gagal: {str(e)}")
            return {"bulan": [], "gagal": True}

    @staticmethod
    async def antrean(user: dict, level: int, departemen: set) -> Dict[str, Any]:
        """
        Papan antrean — lihat `KpiRepository.antrean`.

        Controller ini sengaja tipis: seluruh aturannya izin, dan izin
        diputuskan di satu tempat. Menyalin aturannya ke sini berarti dua
        tempat yang harus sepakat tentang siapa boleh melihat apa.
        """
        try:
            return await KpiRepository.antrean(user, level, departemen)
        except Exception as e:  # noqa: BLE001
            log_error(f"KPI antrean gagal: {str(e)}")
            return {"tahap": [], "gagal": True}
