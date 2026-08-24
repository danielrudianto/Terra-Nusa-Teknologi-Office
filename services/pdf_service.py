from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader
import os
import uuid

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
    return env


def _lengkapi(data: dict) -> dict:
    """Tambahkan nilai turunan yang hanya dipakai saat mencetak."""
    keluar = dict(data)

    # Ringkasan pekerjaan untuk kepala dokumen: nama-nama baris kontrak,
    # dibatasi supaya kepala dokumen tidak tumbuh menjadi setengah halaman.
    nama = []
    for b in data.get("bap") or []:
        n = (b.get("pekerjaan") or "").strip()
        if n and n not in nama:
            nama.append(n)
    ringkas = ", ".join(nama[:2])
    if len(nama) > 2:
        ringkas += f", dan {len(nama) - 2} lainnya"
    keluar["pekerjaanRingkas"] = ringkas or "-"

    # Nomor BAP mengikuti nomor CoP: keduanya terbit berpasangan, dan
    # penomoran terpisah hanya menciptakan dua urutan yang harus dicocokkan
    # tangan setiap kali dokumennya dicari.
    keluar["nomorBap"] = data.get("cop", {}).get("number")
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
