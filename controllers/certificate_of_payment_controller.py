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
    boleh_menyetujui_bap_cop,
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

    #: Material PO-F yang TETAP dilayani CoP meski dokumennya PURCHASE ORDER.
    #:
    #: Beton dikirim bertahap sepanjang pekerjaan dan ditagih menurut kubikasi
    #: yang sudah dituang — bentuk penagihan yang sama dengan pekerjaan
    #: bertahap, sehingga berita acara progresnya menyatakan hal yang sama
    #: pula. Material lain PO-F diserahkan sekali dan ditagih sekali; berita
    #: acara progres atasnya tidak menyatakan apa pun.
    #:
    #: Ditulis sebagai daftar, bukan perbandingan tunggal: material berikutnya
    #: yang ditagih bertahap cukup ditambahkan di sini.
    MATERIAL_BER_COP = frozenset({"beton"})

    @staticmethod
    def melayani_cop(po: Dict[str, Any]) -> bool:
        """
        Certificate of Payment melayani dokumen ini?

        BUKAN sekadar "apakah ini SPK". Sebagian besar memang SPK, tetapi
        pembelian BETON terbit sebagai PURCHASE ORDER dan tetap ditagih
        bertahap — lihat `MATERIAL_BER_COP`. Karena itu pertanyaannya
        dirumuskan sebagai "dilayani CoP", bukan sebagai jenis dokumennya:
        nama yang menyebut jenis akan menjadi keliru pada dokumen pertama
        yang menyimpang darinya, dan yang membacanya akan menyimpulkan
        aturan yang salah.

        Jenis dokumennya sendiri tetap ditentukan `_awalan_dokumen` milik
        purchase order — SATU-SATUNYA tempat itu diputuskan. Menyalin
        daftarnya ke sini akan membuat keduanya berselisih pada jenis
        berikutnya yang ditambahkan, dan yang tertinggal tidak menimbulkan
        galat: hanya CoP yang diam-diam menolak SPK yang sah, atau menerima
        purchase order yang bukan haknya.
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

        # Material PO-F yang ditagih bertahap dilayani meski dokumennya PO.
        #
        # Diperiksa SEBELUM `_awalan_dokumen`, sebab jawabannya di sana sudah
        # pasti "PO" — dan memang benar begitu: yang terbit untuk beton
        # adalah purchase order, dan lembarnya tidak berubah karenanya.
        # Yang ditambahkan di sini hanya haknya atas berita acara progres.
        if jenis == "F":
            material = (
                str((custom or {}).get("materialType") or "").strip().lower()
            )
            if material in CertificateOfPaymentController.MATERIAL_BER_COP:
                return True

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
                if not CertificateOfPaymentController.melayani_cop(po):
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
            if not CertificateOfPaymentController.melayani_cop(spk):
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
            if not CertificateOfPaymentController.melayani_cop(spk):
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

            # Nomor dokumen dan namanya TIDAK disusun di sini.
            #
            # Keduanya diambil di dalam transaksi penyimpanan, sedekat mungkin
            # dengan penyisipannya. Disusun di sini, dua permintaan yang datang
            # bersamaan membaca angka terakhir yang sama dan menghasilkan nama
            # yang sama — lalu yang kedua ditolak kolom unik dengan galat yang
            # tidak menyebut sebabnya.
            hasil = await CertificateOfPaymentRepository.create(
                {
                    "number": nomor,
                    "purchaseOrderID": induk_id,
                    # Vendor diambil dari SPK-nya, bukan dari kiriman layar:
                    # penomoran mengurut per vendor, dan vendor yang keliru
                    # menempatkan dokumen pada deret milik pihak lain.
                    "supplierID": spk.get("supplierID"),
                    "projectName": data.get("projectName") or spk.get("projectName") or "",
                    "date": data.get("date"),
                    "periodStart": data.get("periodStart"),
                    "periodEnd": data.get("periodEnd"),
                    "note": data.get("note"),
                },
                siap,
                user_id,
            )

            # Beri tahu para penyetuju: ada BAP baru yang menunggu persetujuan.
            #
            # Efek samping, BUKAN bagian dari pembuatannya: tugas terpisah dan
            # dibungkus try, supaya push yang gagal tidak pernah menggagalkan
            # penyimpanan CoP yang sudah benar. Pembuatnya dikecualikan — BAP
            # tidak disetujui oleh yang membuatnya.
            if isinstance(hasil, dict) and "error" not in hasil:
                try:
                    import asyncio
                    from repository.push_subscription_repository import (
                        PushSubscriptionRepository,
                    )
                    from utils.webpush import kirim_ke_pengguna, push_aktif

                    if push_aktif():
                        penyetuju = await PushSubscriptionRepository.penyetuju_ids(
                            kecuali_user_ids=[user_id]
                        )
                        if penyetuju:
                            nama = hasil.get("name") or "CoP"
                            proyek = (
                                data.get("projectName")
                                or spk.get("projectName")
                                or ""
                            )
                            label = nama + (f" — {proyek}" if proyek else "")
                            cop_id = hasil.get("certificateOfPaymentID")
                            asyncio.create_task(
                                kirim_ke_pengguna(
                                    penyetuju,
                                    judul="BAP minta disetujui",
                                    pesan=f"{label} — BAP menunggu persetujuan "
                                    "sebelum harga dapat diisi.",
                                    url=f"/Certificate-of-payment/View/{cop_id}",
                                    tag=f"cop-bap-approve-{cop_id}",
                                )
                            )
                except Exception as push_err:
                    log_error(
                        f"Gagal menjadwalkan notifikasi BAP baru: {str(push_err)}"
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
        Sunting CoP — hanya SELAMA BAP-nya belum disetujui.

        Setelah BAP disetujui, volumenya sudah menjadi progres yang diakui
        sah dan menjadi dasar harga diisi; mengubahnya diam-diam membuat yang
        menyetujui BAP mengesahkan angka yang bukan lagi yang dibacanya.
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

            if lama.get("isBapApproved"):
                return app_error(
                    ErrorCode.VALIDATION,
                    "BAP-nya sudah disetujui. Batalkan persetujuan BAP lebih "
                    "dahulu bila volumenya memang perlu diubah.",
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
    # Empat tahap: buat BAP -> setujui BAP -> buat CoP -> setujui CoP
    # ------------------------------------------------------------------

    @staticmethod
    async def approve_bap(
        cop_id: int,
        approve: bool,
        user_id: int,
        user_level: int = 1,
    ):
        """
        Setujui / batalkan BAP — GERBANG PERTAMA.

        Level 4 ke atas. Inilah yang mengesahkan progres lapangan; baru
        SESUDAHNYA harga boleh diisi. Pembuatnya sendiri tidak menyetujuinya
        (kecuali level yang boleh setuju-sendiri) — persetujuan ada untuk
        menghadirkan tangan kedua atas volume yang dicatat.
        """
        try:
            if not boleh_menyetujui_bap_cop(user_level):
                return app_error(
                    ErrorCode.FORBIDDEN,
                    "Persetujuan BAP hanya dapat dilakukan level 4 ke atas.",
                    403,
                )

            cop = await CertificateOfPaymentRepository.get_by_id(cop_id)
            if isinstance(cop, dict) and "error" in cop:
                return cop

            if approve and cop.get("isBapApproved"):
                return app_error(
                    ErrorCode.VALIDATION,
                    "BAP ini sudah disetujui.",
                    409,
                )

            # Membatalkan persetujuan BAP setelah CoP disetujui berarti
            # menarik dasar sebuah tagihan yang sudah terbit — tidak lewat
            # sini, melainkan lewat penghapusan yang tercatat.
            if not approve and cop.get("isApproved"):
                return app_error(
                    ErrorCode.VALIDATION,
                    "CoP sudah disetujui; persetujuan BAP tidak dapat "
                    "dibatalkan lagi.",
                    409,
                )

            if approve and not boleh_menyetujui_sendiri(user_level):
                if int(cop.get("createdBy") or 0) == int(user_id):
                    return app_error(
                        ErrorCode.SELF_APPROVAL_FORBIDDEN,
                        "BAP tidak dapat disetujui oleh pembuatnya sendiri.",
                        403,
                    )

            hasil = await CertificateOfPaymentRepository.bap_approve(
                cop_id, approve, user_id
            )

            # Kabar ke pembuat CoP: BAP-nya disetujui, harga sekarang boleh
            # diisi. Hanya saat DISETUJUI (bukan saat dibatalkan), dan pembuat
            # dikecualikan bila ia sendiri yang menyetujui.
            if approve and isinstance(hasil, dict) and "error" not in hasil:
                try:
                    import asyncio
                    from utils.webpush import kirim_ke_pengguna, push_aktif

                    if push_aktif():
                        pembuat = cop.get("createdBy")
                        if pembuat is not None and int(pembuat) != int(user_id):
                            nama = cop.get("name") or f"CoP #{cop_id}"
                            proyek = cop.get("projectName") or ""
                            label = nama + (f" — {proyek}" if proyek else "")
                            asyncio.create_task(
                                kirim_ke_pengguna(
                                    [int(pembuat)],
                                    judul="BAP disetujui",
                                    pesan=f"{label} — BAP sudah disetujui. "
                                    "Silakan isi harga dan potongannya.",
                                    url=f"/Certificate-of-payment/View/{cop_id}",
                                    tag=f"cop-bap-approved-{cop_id}",
                                )
                            )
                except Exception as push_err:
                    log_error(
                        f"Gagal menjadwalkan notifikasi BAP disetujui: "
                        f"{str(push_err)}"
                    )

            return hasil
        except Exception as e:
            log_error(f"Gagal menyetujui BAP CoP: {str(e)}")
            return internal_error()

    @staticmethod
    async def set_checked(
        cop_id: int,
        checked: bool,
        user_id: int,
        user_level: int = 1,
        departments: set | None = None,
    ):
        """
        Tandai CoP DIBUAT / batalkan pembuatannya — tahap harga & potongan.

        Yang menstempelnya adalah PEMBUAT CoP (engineering level 2 ke atas),
        dan HANYA setelah BAP-nya disetujui: sebelum itu tidak ada nilai
        rupiah yang boleh disentuh sama sekali.
        """
        try:
            if not boleh_memeriksa_cop(user_level, departments):
                return app_error(
                    ErrorCode.FORBIDDEN,
                    "Pembuatan CoP hanya dapat dilakukan engineering level 2 "
                    "ke atas.",
                    403,
                )

            cop = await CertificateOfPaymentRepository.get_by_id(cop_id)
            if isinstance(cop, dict) and "error" in cop:
                return cop

            # GERBANG BAP. CoP tidak dapat dibuat sebelum progresnya disahkan.
            if checked and not cop.get("isBapApproved"):
                return app_error(
                    ErrorCode.VALIDATION,
                    "BAP belum disetujui. CoP baru dapat dibuat setelah "
                    "progres lapangannya disetujui lebih dahulu.",
                    400,
                )

            hasil = await CertificateOfPaymentRepository.set_checked(
                cop_id, checked, user_id
            )

            # Kabar ke penyetuju: CoP sudah dibuat (harga terisi) dan menunggu
            # persetujuan final. Hanya saat DIBUAT (bukan saat dibatalkan).
            # Yang tidak dapat menyetujui CoP ini dikecualikan: pembuat CoP
            # (user_id), pembuat dokumennya, dan penyetuju BAP-nya — ketiganya
            # memang ditolak server bila mencoba menyetujui.
            if checked and isinstance(hasil, dict) and "error" not in hasil:
                try:
                    import asyncio
                    from repository.push_subscription_repository import (
                        PushSubscriptionRepository,
                    )
                    from utils.webpush import kirim_ke_pengguna, push_aktif

                    if push_aktif():
                        penyetuju = await PushSubscriptionRepository.penyetuju_ids(
                            kecuali_user_ids=[
                                user_id,
                                cop.get("createdBy"),
                                cop.get("bapApprovedBy"),
                            ]
                        )
                        if penyetuju:
                            nama = cop.get("name") or f"CoP #{cop_id}"
                            proyek = cop.get("projectName") or ""
                            label = nama + (f" — {proyek}" if proyek else "")
                            asyncio.create_task(
                                kirim_ke_pengguna(
                                    penyetuju,
                                    judul="CoP minta disetujui",
                                    pesan=f"{label} sudah dibuat dan menunggu "
                                    "persetujuan.",
                                    url=f"/Certificate-of-payment/View/{cop_id}",
                                    tag=f"cop-approve-{cop_id}",
                                )
                            )
                except Exception as push_err:
                    log_error(
                        f"Gagal menjadwalkan notifikasi CoP dibuat: "
                        f"{str(push_err)}"
                    )

            return hasil
        except Exception as e:
            log_error(f"Gagal menandai pembuatan CoP: {str(e)}")
            return internal_error()

    @staticmethod
    async def approve(cop_id: int, user_id: int, user_level: int = 1):
        """Setujui CoP — GERBANG TERAKHIR, level 4 ke atas."""
        try:
            if not boleh_menyetujui_cop(user_level):
                return app_error(
                    ErrorCode.FORBIDDEN,
                    "Persetujuan CoP hanya dapat dilakukan level 4 ke atas.",
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

            # Harus SUDAH LEWAT dua tahap sebelumnya.
            if not cop.get("isBapApproved"):
                return app_error(
                    ErrorCode.VALIDATION,
                    "BAP belum disetujui. Setujui BAP-nya lebih dahulu.",
                    400,
                )
            if not cop.get("isCopCreated"):
                return app_error(
                    ErrorCode.VALIDATION,
                    "CoP belum dibuat. Harga dan potongannya perlu diisi "
                    "lebih dahulu.",
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
                # Yang menyetujui BAP tidak merangkap menyetujui CoP — dua
                # persetujuan berarti dua orang. Karena keduanya level 4 dan
                # ambang setuju-sendiri = 5, level 4 tidak pernah lolos.
                penyetuju_bap = cop.get("bapApprovedBy")
                if penyetuju_bap is not None and int(penyetuju_bap) == int(user_id):
                    return app_error(
                        ErrorCode.PO_CHECKER_IS_APPROVER,
                        "Certificate of payment tidak dapat disetujui oleh "
                        "yang menyetujui BAP-nya sendiri.",
                        403,
                    )
                # Pembuat CoP (yang mengisi harga) tidak menyetujui buatannya
                # sendiri — penjagaan yang sama seperti pada purchase order.
                pembuat_cop = cop.get("copCreatedBy")
                if pembuat_cop is not None and int(pembuat_cop) == int(user_id):
                    return app_error(
                        ErrorCode.PO_CHECKER_IS_APPROVER,
                        "Certificate of payment tidak dapat disetujui oleh "
                        "pembuat CoP-nya sendiri.",
                        403,
                    )

            hasil = await CertificateOfPaymentRepository.approve(cop_id, user_id)

            # Kabar bahwa CoP disetujui dan siap ditagih:
            #   * pembuat CoP — dokumennya tembus;
            #   * tim tagihan (seluruh FAT) — ada CoP yang boleh langsung
            #     diterbitkan tagihannya.
            # Penyetujunya sendiri dikecualikan; ia baru menekan tombolnya.
            if isinstance(hasil, dict) and "error" not in hasil:
                try:
                    import asyncio
                    from repository.push_subscription_repository import (
                        PushSubscriptionRepository,
                    )
                    from utils.webpush import kirim_ke_pengguna, push_aktif

                    if push_aktif():
                        nama = cop.get("name") or f"CoP #{cop_id}"
                        proyek = cop.get("projectName") or ""
                        label = nama + (f" — {proyek}" if proyek else "")
                        pembuat = cop.get("createdBy")

                        if pembuat is not None and int(pembuat) != int(user_id):
                            asyncio.create_task(
                                kirim_ke_pengguna(
                                    [int(pembuat)],
                                    judul="CoP disetujui",
                                    pesan=f"{label} telah disetujui dan siap "
                                    "ditagihkan.",
                                    url=f"/Certificate-of-payment/View/{cop_id}",
                                    tag=f"cop-approved-{cop_id}",
                                )
                            )

                        # Tim tagihan: pembuat CoP dikecualikan agar tidak
                        # menerima dua kabar bila ia kebetulan juga di FAT.
                        tagihan = (
                            await PushSubscriptionRepository.penerima_tagihan_ids(
                                kecuali_user_ids=[user_id, pembuat]
                            )
                        )
                        if tagihan:
                            asyncio.create_task(
                                kirim_ke_pengguna(
                                    tagihan,
                                    judul="CoP siap ditagih",
                                    pesan=f"{label} sudah disetujui dan siap "
                                    "diterbitkan tagihannya.",
                                    url=f"/Certificate-of-payment/View/{cop_id}",
                                    tag=f"cop-siap-tagih-{cop_id}",
                                )
                            )
                except Exception as push_err:
                    log_error(
                        f"Gagal menjadwalkan notifikasi CoP disetujui: "
                        f"{str(push_err)}"
                    )

            return hasil
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
            # Tarif PPN mengikuti SPK-nya, BUKAN angka tetap.
            #
            # Ia pernah 10% dan kini 11%; menuliskannya di kode berarti tiap
            # dokumen lama yang dibuka ulang menampilkan tarif yang keliru.
            # Nol berarti dokumen ini memang tidak kena PPN — dan barisnya
            # tidak digambar sama sekali, bukan digambar bernilai nol.
            "ppn": float(_d(spk.get("ppn"))),
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
                    "Potongan dan tambahan hanya dapat diisi pembuat CoP "
                    "(engineering level 2 ke atas).",
                    403,
                )

            cop = await CertificateOfPaymentRepository.get_by_id(cop_id)
            if isinstance(cop, dict) and "error" in cop:
                return cop

            # GERBANG BAP. Nilai rupiah baru boleh disentuh setelah progres
            # lapangannya disahkan — sebelum itu tidak ada harga sama sekali.
            if not cop.get("isBapApproved"):
                return app_error(
                    ErrorCode.VALIDATION,
                    "BAP belum disetujui. Potongan dan tambahan baru dapat "
                    "diisi setelah progres lapangannya disetujui.",
                    400,
                )

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
    async def data_cetak(
        cop_id: int, user_level: int = 1, sertakan_cop: bool = True
    ):
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

            # BELUM DIPERIKSA -> CoP tidak boleh dicetak.
            #
            # Lembar CoP menyatakan nilai tagihan, dan sebelum diperiksa
            # angkanya belum ditelaah siapa pun — potongan uang muka dan
            # retensi bahkan belum tentu dimasukkan. Lembar seperti itu
            # tidak dapat dibedakan dari yang sudah benar begitu keluar dari
            # pencetak, dan satu lembar yang sampai ke pemasok sudah cukup
            # untuk ditagihkan.
            #
            # BAP tetap boleh dicetak: ia menyatakan volume yang terlaksana,
            # bukan nilai yang dibayar, dan justru itulah yang dibawa ke
            # lapangan untuk diperiksa lebih dulu.
            if sertakan_cop and not cop.get("isCopCreated"):
                return app_error(
                    ErrorCode.VALIDATION,
                    "Certificate of payment belum diperiksa, jadi belum dapat "
                    "dicetak. Berita Acara Pemeriksaan tetap dapat diunduh.",
                    409,
                )

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
            if not CertificateOfPaymentController.melayani_cop(spk):
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
            # Nilai PER adendum, bukan hanya jumlahnya.
            #
            # Lembar ini menyebut "Addendum #" satu baris saja, sehingga dua
            # adendum tercetak sebagai satu angka gabungan dan yang membacanya
            # tidak dapat mencocokkannya dengan berkas adendum mana pun.
            per_adendum: Dict[Any, Decimal] = {}
            for b in baris_kontrak:
                nilai = _d(b["quantity"]) * _d(b["price"])
                if b["addendumNumber"] is None:
                    nilai_induk += nilai
                else:
                    nilai_adendum += nilai
                    nomor_ad = b["addendumNumber"]
                    per_adendum[nomor_ad] = per_adendum.get(nomor_ad, Decimal("0")) + nilai
            nilai_kontrak = nilai_induk + nilai_adendum

            # Diurutkan sebagai teks: nomor adendum tidak dijamin berupa
            # angka, dan mengurutkan campuran angka & teks menimbulkan galat
            # yang hanya muncul pada SPK tertentu.
            daftar_adendum = [
                {"nomor": k, "nilai": float(v)}
                for k, v in sorted(per_adendum.items(), key=lambda x: str(x[0]))
            ]

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
            # DASAR PPN sengaja memakai `bersih` YANG TERSIMPAN — yaitu
            # sebelum PPh. PPh adalah pemotongan atas penghasilan pemasok,
            # bukan pengurang dasar pengenaan PPN; mengurangkannya lebih dulu
            # akan mengecilkan PPN yang justru tidak boleh mengecil.
            ppn = bersih * tarif_ppn / Decimal("100")

            # PPh periode ini: tarif SPK x progres KOTOR periode ini.
            #
            # Dasarnya progres kotor — sama dengan dasar yang dipakai baris
            # PPh pada blok syarat kontrak di atas, dan sama dengan yang
            # dipotong pemberi kerja pada pembayarannya.
            tarif_pph = _d(spk.get("pphPercentage"))
            pph_periode = kotor * tarif_pph / Decimal("100")

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
            #
            # PPh TIDAK di sini, melainkan DI BAWAH PPN. Ia bukan pengurang
            # nilai pekerjaan: uang muka dan retensi mengurangi apa yang
            # menjadi hak pemasok atas periode ini, sedangkan PPh dipotong
            # dari hak itu lalu disetorkan ke negara atas namanya. Menaruhnya
            # di antara keduanya membuat orang membacanya sebagai potongan
            # nilai pekerjaan, dan itu pertanyaan yang berulang.
            POKOK = ("uang_muka", "retensi")
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
                    "bapApprovedByName": cop.get("bapApprovedByName"),
                    "copCreatedByName": cop.get("copCreatedByName"),
                    "approvedByName": cop.get("approvedByName"),
                    "createdByPosition": cop.get("createdByPosition"),
                    "bapApprovedByPosition": cop.get("bapApprovedByPosition"),
                    "copCreatedByPosition": cop.get("copCreatedByPosition"),
                    "approvedByPosition": cop.get("approvedByPosition"),
                    "bapApprovedAt": cop.get("bapApprovedAt"),
                    "copCreatedAt": cop.get("copCreatedAt"),
                    "approvedAt": cop.get("approvedAt"),
                    "isBapApproved": bool(cop.get("isBapApproved")),
                    "isCopCreated": bool(cop.get("isCopCreated")),
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
                    "daftarAdendum": daftar_adendum,
                },
                "bap": bap,
                "bapTotal": {
                    "total": float(nilai_kontrak),
                    "bobot": float(_bagi(nilai_kontrak, nilai_kontrak)),
                    "bobotSebelumnya": float(bobot_lalu),
                    "bobotSaatIni": float(bobot_kini),
                    "bobotAkumulatif": float(bobot_akum),
                },
                # PPh MENGURANGI total lembar ini, tetapi TIDAK mengubah nilai
                # tersimpan CoP-nya.
                #
                # Keduanya menyatakan hal yang berbeda, dan dua-duanya benar:
                #
                #   * `totalDibayar` di sini = yang benar-benar DITRANSFER ke
                #     pemasok, setelah PPh-nya dipotong untuk disetorkan ke
                #     negara atas namanya. Itulah angka yang dicocokkan dengan
                #     bukti transfer, dan itulah yang diterbilangkan.
                #
                #   * `netAmount` yang tersimpan tetap BRUTO — ia nilai
                #     pekerjaannya, dan itulah yang menjadi DPP tagihan serta
                #     pembelian yang terbit dari CoP ini. PPh adalah titipan,
                #     bukan pengurang nilai pekerjaan.
                #
                # Selisih keduanya persis sebesar `pph`. Yang membandingkan
                # lembar ini dengan daftar CoP akan menemukan selisih itu, dan
                # baris PPh di bawah PPN-lah yang menjelaskannya.
                "nilai": {
                    "kotor": float(kotor),
                    "persenProgres": float(bobot_kini),
                    "potongan": float(potongan),
                    "tambahan": float(tambahan),
                    "bersih": float(bersih),
                    "tarifPpn": float(tarif_ppn),
                    "ppn": float(ppn),
                    "tarifPph": float(tarif_pph),
                    "pph": float(pph_periode),
                    # Nilai TAGIHAN: bersih + PPN, sebelum PPh dipotong.
                    # Inilah yang akan menjadi tagihan dan pembeliannya —
                    # angka yang sama dengan nilai tersimpan CoP beserta
                    # PPN-nya, dan yang membuat selisih terhadap baris
                    # terakhir terlihat asal-usulnya.
                    "tagihan": float(bersih + ppn),
                    "totalDibayar": float(bersih + ppn - pph_periode),
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
    # Penagihan
    # ------------------------------------------------------------------

    @staticmethod
    async def siap_tagih(
        keyword: str | None = None,
        user_level: int = 1,
        purchase_order_id: int | None = None,
    ):
        """
        CoP yang siap ditagihkan: sudah disetujui, belum ada pembeliannya.

        Dijaga level 2 ke atas seperti seluruh jalan keluar yang memuat
        rupiah — daftar ini menyebut nilai bersih tiap dokumen, dan itulah
        angka yang akan menjadi DPP pembeliannya.

        `purchase_order_id` mempersempitnya pada satu SPK; formulir
        pembelian memakainya untuk memperingatkan bahwa SPK yang dipilih
        masih punya CoP yang belum ditagihkan.
        """
        try:
            if not boleh_melihat_nilai_cop(user_level):
                return app_error(
                    ErrorCode.FORBIDDEN,
                    "Daftar ini memuat nilai rupiah dan hanya dapat dibuka "
                    "level 2 ke atas.",
                    403,
                )
            baris = await CertificateOfPaymentRepository.siap_tagih(
                keyword, purchase_order_id=purchase_order_id
            )
            if isinstance(baris, dict) and "error" in baris:
                return baris

            hasil = []
            for c in baris:
                # Jenis yang memang tidak memakai CoP tidak boleh muncul di
                # sini pula. Dokumen semacam itu seharusnya tidak pernah
                # ada, tetapi aturan A/D lahir belakangan dan yang telanjur
                # tersimpan tetap terbaca oleh kueri ini.
                if not CertificateOfPaymentController.melayani_cop(c):
                    continue
                hasil.append(
                    {
                        "id": c["id"],
                        "name": c["name"],
                        "number": c["number"],
                        "projectName": c["projectName"],
                        "date": c["date"],
                        "periodStart": c.get("periodStart"),
                        "periodEnd": c.get("periodEnd"),
                        "netAmount": float(_d(c.get("netAmount"))),
                        "purchaseOrderID": c.get("purchaseOrderID"),
                        "purchaseOrderName": c.get("purchaseOrderName"),
                        "purchaseType": c.get("purchaseType"),
                        "supplierID": c.get("supplierID"),
                        "supplierName": c.get("supplierName"),
                        "supplierAddress": c.get("supplierAddress"),
                        # Tarif pajak IKUT, supaya formulir pembelian tidak
                        # perlu menanyakan SPK-nya sekali lagi.
                        #
                        # PPh sengaja diteruskan APA ADANYA dari SPK: di
                        # sinilah ia dipotong, bukan di CoP. Lihat catatan
                        # pada KATEGORI_POTONGAN.
                        "ppn": float(_d(c.get("ppn"))),
                        "pphCode": c.get("pphCode"),
                        "pphTaxObject": c.get("pphTaxObject"),
                        "pphPercentage": float(_d(c.get("pphPercentage"))),
                    }
                )
            return hasil
        except Exception as e:
            log_error(f"Gagal membaca CoP siap tagih: {str(e)}")
            return internal_error()

    @staticmethod
    async def periode_bertindih(
        purchase_order_id: int,
        mulai,
        selesai,
        kecuali_cop_id: int | None = None,
    ):
        """
        CoP lain atas SPK yang sama yang periodenya bertindih.

        PERINGATAN, BUKAN PENOLAKAN.

        Periode yang bertindih tidak selalu salah — pekerjaan dapat memang
        disertifikasi ulang setelah perbaikan, dan CoP pembatalan pun
        memakai rentang yang sama. Yang keliru adalah bertindih TANPA
        disadari, dan itu diselesaikan dengan menunjukkan dokumen
        pembandingnya, bukan dengan menutup jalan.

        Karena itu ia berdiri sebagai jalan keluar tersendiri yang dibaca
        layar sebelum menyimpan — bukan pemeriksaan di dalam `create` yang
        akan memaksa server menolak.
        """
        try:
            if not purchase_order_id or not mulai or not selesai:
                return {"bertindih": []}
            baris = await CertificateOfPaymentRepository.periode_bertindih(
                purchase_order_id, mulai, selesai, kecuali_cop_id
            )
            return {
                "bertindih": [
                    {
                        "id": b["id"],
                        "name": b["name"],
                        "number": b["number"],
                        "date": b["date"],
                        "periodStart": b["periodStart"],
                        "periodEnd": b["periodEnd"],
                        "keadaan": (
                            "disetujui"
                            if b.get("isApproved")
                            else "dibuat"
                            if b.get("isCopCreated")
                            else "bap"
                            if b.get("isBapApproved")
                            else "draft"
                        ),
                    }
                    for b in baris
                ]
            }
        except Exception as e:
            log_error(f"Gagal memeriksa tindih periode CoP: {str(e)}")
            return internal_error()

    @staticmethod
    async def tagihan(cop_id: int, user_level: int = 1):
        """Keadaan penagihan sebuah CoP: sudah, atau belum."""
        try:
            p = await CertificateOfPaymentRepository.tagihan(cop_id)
            if not p:
                return {"ditagihkan": False, "pembelian": None}
            keluar = {
                "id": p["id"],
                "invoiceName": p.get("invoiceName"),
                "date": p.get("date"),
                "lastStatus": p.get("lastStatus"),
                "isPaid": bool(p.get("isPaid")),
                "createdByName": p.get("createdByName"),
            }
            if boleh_melihat_nilai_cop(user_level):
                keluar["dpp"] = float(_d(p.get("dpp")))
            return {"ditagihkan": True, "pembelian": keluar}
        except Exception as e:
            log_error(f"Gagal membaca penagihan CoP: {str(e)}")
            return internal_error()

    @staticmethod
    async def periksa_boleh_ditagih(cop_id: int) -> Dict[str, Any] | None:
        """
        Boleh dijadikan dasar pembelian? Kembalikan galat bila tidak.

        Dipanggil dari sisi PEMBELIAN, sebelum barisnya disimpan. Ditulis di
        sini, bukan di controller pembelian, karena syaratnya milik CoP —
        dan yang menyalinnya ke sana akan tertinggal saat syaratnya berubah.
        """
        cop = await CertificateOfPaymentRepository.get_by_id(cop_id)
        if isinstance(cop, dict) and "error" in cop:
            return cop

        if not cop.get("isApproved"):
            return app_error(
                ErrorCode.VALIDATION,
                "Certificate of payment ini belum disetujui, jadi belum dapat "
                "ditagihkan.",
                409,
            )

        sudah = await CertificateOfPaymentRepository.tagihan(cop_id)
        if sudah:
            return app_error(
                ErrorCode.VALIDATION,
                "Certificate of payment ini sudah ditagihkan lewat pembelian "
                f"{sudah.get('invoiceName') or sudah['id']}. Hapus pembelian "
                "itu lebih dahulu bila memang perlu ditagihkan ulang.",
                409,
            )
        return None

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
        sort_by: str | None = None,
        sort_dir: str | None = None,
        keadaan: str | None = None,
    ):
        hasil = await CertificateOfPaymentRepository.get_all(
            purchase_order_id,
            project_name,
            created_by,
            page,
            page_size,
            keyword,
            sort_by,
            sort_dir,
            keadaan,
        )
        if isinstance(hasil, dict) and "error" in hasil:
            return hasil
        return CertificateOfPaymentController.saring_nilai(hasil, user_level)
