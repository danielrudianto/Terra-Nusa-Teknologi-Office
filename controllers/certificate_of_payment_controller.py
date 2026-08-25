"""
Certificate of Payment — keputusan dan penjagaannya.

Yang dijaga di berkas ini ada empat, dan semuanya menyentuh uang:

  1. BARIS HARUS MILIK SPK-nya. Baris pekerjaan yang tidak ada pada rantai
     dokumen ditolak — termasuk baris milik SPK proyek lain.

  2. AKUMULASI TIDAK MELAMPAUI PAGU. Seluruh CoP atas satu baris dijumlahkan;
     yang melampaui volume kontraknya ditolak beserta angka sisanya, supaya
     yang mengisi tahu berapa yang masih boleh.

  3. HARGA TIDAK PERNAH DATANG DARI LAYAR. Ia dibaca dari baris SPK di server.
     Yang dikirim layar hanya volume.

  4. NILAI RUPIAH DISARING SEBELUM DIKIRIM. Level 1 tidak menerima angka
     harga sama sekali — bukan menerimanya lalu menyembunyikannya.

Volume yang bertambah tidak diselesaikan di sini: SPK-nya yang diadendum,
dan pagu baris barunya terbuka dengan sendirinya.
"""

from decimal import Decimal
from typing import Any, Dict, List

from models.certificate_of_payment_model import (
    KATEGORI_POTONGAN,
    KATEGORI_TAMBAHAN,
)
from repository.certificate_of_payment_repository import (
    CertificateOfPaymentRepository,
)
from repository.purchase_order_repository import PurchaseOrderRepository
from utils.errors import ErrorCode, app_error, internal_error
from utils.logger_utils import log_error
from utils.permission import (
    boleh_melihat_nilai_cop,
    boleh_membuat_cop,
    boleh_memeriksa_cop,
    boleh_menyetujui_cop,
    boleh_menyetujui_sendiri,
)


def _d(nilai: Any) -> Decimal:
    if nilai is None:
        return Decimal("0")
    if isinstance(nilai, Decimal):
        return nilai
    return Decimal(str(nilai))


#: Kolom bernilai rupiah pada CoP dan barisnya.
#:
#: Dikumpulkan di satu tempat supaya penyaringnya tidak perlu diingat ulang
#: setiap kali sebuah kolom ditambahkan — yang terlewat tidak menimbulkan
#: galat apa pun, hanya harga yang diam-diam sampai ke lapangan.
KOLOM_NILAI_ITEM = ("price", "amount")
KOLOM_NILAI_HEADER = (
    "total",
    "totalAmount",
    "grossAmount",
    "deductionTotal",
    "additionTotal",
    "netAmount",
)


class CertificateOfPaymentController:
    """Aturan Certificate of Payment."""

    # ------------------------------------------------------------------
    # Jenis dokumen
    # ------------------------------------------------------------------

    #: Jenis SPK yang TIDAK dilayani Certificate of Payment.
    #:
    #: Keduanya dikecualikan atas keputusan pemilik, dengan sebab berbeda:
    #:
    #:   A — pekerjaannya tidak ditagihkan bertahap, sehingga berita acara
    #:       progres tidak menyatakan apa pun di sana;
    #:   D — penagihannya sudah ditangani pembuat faktur yang lebih dulu ada.
    #:       Menyediakan jalur kedua untuk pekerjaan yang sama membuat dua
    #:       dokumen dapat terbit atas progres yang satu, dan yang menerima
    #:       tagihan tidak punya cara mengetahui mana yang berlaku.
    #:
    #: Ditegakkan pada SETIAP pintu masuk — daftar pilihan, pagu, pembuatan,
    #: dan pencetakan. Satu jalur yang lupa dijaga sudah cukup membuat
    #: aturannya tidak berlaku.
    JENIS_TANPA_COP = frozenset({"A", "D"})

    @staticmethod
    def adalah_spk(po: Dict[str, Any]) -> bool:
        """
        Dokumen ini terbit sebagai SURAT PERINTAH KERJA?

        Memakai `_awalan_dokumen` milik purchase order — SATU-SATUNYA tempat
        jenis dokumen ditentukan. Menyalin daftarnya ke sini akan membuat
        keduanya berselisih pada jenis berikutnya yang ditambahkan, dan yang
        tertinggal tidak menimbulkan galat: hanya CoP yang diam-diam menolak
        SPK yang sah, atau menerima purchase order yang bukan haknya.
        """
        import json

        from controllers.purchase_order_controller import PurchaseOrderController

        custom = po.get("customData")
        if isinstance(custom, str):
            try:
                custom = json.loads(custom or "{}")
            except Exception:
                custom = {}

        jenis = (po.get("purchaseType") or "").strip()
        # Varian diringkas dulu ("H1" -> "H"), sama seperti saat nomornya
        # disusun — tanpa itu pengecualian di bawah tidak pernah cocok.
        jenis = PurchaseOrderController.VARIAN_JENIS.get(jenis, jenis)
        if jenis in CertificateOfPaymentController.JENIS_TANPA_COP:
            return False

        awalan = PurchaseOrderController._awalan_dokumen(
            po.get("purchaseType") or "", custom or {}
        )
        return awalan == "SPK"

    @staticmethod
    async def spk_kandidat(
        project_name: str | None = None,
        keyword: str | None = None,
        user_level: int = 1,
    ):
        """
        Daftar SPK yang dapat dijadikan dasar CoP.

        Penyaring SPK-vs-PO dijalankan DI SINI, bukan di SQL: jenis dokumen
        ditentukan `_awalan_dokumen` yang membaca `customData`.

        Nilai `dpp` ikut disaring seperti tempat lain — daftar pilihan pun
        tidak boleh membocorkan nilai kontrak kepada lapangan.
        """
        try:
            baris = await CertificateOfPaymentRepository.spk_kandidat(
                project_name, keyword
            )
            if isinstance(baris, dict) and "error" in baris:
                return baris

            hasil = []
            for po in baris:
                if not CertificateOfPaymentController.adalah_spk(po):
                    continue
                keluar = {
                    "id": po["id"],
                    "name": po["name"],
                    "projectName": po["projectName"],
                    "purchaseType": po["purchaseType"],
                    "supplierName": po.get("supplierName"),
                    # Alamat pemasok BUKAN nilai rupiah, jadi ia ikut ke
                    # level 1: yang mengisi volume tetap perlu memastikan
                    # SPK yang dipegangnya milik pemasok yang benar, dan
                    # nomor SPK yang mirip dibedakan justru oleh ini.
                    "supplierAddress": po.get("supplierAddress"),
                    "date": po.get("date"),
                }
                if boleh_melihat_nilai_cop(user_level):
                    keluar["dpp"] = float(po["dpp"] or 0)
                hasil.append(keluar)
            return hasil
        except Exception as e:
            log_error(f"Gagal membaca kandidat SPK: {str(e)}")
            return internal_error()

    # ------------------------------------------------------------------
    # Penyaringan nilai
    # ------------------------------------------------------------------

    @staticmethod
    def saring_nilai(data: Any, user_level: int) -> Any:
        """
        Buang seluruh angka rupiah bila levelnya belum boleh melihatnya.

        Dipakai pada SETIAP jalan keluar — detail, daftar, dan pagu — bukan
        hanya pada satu di antaranya. Satu jalan yang lupa disaring sudah
        cukup membuat aturannya tidak berlaku.
        """
        if boleh_melihat_nilai_cop(user_level):
            return data

        def _bersih(d: Dict[str, Any], kolom) -> Dict[str, Any]:
            keluar = dict(d)
            for k in kolom:
                keluar.pop(k, None)
            return keluar

        if isinstance(data, list):
            return [
                CertificateOfPaymentController.saring_nilai(x, user_level)
                for x in data
            ]
        if not isinstance(data, dict):
            return data

        hasil = _bersih(data, KOLOM_NILAI_HEADER + KOLOM_NILAI_ITEM)

        # Penyesuaian dibuang SELURUH BARISNYA, bukan hanya nominalnya.
        #
        # Sebuah baris "Potongan uang muka" tanpa angka pun sudah menceritakan
        # susunan kesepakatan dengan pemasok — dan itu bukan bagian pekerjaan
        # orang lapangan.
        hasil.pop("adjustments", None)
        # Syarat pajak SPK juga bukan bagian pekerjaan lapangan.
        hasil.pop("spkSyarat", None)

        if isinstance(data.get("items"), list):
            hasil["items"] = [
                _bersih(dict(i), KOLOM_NILAI_ITEM) for i in data["items"]
            ]
        if isinstance(data.get("data"), list):
            hasil["data"] = [
                CertificateOfPaymentController.saring_nilai(x, user_level)
                for x in data["data"]
            ]
        return hasil

    # ------------------------------------------------------------------
    # Pagu
    # ------------------------------------------------------------------

    @staticmethod
    async def pagu_spk(
        purchase_order_id: int, user_level: int = 1
    ) -> Dict[str, Any] | List[Dict[str, Any]]:
        """
        Baris pekerjaan SPK ini beserta sisa pagunya.

        Inilah yang dibaca layar orang lapangan untuk memilih pekerjaan —
        dan karena itu ia pun disaring: yang tampak hanya volume dan sisanya.
        """
        try:
            spk = await PurchaseOrderRepository.get_by_id(purchase_order_id)
            if not spk or (isinstance(spk, dict) and "error" in spk):
                return app_error(ErrorCode.NOT_FOUND, "SPK tidak ditemukan", 404)

            # Dijaga di sini JUGA, bukan hanya saat menyimpan: layar yang
            # memuat baris purchase order pembelian sudah menyesatkan yang
            # mengisinya sebelum ia sempat menekan simpan.
            if not CertificateOfPaymentController.adalah_spk(spk):
                return app_error(
                    ErrorCode.VALIDATION,
                    "Dokumen ini purchase order pembelian, bukan SPK. "
                    "Certificate of payment hanya dibuat atas SPK.",
                    400,
                )

            baris = await CertificateOfPaymentRepository.pagu(purchase_order_id)
            # Decimal tidak dapat dikirim apa adanya sebagai JSON.
            keluar = [
                {
                    **b,
                    "price": float(b["price"]),
                    "pagu": float(b["pagu"]),
                    "terpakai": float(b["terpakai"]),
                    "sisa": float(b["sisa"]),
                }
                for b in baris
            ]
            return CertificateOfPaymentController.saring_nilai(keluar, user_level)
        except Exception as e:
            log_error(f"Gagal membaca pagu SPK: {str(e)}")
            return internal_error()

    # ------------------------------------------------------------------
    # Buat
    # ------------------------------------------------------------------

    @staticmethod
    async def create(
        data: Dict[str, Any],
        user_id: int,
        user_level: int = 1,
        departments: set | None = None,
    ):
        """Buat CoP baru atas sebuah SPK."""
        try:
            if not boleh_membuat_cop(user_level, departments):
                return app_error(
                    ErrorCode.FORBIDDEN,
                    "Certificate of payment hanya dapat dibuat oleh divisi "
                    "engineering.",
                    403,
                )

            po_id = data.get("purchaseOrderID")
            if not po_id:
                return app_error(
                    ErrorCode.VALIDATION, "SPK belum dipilih.", 400
                )

            spk = await PurchaseOrderRepository.get_by_id(int(po_id))
            if not spk or (isinstance(spk, dict) and "error" in spk):
                return app_error(ErrorCode.NOT_FOUND, "SPK tidak ditemukan", 404)

            # SPK harus SUDAH DISETUJUI.
            #
            # Dokumen yang belum disetujui belum menjadi kesepakatan; volume
            # di dalamnya belum tentu yang akan berlaku, dan mensertifikasi
            # progres atasnya berarti menagih pekerjaan yang dasarnya masih
            # dapat berubah.
            if not spk.get("isApproved"):
                return app_error(
                    ErrorCode.VALIDATION,
                    "SPK belum disetujui. Certificate of payment hanya dapat "
                    "dibuat atas SPK yang sudah terbit.",
                    400,
                )

            # Dokumennya harus benar-benar SPK, bukan PURCHASE ORDER.
            #
            # CoP mensertifikasi PEKERJAAN yang terlaksana bertahap — itulah
            # yang diperintahkan sebuah surat perintah kerja. Purchase order
            # adalah pembelian barang: ia diterima sekali, dan progres
            # mingguan atasnya tidak berarti apa-apa.
            #
            # Diperiksa dengan fungsi yang SAMA dengan yang menyusun nomornya,
            # bukan dengan membaca teks "SPK" pada namanya. Jenis dokumen di
            # sini bergantung isian (PO-F jasa uji terbit sebagai SPK, PO-F
            # material sebagai PO), dan menebaknya dari teks membuat keduanya
            # tertukar tanpa galat apa pun.
            if not CertificateOfPaymentController.adalah_spk(spk):
                return app_error(
                    ErrorCode.VALIDATION,
                    "Certificate of payment hanya dapat dibuat atas SPK "
                    "(surat perintah kerja), bukan atas purchase order "
                    "pembelian barang.",
                    400,
                )

            galat_periode = CertificateOfPaymentController._periksa_periode(data)
            if galat_periode:
                return galat_periode

            items_masuk = data.get("items") or []
            if not items_masuk:
                return app_error(
                    ErrorCode.VALIDATION,
                    "Tidak ada baris pekerjaan yang diisi.",
                    400,
                )

            siap, galat = await CertificateOfPaymentController._siapkan_items(
                int(po_id), items_masuk
            )
            if galat:
                return galat

            induk_id = spk.get("parentPurchaseOrderID") or spk.get("id") or int(po_id)
            nomor = await CertificateOfPaymentRepository.nomor_berikut(int(po_id))
            nama = f"{spk.get('name') or f'SPK-{induk_id}'}/CoP-{nomor:03d}"

            hasil = await CertificateOfPaymentRepository.create(
                {
                    "name": nama,
                    "number": nomor,
                    "purchaseOrderID": induk_id,
                    "projectName": data.get("projectName") or spk.get("projectName") or "",
                    "date": data.get("date"),
                    "periodStart": data.get("periodStart"),
                    "periodEnd": data.get("periodEnd"),
                    "note": data.get("note"),
                },
                siap,
                user_id,
            )
            return hasil
        except Exception as e:
            log_error(f"Gagal membuat CoP: {str(e)}")
            return internal_error()

    @staticmethod
    def _periksa_periode(data: Dict[str, Any]):
        """
        Periode WAJIB, dan urutannya harus masuk akal.

        Ditegakkan DI SINI, bukan hanya di layar dan bukan hanya di skema:
        skema menolak yang kosong, tetapi tidak dapat menyatakan bahwa
        akhir tidak boleh mendahului awal — dan periode terbalik menghasilkan
        BAP yang menyebut rentang negatif tanpa satu pun galat muncul.
        """
        awal = data.get("periodStart")
        akhir = data.get("periodEnd")
        if not awal or not akhir:
            return app_error(
                ErrorCode.VALIDATION,
                "Periode pekerjaan wajib diisi — tanggal awal dan akhirnya.",
                400,
            )
        try:
            if akhir < awal:
                return app_error(
                    ErrorCode.VALIDATION,
                    "Periode akhir tidak boleh mendahului periode awal.",
                    400,
                )
        except TypeError:
            # Jenis tanggalnya tidak dapat dibandingkan; skema yang menolak.
            pass
        return None

    @staticmethod
    async def _siapkan_items(
        purchase_order_id: int,
        items_masuk: List[Dict[str, Any]],
        abaikan_cop_id: int | None = None,
    ):
        """
        Ubah kiriman layar menjadi baris siap simpan — atau tolak.

        Di sinilah harga DIAMBIL dari SPK dan pagunya diperiksa. Yang
        dikembalikan sepasang: (baris_siap, galat). Salah satunya selalu None.
        """
        pagu = await CertificateOfPaymentRepository.pagu(purchase_order_id)
        peta = {b["purchaseOrderItemID"]: b for b in pagu}

        # Volume yang sudah tercatat pada CoP INI sendiri tidak boleh dihitung
        # sebagai pemakaian orang lain saat ia disunting — bila dihitung,
        # menyunting CoP tanpa mengubah apa pun akan ditolak karena pagunya
        # seolah terpakai dua kali.
        milik_sendiri: Dict[int, Decimal] = {}
        if abaikan_cop_id:
            lama = await CertificateOfPaymentRepository.get_by_id(abaikan_cop_id)
            if isinstance(lama, dict) and "error" not in lama:
                for i in lama.get("items") or []:
                    kunci = i["purchaseOrderItemID"]
                    milik_sendiri[kunci] = milik_sendiri.get(
                        kunci, Decimal("0")
                    ) + _d(i["quantity"])

        siap: List[Dict[str, Any]] = []
        # Beberapa baris kiriman boleh menunjuk pekerjaan yang sama; yang
        # diperiksa jumlahnya, bukan satu per satu — kalau tidak, sepuluh
        # baris @ 30 jam lolos semua pada pagu 50.
        diminta: Dict[int, Decimal] = {}

        for it in items_masuk:
            baris_id = it.get("purchaseOrderItemID")
            if baris_id is None:
                return None, app_error(
                    ErrorCode.VALIDATION, "Ada baris tanpa pekerjaan.", 400
                )
            baris_id = int(baris_id)

            if baris_id not in peta:
                return None, app_error(
                    ErrorCode.VALIDATION,
                    "Ada baris pekerjaan yang bukan milik SPK ini.",
                    400,
                )

            jumlah = _d(it.get("quantity"))
            if jumlah <= 0:
                return None, app_error(
                    ErrorCode.VALIDATION,
                    f"Volume pada '{peta[baris_id]['task'] or 'baris'}' harus "
                    "lebih dari nol.",
                    400,
                )
            diminta[baris_id] = diminta.get(baris_id, Decimal("0")) + jumlah

        for baris_id, jumlah in diminta.items():
            b = peta[baris_id]
            tersedia = b["sisa"] + milik_sendiri.get(baris_id, Decimal("0"))
            if jumlah > tersedia:
                return None, app_error(
                    ErrorCode.VALIDATION,
                    f"Volume '{b['task'] or 'baris'}' melebihi sisa SPK. "
                    f"Diminta {jumlah:g} {b['unit'] or ''}".strip()
                    + f", sisa {tersedia:g} {b['unit'] or ''}".rstrip()
                    + ". Bila volumenya memang bertambah, SPK harus "
                    "diadendum lebih dahulu.",
                    400,
                )

        for it in items_masuk:
            baris_id = int(it["purchaseOrderItemID"])
            b = peta[baris_id]
            jumlah = _d(it.get("quantity"))
            harga = b["price"]
            siap.append(
                {
                    "purchaseOrderItemID": baris_id,
                    "quantity": jumlah,
                    # Harga & nilai DISUSUN DI SINI, bukan diambil dari `it`.
                    "price": harga,
                    "amount": jumlah * harga,
                    "remarks": it.get("remarks"),
                }
            )
        return siap, None

    # ------------------------------------------------------------------
    # Ubah
    # ------------------------------------------------------------------

    @staticmethod
    async def update(
        cop_id: int,
        data: Dict[str, Any],
        user_id: int,
        user_level: int = 1,
        departments: set | None = None,
    ):
        """
        Sunting CoP — hanya SELAMA belum diperiksa.

        Setelah diperiksa, isinya sudah menjadi dasar orang lain mengambil
        keputusan; mengubahnya diam-diam membuat yang memeriksa menyetujui
        angka yang bukan lagi yang dibacanya.
        """
        try:
            lama = await CertificateOfPaymentRepository.get_by_id(cop_id)
            if isinstance(lama, dict) and "error" in lama:
                return lama

            # Pembuatnya, atau siapa pun yang berwenang MEMERIKSA.
            #
            # Memeriksa bukan sekadar membubuhkan tanda: tugasnya membetulkan
            # volume yang keliru dicatat sebelum dokumennya naik ke penyetuju.
            # Batas level 3 di sini membuat pemeriksa level 2 hanya dapat
            # menolak seluruh dokumen dan mengembalikannya ke lapangan untuk
            # satu angka yang salah ketik — yang dalam praktiknya berakhir
            # dengan dokumen ditandai diperiksa apa adanya.
            adalah_pembuat = int(lama.get("createdBy") or 0) == int(user_id)
            if not adalah_pembuat and not boleh_memeriksa_cop(user_level):
                return app_error(
                    ErrorCode.FORBIDDEN,
                    "Certificate of payment hanya dapat diubah oleh "
                    "pembuatnya, atau yang berwenang memeriksanya.",
                    403,
                )

            if lama.get("isChecked"):
                return app_error(
                    ErrorCode.VALIDATION,
                    "Certificate of payment ini sudah diperiksa. Cabut "
                    "pemeriksaannya lebih dahulu bila memang perlu diubah.",
                    409,
                )

            # Menyunting boleh mengubah periodenya, tetapi tidak boleh
            # mengosongkannya — dokumen yang sudah terbit tanpa periode
            # sama tak terbacanya dengan yang dibuat tanpa periode.
            if "periodStart" in data or "periodEnd" in data:
                gabung = {
                    "periodStart": data.get("periodStart", lama.get("periodStart")),
                    "periodEnd": data.get("periodEnd", lama.get("periodEnd")),
                }
                galat_periode = CertificateOfPaymentController._periksa_periode(gabung)
                if galat_periode:
                    return galat_periode

            meta = {
                k: data[k]
                for k in ("date", "periodStart", "periodEnd", "note")
                if k in data and data[k] is not None
            }
            if meta:
                hasil = await CertificateOfPaymentRepository.update_meta(
                    cop_id, meta, user_id
                )
                if "error" in hasil:
                    return hasil

            if data.get("items") is not None:
                siap, galat = await CertificateOfPaymentController._siapkan_items(
                    int(lama["purchaseOrderID"]),
                    data["items"],
                    abaikan_cop_id=cop_id,
                )
                if galat:
                    return galat
                hasil = await CertificateOfPaymentRepository.ganti_items(
                    cop_id, siap, user_id
                )
                if "error" in hasil:
                    return hasil

            return {"message": "Certificate of payment diperbarui"}
        except Exception as e:
            log_error(f"Gagal mengubah CoP: {str(e)}")
            return internal_error()

    # ------------------------------------------------------------------
    # Periksa & setujui
    # ------------------------------------------------------------------

    @staticmethod
    async def set_checked(
        cop_id: int,
        checked: bool,
        user_id: int,
        user_level: int = 1,
        departments: set | None = None,
    ):
        """Tandai CoP sudah/belum diperiksa."""
        try:
            if not boleh_memeriksa_cop(user_level, departments):
                return app_error(
                    ErrorCode.FORBIDDEN,
                    "Pemeriksaan hanya dapat dilakukan engineering level 2 "
                    "ke atas.",
                    403,
                )

            cop = await CertificateOfPaymentRepository.get_by_id(cop_id)
            if isinstance(cop, dict) and "error" in cop:
                return cop

            # Pembuatnya tidak memeriksa sendiri.
            #
            # Pemeriksaan ada untuk menghadirkan mata kedua atas volume yang
            # dicatat; yang mencatat dan memeriksa sendiri mengembalikannya
            # menjadi satu tangan.
            if checked and not boleh_menyetujui_sendiri(user_level):
                if int(cop.get("createdBy") or 0) == int(user_id):
                    return app_error(
                        ErrorCode.SELF_APPROVAL_FORBIDDEN,
                        "Certificate of payment tidak dapat diperiksa oleh "
                        "pembuatnya sendiri.",
                        403,
                    )

            return await CertificateOfPaymentRepository.set_checked(
                cop_id, checked, user_id
            )
        except Exception as e:
            log_error(f"Gagal menandai pemeriksaan CoP: {str(e)}")
            return internal_error()

    @staticmethod
    async def approve(cop_id: int, user_id: int, user_level: int = 1):
        """Setujui CoP — tahap terakhir."""
        try:
            if not boleh_menyetujui_cop(user_level):
                return app_error(
                    ErrorCode.FORBIDDEN,
                    "Persetujuan hanya dapat dilakukan level 3 ke atas.",
                    403,
                )

            cop = await CertificateOfPaymentRepository.get_by_id(cop_id)
            if isinstance(cop, dict) and "error" in cop:
                return cop

            if cop.get("isApproved"):
                return app_error(
                    ErrorCode.VALIDATION,
                    "Certificate of payment ini sudah disetujui.",
                    409,
                )

            # Harus SUDAH DIPERIKSA.
            if not cop.get("isChecked"):
                return app_error(
                    ErrorCode.VALIDATION,
                    "Certificate of payment belum diperiksa. Mintakan "
                    "pemeriksaan lebih dahulu.",
                    400,
                )

            if not boleh_menyetujui_sendiri(user_level):
                if int(cop.get("createdBy") or 0) == int(user_id):
                    return app_error(
                        ErrorCode.SELF_APPROVAL_FORBIDDEN,
                        "Certificate of payment tidak dapat disetujui oleh "
                        "pembuatnya sendiri.",
                        403,
                    )
                # Pemeriksa tidak menyetujui yang diperiksanya sendiri —
                # penjagaan yang sama seperti pada purchase order, dan karena
                # alasan yang sama: dua tahap yang dikerjakan satu orang
                # berturut-turut bukan dua tangan.
                pemeriksa = cop.get("checkedBy")
                if pemeriksa is not None and int(pemeriksa) == int(user_id):
                    return app_error(
                        ErrorCode.PO_CHECKER_IS_APPROVER,
                        "Certificate of payment tidak dapat disetujui oleh "
                        "pemeriksanya sendiri.",
                        403,
                    )

            return await CertificateOfPaymentRepository.approve(cop_id, user_id)
        except Exception as e:
            log_error(f"Gagal menyetujui CoP: {str(e)}")
            return internal_error()

    # ------------------------------------------------------------------
    # Syarat SPK: uang muka, retensi, PPh — beserta pagunya
    # ------------------------------------------------------------------

    @staticmethod
    async def _syarat_spk(
        purchase_order_id: int, cop_id: int | None, kotor: Decimal
    ) -> Dict[str, Any]:
        """
        Syarat pembayaran kontrak beserta SISA yang masih boleh dipotong.

        MENGAPA UANG MUKA DIPOTONG SETIAP PERIODE

        Uang muka dibayarkan di depan, lalu dikembalikan sedikit demi sedikit
        dari tiap pembayaran progres. Bila 20% dibayarkan di depan dan tiap
        progres dipotong 20% dari nilainya, maka ketika progres mencapai
        100% jumlah yang telah dikembalikan tepat 20% dari kontrak — persis
        sebesar uang muka itu. Perhitungannya menutup sendiri; tidak ada
        yang perlu diakali pada periode terakhir.

        Retensi berjalan dengan pola yang sama, hanya tujuannya berbeda:
        ia ditahan sampai masa pemeliharaan berakhir, bukan dikembalikan.

        PAGU

        Keduanya punya batas: pengembalian uang muka seluruh CoP tidak boleh
        melebihi uang muka yang benar-benar dibayarkan, dan retensi tidak
        boleh melebihi retensi yang disepakati. Batas itu tidak akan
        tersentuh selama potongannya proporsional — ia menjaga yang DIKETIK
        TANGAN, karena di situlah kelebihannya mungkin terjadi.
        """
        spk = await PurchaseOrderRepository.get_by_id(purchase_order_id)
        if not spk or (isinstance(spk, dict) and "error" in spk):
            return {}

        tarif_pph = _d(spk.get("pphPercentage"))
        tarif_dp = _d(spk.get("dpPercentage"))
        tarif_ret = _d(spk.get("retentionPercentage"))

        nilai_kontrak = await CertificateOfPaymentRepository.nilai_kontrak(
            purchase_order_id
        )
        # CoP INI dikeluarkan dari akumulasi: potongannya sendiri bukan
        # pemakaian orang lain.
        sudah = await CertificateOfPaymentRepository.akumulasi_penyesuaian(
            purchase_order_id, kecuali_cop_id=cop_id
        )

        dp_pagu = nilai_kontrak * tarif_dp / 100
        ret_pagu = nilai_kontrak * tarif_ret / 100
        dp_lalu = sudah.get("deduction:uang_muka", Decimal("0"))
        ret_lalu = sudah.get("deduction:retensi", Decimal("0"))
        dp_sisa = max(dp_pagu - dp_lalu, Decimal("0"))
        ret_sisa = max(ret_pagu - ret_lalu, Decimal("0"))

        # Saran DIBATASI sisanya.
        #
        # Pada periode terakhir, 20% dari progres dapat melampaui uang muka
        # yang belum kembali — dan menyarankan angka yang pasti ditolak
        # server hanya membuat yang mengisi mencoba-coba sendiri.
        saran_dp = min(kotor * tarif_dp / 100, dp_sisa)
        saran_ret = min(kotor * tarif_ret / 100, ret_sisa)

        return {
            "pphCode": spk.get("pphCode"),
            "pphTaxObject": spk.get("pphTaxObject"),
            "pphPercentage": float(tarif_pph),
            "dpPercentage": float(tarif_dp),
            "retentionPercentage": float(tarif_ret),
            "nilaiKontrak": float(nilai_kontrak),
            # Uang muka: pagu, sudah dikembalikan, sisa.
            "dpPagu": float(dp_pagu),
            "dpTerpakai": float(dp_lalu),
            "dpSisa": float(dp_sisa),
            # Retensi: pagu, sudah ditahan, sisa.
            "retensiPagu": float(ret_pagu),
            "retensiTerpakai": float(ret_lalu),
            "retensiSisa": float(ret_sisa),
            "saranPph": float(kotor * tarif_pph / 100),
            "saranUangMuka": float(saran_dp),
            "saranRetensi": float(saran_ret),
        }

    # ------------------------------------------------------------------
    # Penyesuaian: potongan & tambahan
    # ------------------------------------------------------------------

    @staticmethod
    async def set_penyesuaian(
        cop_id: int,
        penyesuaian: List[Dict[str, Any]],
        user_id: int,
        user_level: int = 1,
        departments: set | None = None,
    ):
        """
        Ganti seluruh potongan & tambahan sebuah CoP.

        Yang mengisinya PEMERIKSA — di tahap inilah nilai rupiah mulai
        terlihat, dan orang lapangan memang tidak pernah menerimanya.

        Terkunci setelah DISETUJUI: nilai yang sudah disetujui adalah nilai
        yang akan ditagihkan, dan mengubahnya sesudahnya membuat yang
        menandatangani menyetujui angka yang bukan lagi yang dibacanya.
        """
        try:
            if not boleh_memeriksa_cop(user_level, departments):
                return app_error(
                    ErrorCode.FORBIDDEN,
                    "Potongan dan tambahan hanya dapat diisi pemeriksa "
                    "(engineering level 2 ke atas).",
                    403,
                )

            cop = await CertificateOfPaymentRepository.get_by_id(cop_id)
            if isinstance(cop, dict) and "error" in cop:
                return cop

            if cop.get("isApproved"):
                return app_error(
                    ErrorCode.VALIDATION,
                    "Certificate of payment ini sudah disetujui; potongan "
                    "dan tambahannya tidak dapat diubah lagi.",
                    409,
                )

            siap, galat = await CertificateOfPaymentController._siapkan_penyesuaian(
                penyesuaian,
                _d(cop.get("grossAmount")),
                # `.get`, bukan indeks langsung: CoP yang dibaca lewat
                # jalur lain belum tentu membawa kolom ini, dan yang
                # meledak di sini menggagalkan penyimpanan yang sah.
                int(cop.get("purchaseOrderID") or 0) or None,
                cop_id,
            )
            if galat:
                return galat

            hasil = await CertificateOfPaymentRepository.ganti_penyesuaian(
                cop_id, siap, user_id
            )
            if isinstance(hasil, dict) and "error" in hasil:
                return hasil

            return {
                "message": "Potongan dan tambahan diperbarui",
                "grossAmount": float(hasil["grossAmount"]),
                "deductionTotal": float(hasil["deductionTotal"]),
                "additionTotal": float(hasil["additionTotal"]),
                "netAmount": float(hasil["netAmount"]),
            }
        except Exception as e:
            log_error(f"Gagal menyimpan penyesuaian CoP: {str(e)}")
            return internal_error()

    @staticmethod
    async def _siapkan_penyesuaian(
        masuk: List[Dict[str, Any]],
        kotor: Decimal,
        purchase_order_id: int | None = None,
        cop_id: int | None = None,
    ):
        """
        Periksa kiriman layar. Kembalikan (baris_siap, galat).

        Empat penjagaan:

          1. jenis & kategori harus dikenali — kategori karangan membuat
             pembukuan tidak dapat memetakannya;
          2. `lain_lain` WAJIB berlabel — tanpa itu barisnya tidak berarti
             apa pun bagi yang membacanya bulan depan;
          3. nominal harus positif — tanda ditentukan `kind`, dan nominal
             minus adalah cara paling mudah membuat potongan terjumlah
             sebagai tambahan tanpa ada yang menyadarinya;
          4. nilai bersih tidak boleh negatif — CoP yang potongannya
             melebihi nilai pekerjaannya berarti pemasok berutang kepada
             perusahaan, dan itu bukan yang dinyatakan sebuah berita acara
             progres.
        """
        siap: List[Dict[str, Any]] = []
        potongan = Decimal("0")
        tambahan = Decimal("0")

        for p in masuk or []:
            jenis = (p.get("kind") or "").strip()
            if jenis not in ("deduction", "addition"):
                return None, app_error(
                    ErrorCode.VALIDATION,
                    "Jenis penyesuaian tidak dikenali.",
                    400,
                )

            kategori = (p.get("category") or "").strip()
            sah = (
                KATEGORI_POTONGAN if jenis == "deduction" else KATEGORI_TAMBAHAN
            )
            if kategori not in sah:
                return None, app_error(
                    ErrorCode.VALIDATION,
                    f"Kategori '{kategori}' tidak berlaku untuk "
                    + ("potongan." if jenis == "deduction" else "tambahan."),
                    400,
                )

            label = (p.get("label") or "").strip()
            if kategori == "lain_lain" and not label:
                return None, app_error(
                    ErrorCode.VALIDATION,
                    "Baris lain-lain harus diberi keterangan.",
                    400,
                )

            nominal = _d(p.get("amount"))
            if nominal <= 0:
                return None, app_error(
                    ErrorCode.VALIDATION,
                    "Nominal penyesuaian harus lebih dari nol.",
                    400,
                )

            if jenis == "deduction":
                potongan += nominal
            else:
                tambahan += nominal

            siap.append(
                {
                    "kind": jenis,
                    "category": kategori,
                    "label": label or None,
                    "amount": nominal,
                    "note": p.get("note"),
                }
            )

        # ---- pagu uang muka & retensi ----
        #
        # Sama prinsipnya dengan pagu volume: yang sudah dipotong pada CoP
        # sebelumnya dijumlahkan, dan yang melampaui kesepakatannya ditolak
        # beserta angka sisanya.
        #
        # Selama potongannya proporsional, batas ini tidak akan tersentuh —
        # 20% dari tiap progres berjumlah tepat 20% dari kontrak ketika
        # pekerjaannya selesai. Yang dijaganya adalah angka yang DIKETIK
        # TANGAN, karena di situlah kelebihannya mungkin terjadi.
        if purchase_order_id:
            syarat = await CertificateOfPaymentController._syarat_spk(
                purchase_order_id, cop_id, kotor
            )
            for kategori, kunci_sisa, sebutan in (
                ("uang_muka", "dpSisa", "pengembalian uang muka"),
                ("retensi", "retensiSisa", "retensi"),
            ):
                diminta = sum(
                    (
                        p["amount"]
                        for p in siap
                        if p["kind"] == "deduction" and p["category"] == kategori
                    ),
                    Decimal("0"),
                )
                if diminta <= 0:
                    continue
                sisa = _d(syarat.get(kunci_sisa))
                # Pagu nol berarti syaratnya memang tidak tercatat di SPK —
                # dibiarkan lewat supaya SPK lama tetap dapat dipotong.
                pagu = _d(syarat.get("dpPagu" if kategori == "uang_muka" else "retensiPagu"))
                if pagu <= 0:
                    continue
                if diminta > sisa:
                    return None, app_error(
                        ErrorCode.VALIDATION,
                        f"Potongan {sebutan} ({diminta:,.2f}) melebihi sisanya "
                        f"({sisa:,.2f}). Seluruhnya {pagu:,.2f}, dan sebagian "
                        "sudah dipotong pada certificate of payment sebelumnya.",
                        400,
                    )

        bersih = kotor - potongan + tambahan
        if bersih < 0:
            return None, app_error(
                ErrorCode.VALIDATION,
                f"Potongan ({potongan:g}) melebihi nilai pekerjaan beserta "
                f"tambahannya ({kotor + tambahan:g}). Nilai bersih certificate "
                "of payment tidak boleh negatif.",
                400,
            )

        return siap, None

    # ------------------------------------------------------------------
    # Data pencetakan (CoP + BAP)
    # ------------------------------------------------------------------

    @staticmethod
    async def data_cetak(cop_id: int, user_level: int = 1):
        """
        Susun seluruh angka yang dicetak pada CoP dan BAP.

        BENTUK YANG DIIKUTI

        Mengikuti berkas Excel yang selama ini dipakai, termasuk kolom BOBOT
        pada BAP: bobot sebuah baris adalah porsi nilainya terhadap seluruh
        nilai kontrak, dan bobot progres adalah bobot itu dikali persentase
        volumenya. Jumlah seluruh bobot akhir = persentase progres kontrak,
        dan itulah angka yang muncul di baris "Progress Kontrak" pada CoP.

        YANG DICETAK HARUS TETAP SAMA BILA DICETAK ULANG

        "Volume sebelumnya" dibatasi NOMOR CoP, bukan "semua kecuali yang
        ini". Mencetak ulang CoP nomor 2 setelah nomor 3 terbit harus
        menghasilkan lembar yang sama persis seperti saat ia diterbitkan.
        """
        try:
            if not boleh_melihat_nilai_cop(user_level):
                return app_error(
                    ErrorCode.FORBIDDEN,
                    "Dokumen ini memuat nilai rupiah dan hanya dapat diunduh "
                    "level 2 ke atas.",
                    403,
                )

            cop = await CertificateOfPaymentRepository.get_by_id(cop_id)
            if isinstance(cop, dict) and "error" in cop:
                return cop

            po_id = int(cop["purchaseOrderID"])
            spk = await PurchaseOrderRepository.get_by_id(po_id)
            if not spk or (isinstance(spk, dict) and "error" in spk):
                return app_error(ErrorCode.NOT_FOUND, "SPK tidak ditemukan", 404)

            # Dijaga DI SINI juga, bukan hanya saat CoP dibuat.
            #
            # Aturan ini lahir belakangan; CoP yang terlanjur tersimpan
            # sebelum jenis A dikecualikan tetap ada di basis data, dan
            # tanpa penjagaan di sini ia masih dapat dicetak sebagai
            # dokumen resmi.
            if not CertificateOfPaymentController.adalah_spk(spk):
                return app_error(
                    ErrorCode.VALIDATION,
                    "Dokumen ini bukan SPK yang memakai certificate of "
                    "payment, sehingga tidak dapat dicetak.",
                    400,
                )

            nomor = int(cop["number"])
            baris_kontrak = await CertificateOfPaymentRepository.baris_kontrak(po_id)
            sebelumnya = await CertificateOfPaymentRepository.cop_sebelumnya(
                po_id, nomor
            )
            riwayat = await CertificateOfPaymentRepository.riwayat_pembayaran(
                po_id, nomor
            )

            # Volume periode ini, per baris.
            periode_ini: Dict[int, Decimal] = {}
            catatan_baris: Dict[int, str] = {}
            for i in cop.get("items") or []:
                kunci = int(i["purchaseOrderItemID"])
                periode_ini[kunci] = periode_ini.get(kunci, Decimal("0")) + _d(
                    i["quantity"]
                )
                if i.get("remarks"):
                    catatan_baris[kunci] = i["remarks"]

            # ---- nilai kontrak: induk + seluruh adendum yang disetujui ----
            nilai_induk = Decimal("0")
            nilai_adendum = Decimal("0")
            for b in baris_kontrak:
                nilai = _d(b["quantity"]) * _d(b["price"])
                if b["addendumNumber"] is None:
                    nilai_induk += nilai
                else:
                    nilai_adendum += nilai
            nilai_kontrak = nilai_induk + nilai_adendum

            # ---- baris BAP ----
            def _bagi(a: Decimal, b: Decimal) -> Decimal:
                return (a / b) if b else Decimal("0")

            bap: List[Dict[str, Any]] = []
            for urut, b in enumerate(baris_kontrak, start=1):
                vol_kontrak = _d(b["quantity"])
                harga = _d(b["price"])
                total_baris = vol_kontrak * harga
                bobot = _bagi(total_baris, nilai_kontrak)

                vol_lalu = sebelumnya.get(b["id"], Decimal("0"))
                vol_kini = periode_ini.get(b["id"], Decimal("0"))
                vol_akum = vol_lalu + vol_kini

                pers_lalu = _bagi(vol_lalu, vol_kontrak)
                pers_kini = _bagi(vol_kini, vol_kontrak)
                pers_akum = _bagi(vol_akum, vol_kontrak)

                bap.append(
                    {
                        "no": urut,
                        "pekerjaan": b["task"] or "-",
                        "keterangan": b["remarks_1"],
                        "adendum": b["addendumNumber"],
                        "volumeKontrak": float(vol_kontrak),
                        "satuan": b["unit"] or "",
                        "hargaSatuan": float(harga),
                        "total": float(total_baris),
                        "bobot": float(bobot),
                        "volumeSebelumnya": float(vol_lalu),
                        "persentaseSebelumnya": float(pers_lalu),
                        "bobotSebelumnya": float(bobot * pers_lalu),
                        "volumePeriodeIni": float(vol_kini),
                        "persentaseSaatIni": float(pers_kini),
                        "bobotSaatIni": float(bobot * pers_kini),
                        "volumeAkumulatif": float(vol_akum),
                        "persentaseAkumulatif": float(pers_akum),
                        "bobotAkumulatif": float(bobot * pers_akum),
                        "catatan": catatan_baris.get(b["id"]),
                    }
                )

            bobot_lalu = sum((Decimal(str(r["bobotSebelumnya"])) for r in bap), Decimal("0"))
            bobot_kini = sum((Decimal(str(r["bobotSaatIni"])) for r in bap), Decimal("0"))
            bobot_akum = sum((Decimal(str(r["bobotAkumulatif"])) for r in bap), Decimal("0"))

            # ---- ringkasan CoP ----
            kotor = _d(cop.get("grossAmount"))
            potongan = _d(cop.get("deductionTotal"))
            tambahan = _d(cop.get("additionTotal"))
            bersih = _d(cop.get("netAmount"))

            # PPN mengikuti tarif SPK-nya, bukan angka tetap di kode.
            #
            # Tarifnya pernah 10% dan kini 11%; menuliskannya di sini berarti
            # setiap dokumen lama tercetak ulang dengan tarif yang keliru.
            tarif_ppn = _d(spk.get("ppn"))
            ppn = bersih * tarif_ppn / Decimal("100")

            penyesuaian = []
            for a in cop.get("adjustments") or []:
                nominal = _d(a["amount"])
                penyesuaian.append(
                    {
                        "kind": a["kind"],
                        "category": a["category"],
                        "label": a.get("label"),
                        "amount": float(nominal),
                        # Persentase terhadap nilai pekerjaan periode ini —
                        # begitulah kolom tengah pada lembar lama dibaca.
                        "persenDariKotor": float(_bagi(nominal, kotor)),
                    }
                )

            # ---- pengurangan sebagai TIGA BARIS TETAP ----
            #
            # Lembar Excel yang selama ini dipakai selalu mencetak
            # "Pengembalian Down Payment", "Retensi", dan "PPh" — bahkan bila
            # nilainya nol, di mana kolomnya berisi tanda pisah. Yang
            # membacanya membaca ketiganya sebagai daftar periksa: baris yang
            # HILANG tidak terbaca sebagai "tidak dipotong" melainkan sebagai
            # "terlupa dipotong", dan itulah yang ditanyakan balik ke lapangan.
            #
            # Karena itu ketiganya dibentuk di sini, bukan diserahkan pada
            # perulangan daftar penyesuaian. Kategori di luar ketiganya
            # (denda, lain-lain) tetap dicetak menyusul apa adanya.
            POKOK = ("uang_muka", "retensi", "pph")
            baku: Dict[str, Decimal] = {k: Decimal("0") for k in POKOK}
            potongan_lain: List[Dict[str, Any]] = []
            for a in cop.get("adjustments") or []:
                if a["kind"] != "deduction":
                    continue
                nominal = _d(a["amount"])
                if a["category"] in baku:
                    baku[a["category"]] += nominal
                else:
                    potongan_lain.append(
                        {
                            "category": a["category"],
                            "label": a.get("label"),
                            "amount": float(nominal),
                            "persenDariKotor": float(_bagi(nominal, kotor)),
                        }
                    )

            pengurangan_pokok = [
                {
                    "category": k,
                    "amount": float(baku[k]),
                    "persenDariKotor": float(_bagi(baku[k], kotor)),
                }
                for k in POKOK
            ]

            # Uang muka yang DITERIMA di muka — baris pertama pada akumulasi.
            #
            # Ia bukan pembayaran progres, tetapi tetap uang yang sudah
            # berpindah; akumulasi yang tidak menyebutnya membuat jumlah di
            # lembar ini berselisih dengan catatan penerimaan pemasok.
            dp_kontrak = nilai_kontrak * _d(spk.get("dpPercentage")) / Decimal("100")

            return {
                "cop": {
                    "id": cop["id"],
                    "name": cop["name"],
                    "number": nomor,
                    "date": cop["date"],
                    "periodStart": cop.get("periodStart"),
                    "periodEnd": cop.get("periodEnd"),
                    "note": cop.get("note"),
                    "projectName": cop["projectName"],
                    "createdByName": cop.get("createdByName"),
                    "checkedByName": cop.get("checkedByName"),
                    "approvedByName": cop.get("approvedByName"),
                    "createdByPosition": cop.get("createdByPosition"),
                    "checkedByPosition": cop.get("checkedByPosition"),
                    "approvedByPosition": cop.get("approvedByPosition"),
                    "checkedAt": cop.get("checkedAt"),
                    "approvedAt": cop.get("approvedAt"),
                    "isApproved": bool(cop.get("isApproved")),
                },
                "spk": {
                    "name": spk.get("name"),
                    "supplierName": spk.get("supplierName") or spk.get("supplier_name"),
                    "purchaseType": spk.get("purchaseType"),
                    "dpPercentage": float(_d(spk.get("dpPercentage"))),
                    "retentionPercentage": float(_d(spk.get("retentionPercentage"))),
                    "pphPercentage": float(_d(spk.get("pphPercentage"))),
                    "ppn": float(tarif_ppn),
                },
                "kontrak": {
                    "induk": float(nilai_induk),
                    "adendum": float(nilai_adendum),
                    "total": float(nilai_kontrak),
                    "adaAdendum": nilai_adendum > 0,
                },
                "bap": bap,
                "bapTotal": {
                    "total": float(nilai_kontrak),
                    "bobot": float(_bagi(nilai_kontrak, nilai_kontrak)),
                    "bobotSebelumnya": float(bobot_lalu),
                    "bobotSaatIni": float(bobot_kini),
                    "bobotAkumulatif": float(bobot_akum),
                },
                "nilai": {
                    "kotor": float(kotor),
                    "persenProgres": float(bobot_kini),
                    "potongan": float(potongan),
                    "tambahan": float(tambahan),
                    "bersih": float(bersih),
                    "tarifPpn": float(tarif_ppn),
                    "ppn": float(ppn),
                    "totalDibayar": float(bersih + ppn),
                },
                "penyesuaian": penyesuaian,
                "pengurangan": {
                    "pokok": pengurangan_pokok,
                    "lain": potongan_lain,
                },
                "dpKontrak": float(dp_kontrak),
                "riwayat": [
                    {
                        "number": r["number"],
                        "name": r["name"],
                        "date": r["date"],
                        "gross": float(_d(r["grossAmount"])),
                        "net": float(_d(r["netAmount"])),
                        "iniSendiri": int(r["number"]) == nomor,
                    }
                    for r in riwayat
                ],
                "riwayatTotal": float(
                    sum((_d(r["netAmount"]) for r in riwayat), Decimal("0"))
                ),
            }
        except Exception as e:
            log_error(f"Gagal menyusun data cetak CoP: {str(e)}")
            return internal_error()

    # ------------------------------------------------------------------
    # Hapus & baca
    # ------------------------------------------------------------------

    @staticmethod
    async def delete(cop_id: int, user_id: int, user_level: int = 1):
        """
        Hapus CoP.

        Yang sudah DISETUJUI tidak dapat dihapus di bawah level 4: ia sudah
        menjadi dasar penagihan, dan volumenya sudah masuk hitungan pihak
        lain.
        """
        try:
            cop = await CertificateOfPaymentRepository.get_by_id(cop_id)
            if isinstance(cop, dict) and "error" in cop:
                return cop

            if cop.get("isApproved") and int(user_level or 1) < 4:
                return app_error(
                    ErrorCode.FORBIDDEN,
                    "Certificate of payment yang sudah disetujui hanya dapat "
                    "dihapus level 4 ke atas.",
                    403,
                )

            adalah_pembuat = int(cop.get("createdBy") or 0) == int(user_id)
            if not adalah_pembuat and int(user_level or 1) < 3:
                return app_error(
                    ErrorCode.FORBIDDEN,
                    "Hanya pembuatnya, atau level 3 ke atas, yang dapat "
                    "menghapus certificate of payment.",
                    403,
                )

            return await CertificateOfPaymentRepository.soft_delete(cop_id, user_id)
        except Exception as e:
            log_error(f"Gagal menghapus CoP: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_by_id(cop_id: int, user_level: int = 1):
        hasil = await CertificateOfPaymentRepository.get_by_id(cop_id)
        if isinstance(hasil, dict) and "error" in hasil:
            return hasil

        # Syarat pajak & pembayaran DIBAWA DARI SPK, tidak diketik ulang.
        #
        # Kode PPh, objek pajaknya, dan tarifnya sudah tercatat saat purchase
        # order dibuat. Meminta pemeriksa mengetiknya lagi tiap periode
        # berarti angka yang sama disimpan di dua tempat — dan yang berbeda
        # di antara keduanya tidak menimbulkan galat apa pun, hanya potongan
        # yang keliru pada periode kelima.
        #
        # Yang dikirim SARANNYA, bukan potongan yang sudah jadi: pemeriksa
        # tetap yang memutuskan ia dipotong periode ini atau tidak.
        if boleh_melihat_nilai_cop(user_level):
            try:
                hasil["spkSyarat"] = await CertificateOfPaymentController._syarat_spk(
                    int(hasil["purchaseOrderID"]),
                    cop_id,
                    _d(hasil.get("grossAmount")),
                )
            except Exception as e:
                # Gagal membaca syarat SPK tidak boleh menggagalkan pembacaan
                # CoP-nya; yang hilang hanya sarannya.
                log_error(f"Gagal membaca syarat SPK untuk CoP: {str(e)}")

        return CertificateOfPaymentController.saring_nilai(hasil, user_level)

    @staticmethod
    async def get_all(
        purchase_order_id: int | None = None,
        project_name: str | None = None,
        created_by: int | None = None,
        page: int = 0,
        page_size: int = 20,
        user_level: int = 1,
        keyword: str | None = None,
    ):
        hasil = await CertificateOfPaymentRepository.get_all(
            purchase_order_id, project_name, created_by, page, page_size, keyword
        )
        if isinstance(hasil, dict) and "error" in hasil:
            return hasil
        return CertificateOfPaymentController.saring_nilai(hasil, user_level)
