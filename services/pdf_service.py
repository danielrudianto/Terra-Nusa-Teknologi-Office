from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader
import base64
import os
import uuid
from decimal import Decimal


def _D(nilai) -> Decimal:
    """
    Apa pun menjadi Decimal.

    Perkalian persen pada lembar CoP dikerjakan di sini, bukan di templat:
    Jinja menghitung dengan float, dan 5% dari 11.035.750.000 berakhir
    dengan pecahan yang tidak pernah ada di kontraknya.
    """
    if isinstance(nilai, Decimal):
        return nilai
    try:
        return Decimal(str(nilai if nilai is not None else 0))
    except Exception:
        return Decimal("0")

class PDFService:
    TEMPLATE_DIR = "templates/pdf"
    OUTPUT_DIR = "storage/salary_slips"

    @staticmethod
    def format_rupiah(amount: float) -> str:
        return f"Rp {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


    @staticmethod
    def generateSalarySlip(data: dict) -> str:
        os.makedirs(PDFService.OUTPUT_DIR, exist_ok=True)
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        TEMPLATE_DIR = os.path.join(BASE_DIR, "../templates/pdf")
        env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR)
        )
        template = env.get_template("salary_slip.html")

        MONTHS = {
            1: "Januari",
            2: "Februari",
            3: "Maret",
            4: "April",
            5: "Mei",
            6: "Juni",
            7: "Juli",
            8: "Agustus",
            9: "September",
            10: "Oktober",
            11: "November",
            12: "Desember",
        }

        month_name = MONTHS[data['month']]

        transport_total = data['transportationAllowanceRate'] * data['transportationAllowanceQuantity']
        meal_total = data['mealAllowanceRate'] * data['mealAllowanceQuantity']
        overtime_total = data['overtimeRate'] * data['overtimeQuantity']

        total_income = (
            data['basicSalary']
            + transport_total
            + meal_total
            + overtime_total + sum(item["amount"] for item in data["other_allowances"])
        )

        other_income_rows = ""
        
        if(len(data['other_allowances']) > 0):
            for item in data["other_allowances"]:
                other_income_rows += f"""
                <tr>
                    <td colspan="2">
                        <p style="margin-bottom:0; margin-top:0;">{item.get('name')}</p>
                        <p style="margin-bottom:0; margin-top:0;">{item.get('description', '')}</p>
                    </td>
                    <td>{PDFService.format_rupiah(item.get('amount'))}</td>
                    <td align="right">{PDFService.format_rupiah(item.get('amount', 0))}</td>
                </tr>
                """
        else:
            other_income_rows += f"""
                <tr>
                    <td colspan="2">
                    Tidak ada pendapatan lain
                    </td>
                    <td>{PDFService.format_rupiah(0)}</td>
                    <td align="right">{PDFService.format_rupiah(0)}</td>
                </tr>
                """

        other_deduction_rows = ""

        if(len(data['other_deductions']) > 0):
            for item in data["other_deductions"]:
                other_deduction_rows += f"""
                <tr>
                    <td colspan="2">
                        <p style="margin-bottom:0; margin-top:0;">{item.get('name')}</p>
                        <p style="margin-bottom:0; margin-top:0;">{item.get('description', '')}</p>
                    </td>
                    <td>{PDFService.format_rupiah(item.get('amount'))}</td>
                    <td align="right">{PDFService.format_rupiah(item.get('amount', 0))}</td>
                </tr>
                """
        else:
            other_deduction_rows += f"""
                <tr>
                    <td colspan="3">
                    Tidak ada pengurangan lain
                    </td>
                </tr>
                """

        total_deduction = data['taxAmount']
        gross_salary = total_income - sum(item["amount"] for item in data["other_deductions"])
        included_salary =  (
            data['basicSalary']
            + transport_total
            + meal_total
            + overtime_total
            + sum(item["amount"] for item in data["other_allowances"] if item['isIncluded'] == True)
            - sum(item["amount"] for item in data["other_deductions"] if item['isIncluded'] == True)
        )
        net_salary = gross_salary - total_deduction
        
        html_content = f"""
            <html>
            <head>
            <style>
            @page {{
                size: A4;
                margin: 10mm 12mm;
            }}

            body {{
                font-family: sans-serif;
                font-size: 12px;
            }}

            h1, h2 {{
                text-align: center;
                font-weight: normal;
                font-size: 14px;
                margin: 5px 0;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
            }}

            td {{
                padding: 3px;
            }}

            .section-title {{
                font-weight: bold;
                margin-top: 15px;
            }}

            .total {{
                font-weight: bold;
            }}

            hr {{
                border: 0.5px solid #000;
                margin: 15px 0;
            }}

            .horiz-border tr {{
                border-bottom: 0.5px solid #333;
            }}
            </style>

            </head>
            <body>

            <h1>SLIP GAJI</h1>
            <p style="text-align:center;">Periode {month_name} {data['year']}</p>

            <table style="margin-top: 20px;" class="horiz-border">
            <tr>
            <td>Nama</td>
            <td>:</td>
            <td>{data['name']}</td>
            </tr>
            <tr>
            <td>Jabatan</td>
            <td>:</td>
            <td>{data['position']}</td>
            </tr>
            <tr>
            <td>Status TK</td>
            <td>:</td>
            <td>{data['taxCategory']}</td>
            </tr>
            <tr>
            <td>NIK</td>
            <td>:</td>
            <td>{data['nik']}</td>
            </tr>
            </table>

            <h2 style="text-align:left; margin-top:20px; margin-bottom:20px;">Pendapatan</h2>

            <table class="horiz-border">
            <tr>
            <td>Gaji Pokok</td>
            <td>1</td>
            <td>LS</td>
            <td align="right">{PDFService.format_rupiah(data['basicSalary'])}</td>
            </tr>

            <tr>
            <td>Tunjangan Transportasi</td>
            <td>{data['transportationAllowanceQuantity']}</td>
            <td>hari</td>
            <td align="right">{PDFService.format_rupiah(transport_total)}</td>
            </tr>

            <tr>
            <td>Tunjangan Uang Makan</td>
            <td>{data['mealAllowanceQuantity']}</td>
            <td>hari</td>
            <td align="right">{PDFService.format_rupiah(meal_total)}</td>
            </tr>


            <tr>
            <td>Lembur</td>
            <td>{data['overtimeQuantity']}</td>
            <td>hari</td>
            <td align="right">{PDFService.format_rupiah(overtime_total)}</td>
            </tr>
            
            <tr>
            <td colspan="4"><strong>Pendapatan Lain</strong></td>
            </tr>
            {other_income_rows}

            <tr>
            <td colspan="3"><strong>Jumlah Pendapatan</strong></td>
            <td align="right" class="total">{PDFService.format_rupiah(total_income)}</td>
            </tr>

            </table>


            <h2 style="text-align:left; margin-top:20px; margin-bottom:20px;">Pengurangan</h2>

            <table class="horiz-border">
            {other_deduction_rows}
            <tr>
            <td colspan="3"><strong>Jumlah Pengurangan</strong></td>
            <td align="right" class="total">{PDFService.format_rupiah(total_deduction)}</td>
            </table>

            <h2 style="text-align:left; margin-top:20px; margin-bottom:20px;">Rekapitulasi Data</h2>
            <table class="horiz-border">
            <tr>
            <td>Jumlah gaji sebelum pajak</td>
            <td align="right" class="total">{PDFService.format_rupiah(gross_salary)}</td>
            </tr>
            <tr>
            <td>Gaji yang diperhitungkan dalam perhitungan pajak</td>
            <td align="right">{PDFService.format_rupiah(included_salary)}</td>
            </tr>
            <tr>
            <td>PPh21</td>
            <td>{PDFService.format_rupiah(data['taxAmount'])}</td>
            </tr>
            <tr>
            <td>Jumlah gaji dibayarkan</td>
            <td align="right" class="total">{PDFService.format_rupiah(net_salary)}</td>
            </tr>
            </table>



            <h2 style="text-align:left; margin-top:20px; margin-bottom:20px;">Dibayarkan melalui</h2>

            <table class="horiz-border">
            <tr>
            <td>Bank</td>
            <td>:</td>
            <td>{data['bankName']}</td>
            </tr>

            <tr>
            <td>Nomor Rekening</td>
            <td>:</td>
            <td>{data['bankAccountNumber']}</td>
            </tr>

            <tr>
            <td>Nama Akun</td>
            <td>:</td>
            <td>{data['bankAccountName']}</td>
            </tr>
            </table>
            <table class="horiz-border">
                <tr>
                    <td>
                    <p style="text-align:center">Dibuat oleh</p>
                    <br><br><br><br>
                    </td>

                    <td>
                    <p style="text-align:center">Diperiksa oleh</p>
                    <br><br><br><br>
                    </td>


                    <td>
                    <p style="text-align:center">Disetujui oleh</p>
                    <br><br><br><br>
                    </td>
                </tr>
            </table>
            </table>

            </body>
            </html>
        """

        filename = f"salary-slip-{uuid.uuid4()}.pdf"
        file_path = os.path.join(PDFService.OUTPUT_DIR, filename)

        HTML(string=html_content).write_pdf(file_path)

        return file_path


# =====================================================================
# Certificate of Payment & Berita Acara Pemeriksaan
# =====================================================================
#
# Dikembalikan sebagai BYTES, bukan disimpan sebagai berkas.
#
# Slip gaji disimpan karena ia dilampirkan pada surel; CoP diunduh langsung
# oleh yang menekan tombolnya. Menyimpannya lebih dulu hanya menumpuk berkas
# yang memuat nilai kontrak di dalam `storage/` — dan yang menumpuk di sana
# tidak ada yang membersihkan.

_BULAN_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}

_NAMA_KATEGORI = {
    "uang_muka": "Pengembalian Down Payment",
    "retensi": "Retensi",
    "denda": "Denda",
    "pph": "PPh",
    "lain_lain": "Lain-lain",
    "biaya_luar_kontrak": "Biaya di luar kontrak",
}


def _f_tanggal(nilai) -> str:
    """Tanggal gaya Indonesia. Yang kosong menjadi tanda pisah, bukan 'None'."""
    if not nilai:
        return "—"
    try:
        return f"{nilai.day} {_BULAN_ID[nilai.month]} {nilai.year}"
    except Exception:
        return str(nilai)


def _f_rupiah(nilai) -> str:
    """
    1.234.567,89 — titik ribuan, koma desimal.

    Tanpa awalan "Rp": lembar aslinya menaruh "Rp." pada kolom tersendiri,
    dan menempelkannya di sini membuat kolom itu tercetak dua kali.
    """
    try:
        n = float(nilai or 0)
    except (TypeError, ValueError):
        return "0,00"
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _f_angka(nilai) -> str:
    """Volume: dua desimal, tetapi bulat bila memang bulat."""
    try:
        n = float(nilai or 0)
    except (TypeError, ValueError):
        return "0"
    teks = f"{n:,.2f}" if n % 1 else f"{n:,.0f}"
    return teks.replace(",", "X").replace(".", ",").replace("X", ".")


def _f_persen(nilai) -> str:
    """Nilai yang SUDAH berupa persen (5 -> '5,00%')."""
    try:
        n = float(nilai or 0)
    except (TypeError, ValueError):
        n = 0.0
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + "%"


def _f_persen_pecahan(nilai) -> str:
    """
    Pecahan yang dijadikan persen (0,004747 -> '0,475%').

    Tiga desimal, bukan dua: progres mingguan pada kontrak besar kerap
    berada di bawah 0,01% — dibulatkan dua desimal seluruh barisnya menjadi
    '0,00%' dan lembarnya tidak menyatakan apa pun.
    """
    try:
        n = float(nilai or 0) * 100
    except (TypeError, ValueError):
        n = 0.0
    return f"{n:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".") + "%"


def _f_nama_kategori(kode) -> str:
    return _NAMA_KATEGORI.get(kode, str(kode or "").replace("_", " ").title())


def _f_uang(nilai) -> str:
    """
    Nominal seperti pada lembar Excel: 11,035,750,000.00 — dan NOL menjadi "-".

    Dua hal yang membedakannya dari `rupiah`:

    1. Pemisahnya mengikuti berkas aslinya (koma ribuan, titik desimal),
       bukan gaya Indonesia. Lembar ini beredar berdampingan dengan cetakan
       Excel lama di map yang sama, dan dua gaya angka pada dokumen yang
       seharusnya identik membuat yang membandingkannya berhenti untuk
       memastikan ia tidak sedang membaca dokumen yang salah.

    2. Nol dicetak sebagai tanda pisah. Barisnya memang selalu ada — uang
       muka, retensi, dan PPh dicetak sekalipun tidak dipotong — dan "0.00"
       terbaca sebagai angka hasil hitungan, sedangkan "-" terbaca sebagai
       "tidak ada", yang memang maksudnya.
    """
    try:
        n = float(nilai or 0)
    except (TypeError, ValueError):
        n = 0.0
    if abs(n) < 0.005:
        return "-"
    return f"{n:,.2f}"


def _f_persen_us(nilai) -> str:
    """
    Persen bergaya sama dengan `_f_uang`: titik desimal.

    Tarif yang BULAT dicetak tanpa desimal — "PPN 11%", bukan "PPN 11.00%".
    Begitulah tarif pajak ditulis di mana pun ia disebut, termasuk pada
    faktur yang dilampirkan bersama lembar ini; dua angka nol di belakangnya
    membuatnya terbaca seperti hasil hitungan, bukan tarif yang ditetapkan.
    """
    try:
        n = float(nilai or 0)
    except (TypeError, ValueError):
        n = 0.0
    if abs(n - round(n)) < 0.005:
        return f"{round(n):,d}%"
    return f"{n:,.2f}%"


def _f_persen_pecahan_us(nilai) -> str:
    """Pecahan menjadi persen bergaya Excel (0.004747 -> '0.47%')."""
    try:
        n = float(nilai or 0) * 100
    except (TypeError, ValueError):
        n = 0.0
    return f"{n:,.2f}%"


_SATUAN = (
    "", "Satu", "Dua", "Tiga", "Empat", "Lima",
    "Enam", "Tujuh", "Delapan", "Sembilan", "Sepuluh", "Sebelas",
)


def _terbilang_bulat(n: int) -> str:
    """
    Bilangan bulat menjadi kata Indonesia.

    Ditulis sendiri, bukan lewat pustaka: kaidahnya sedikit — "seratus" dan
    "seribu" memakai awalan *se-*, sisanya berulang per tiga digit — dan
    menambah satu ketergantungan demi itu berarti satu hal lagi yang harus
    dipasang di server saat dokumen resmi tidak mau tercetak.
    """
    if n < 0:
        return "Minus " + _terbilang_bulat(-n)
    # Nol menghasilkan untai KOSONG, bukan kata "Nol".
    #
    # Fungsi ini memanggil dirinya untuk sisa pembagian, dan sisa nol adalah
    # keadaan yang paling lazim: 58.152.900 berakhir pada sisa 0 di puluhan,
    # sehingga "Nol" di sini muncul sebagai "Sembilan Ratus Nol Rupiah".
    # Yang memanggil dari luar (`_f_terbilang`) yang menggantinya menjadi
    # "Nol" bila memang seluruh bilangannya nol.
    if n < 12:
        return _SATUAN[n]
    if n < 20:
        return _terbilang_bulat(n - 10) + " Belas"
    if n < 100:
        return _terbilang_bulat(n // 10) + " Puluh " + _terbilang_bulat(n % 10)
    if n < 200:
        return "Seratus " + _terbilang_bulat(n - 100)
    if n < 1_000:
        return _terbilang_bulat(n // 100) + " Ratus " + _terbilang_bulat(n % 100)
    if n < 2_000:
        return "Seribu " + _terbilang_bulat(n - 1_000)
    if n < 1_000_000:
        return _terbilang_bulat(n // 1_000) + " Ribu " + _terbilang_bulat(n % 1_000)
    if n < 1_000_000_000:
        return (
            _terbilang_bulat(n // 1_000_000)
            + " Juta "
            + _terbilang_bulat(n % 1_000_000)
        )
    if n < 1_000_000_000_000:
        return (
            _terbilang_bulat(n // 1_000_000_000)
            + " Milyar "
            + _terbilang_bulat(n % 1_000_000_000)
        )
    return (
        _terbilang_bulat(n // 1_000_000_000_000)
        + " Triliun "
        + _terbilang_bulat(n % 1_000_000_000_000)
    )


def _f_terbilang(nilai) -> str:
    """
    58152900 -> "Lima Puluh Delapan Juta Seratus Lima Puluh Dua Ribu Sembilan
    Ratus Rupiah".

    Sennya disebut hanya bila ADA. Nilai pada dokumen ini hampir selalu
    bulat, dan "… Rupiah Nol Sen" di setiap lembar menambah panjang tanpa
    menambah keterangan.
    """
    try:
        n = float(nilai or 0)
    except (TypeError, ValueError):
        n = 0.0
    bulat = int(abs(n))
    sen = int(round((abs(n) - bulat) * 100))
    kata = " ".join(_terbilang_bulat(bulat).split()) or "Nol"
    hasil = kata + " Rupiah"
    if sen:
        hasil += " " + " ".join(_terbilang_bulat(sen).split()) + " Sen"
    return ("Minus " + hasil) if n < 0 else hasil


def _lingkungan_cop():
    from jinja2 import Environment, FileSystemLoader

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    env = Environment(
        loader=FileSystemLoader(os.path.join(BASE_DIR, "../templates/pdf")),
        autoescape=True,
    )
    env.filters["tanggal"] = _f_tanggal
    env.filters["rupiah"] = _f_rupiah
    env.filters["angka"] = _f_angka
    env.filters["persen"] = _f_persen
    env.filters["persenPecahan"] = _f_persen_pecahan
    env.filters["namaKategori"] = _f_nama_kategori
    # Gaya Excel — dipakai lembar CoP supaya sama persis dengan cetakan lama.
    env.filters["uang"] = _f_uang
    env.filters["persenUS"] = _f_persen_us
    env.filters["persenPecahanUS"] = _f_persen_pecahan_us
    env.filters["terbilang"] = _f_terbilang
    return env


_PERUSAHAAN = {"nama": "PT. Alpha Konstruksi Nusantara"}


def _logo_data_uri() -> str:
    """
    Logo sebagai data URI, atau kosong bila berkasnya tidak ada.

    Ditanam ke dalam HTML, bukan dirujuk lewat jalur berkas: WeasyPrint
    menyelesaikan jalur relatif terhadap dokumennya, dan dokumen ini dirakit
    dari untai teks — sehingga gambar yang dirujuk begitu tidak pernah
    ditemukan dan lembarnya tercetak tanpa kop.

    Ketiadaan logo BUKAN kesalahan yang menggagalkan cetakan: dokumen tanpa
    kop masih dapat dibaca dan ditandatangani, sedangkan cetakan yang gagal
    sama sekali menghentikan penagihan.
    """
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    for nama in ("logo.png", "logo.jpg", "logo.jpeg"):
        jalur = os.path.join(BASE_DIR, "../templates/pdf/assets", nama)
        if os.path.exists(jalur):
            jenis = "jpeg" if nama.endswith(("jpg", "jpeg")) else "png"
            with open(jalur, "rb") as f:
                return f"data:image/{jenis};base64," + base64.b64encode(
                    f.read()
                ).decode("ascii")
    return ""


def _lengkapi(data: dict) -> dict:
    """Tambahkan nilai turunan yang hanya dipakai saat mencetak."""
    keluar = dict(data)
    cop = data.get("cop") or {}
    kontrak = data.get("kontrak") or {}
    spk = data.get("spk") or {}

    # Nama pekerjaan: daftar utuh untuk kepala dokumen, ringkas untuk
    # menyusul kata "Nilai Kontrak" pada bagian harga.
    nama = []
    for b in data.get("bap") or []:
        n = (b.get("pekerjaan") or "").strip()
        if n and n not in nama:
            nama.append(n)
    keluar["pekerjaanDaftar"] = nama
    ringkas = ", ".join(nama[:2])
    if len(nama) > 2:
        ringkas += f", dan {len(nama) - 2} lainnya"
    keluar["pekerjaanRingkas"] = ringkas

    # Nomor BAP mengikuti nomor CoP: keduanya terbit berpasangan, dan
    # penomoran terpisah hanya menciptakan dua urutan yang harus dicocokkan
    # tangan setiap kali dokumennya dicari.
    keluar["nomorBap"] = cop.get("number")
    keluar["nomorAdendum"] = "Ada" if kontrak.get("adaAdendum") else None

    # Syarat kontrak dihitung DI SINI, bukan di dalam templat.
    #
    # Jinja tidak memakai Decimal, sehingga perkalian persen yang ditulis di
    # templat dikerjakan sebagai float — dan 5% dari 11.035.750.000 berakhir
    # dengan angka di belakang koma yang tidak pernah ada di kontraknya.
    total = _D(kontrak.get("total"))
    keluar["syarat"] = {
        "dp": float(total * _D(spk.get("dpPercentage")) / Decimal("100")),
        "retensi": float(total * _D(spk.get("retentionPercentage")) / Decimal("100")),
        "pph": float(total * _D(spk.get("pphPercentage")) / Decimal("100")),
    }

    # Progres dipecah INDUK dan ADENDUM, seperti pada lembar Excel.
    #
    # Keduanya dibayar dengan persentase yang berbeda — adendum baru berjalan
    # setelah induknya sebagian selesai — dan satu baris gabungan menyembunyikan
    # selisih itu justru pada dokumen yang dipakai menagihnya.
    induk = Decimal("0")
    adendum = Decimal("0")
    for b in data.get("bap") or []:
        nilai_baris = _D(b.get("bobotSaatIni")) * total
        if b.get("adendum") is None:
            induk += nilai_baris
        else:
            adendum += nilai_baris
    nilai_induk = _D(kontrak.get("induk"))
    nilai_adendum = _D(kontrak.get("adendum"))
    keluar["progres"] = {
        "nilaiInduk": float(induk),
        "nilaiAdendum": float(adendum),
        "persenInduk": float(induk / nilai_induk) if nilai_induk else 0.0,
        "persenAdendum": float(adendum / nilai_adendum) if nilai_adendum else 0.0,
    }

    # Akumulasi: persentase tiap pembayaran terhadap nilai kontrak.
    riwayat = []
    akumulasi = Decimal("0")
    for r in data.get("riwayat") or []:
        net = _D(r.get("net"))
        akumulasi += net
        baris = dict(r)
        baris["persen"] = float(net / total) if total else 0.0
        riwayat.append(baris)
    keluar["riwayat"] = riwayat
    keluar["akumulasiTotal"] = float(akumulasi)

    # Penandatangan pihak pemberi tugas.
    #
    # Yang MENYETUJUI, bukan yang membuat: tanda tangan pada lembar ini
    # menyatakan bahwa perusahaan menerima tagihannya, dan itu keputusan
    # penyetuju. Selama belum disetujui kolomnya sengaja dibiarkan kosong
    # bergaris — dokumen yang belum diputuskan tidak boleh tercetak seolah
    # sudah ada yang menanggungnya.
    keluar["penandatangan"] = {
        "nama": cop.get("approvedByName"),
        "jabatan": cop.get("approvedByPosition"),
    }
    keluar["perusahaan"] = _PERUSAHAAN
    keluar["logoDataUri"] = _logo_data_uri()
    return keluar


class CoPDocumentService:
    """Cetak Certificate of Payment dan Berita Acara Pemeriksaan."""

    @staticmethod
    def render(data: dict, sertakan_bap: bool = True) -> bytes:
        """CoP (potret) + BAP (lanskap) dalam satu berkas PDF."""
        env = _lingkungan_cop()
        template = env.get_template("certificate_of_payment.html")
        html = template.render(**_lengkapi(data), sertakanBap=sertakan_bap)
        return HTML(string=html).write_pdf()

    @staticmethod
    def render_bap(data: dict) -> bytes:
        """BAP saja — seluruhnya lanskap."""
        env = _lingkungan_cop()
        template = env.get_template("berita_acara_pemeriksaan.html")
        html = template.render(**_lengkapi(data))
        return HTML(string=html).write_pdf()
