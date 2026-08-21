from typing import Any, Dict, Optional

from repository.project_repository import ProjectRepository
from utils.logger_utils import log_error


#: Proyek "ember" untuk kerjaan terlalu kecil (bor satu titik, dsb) yang tidak
#: sepadan dibuatkan proyek + SPK sendiri. Client-nya berganti-ganti dan
#: dicatat per dokumen. Dokumennya (mis. SPK) langsung terbit di bawah kode
#: ini tanpa menunggu penyiapan proyek.
KODE_MCH = "MCH"


def _mch_terkunci(kode: str | None, data: dict) -> dict | None:
    """
    Jaga MCH tetap ada dan tetap TERBUKA.

    MCH adalah tempat menampung kerjaan receh yang terus berjalan; menutup,
    membatalkan, mengganti kodenya, atau menghapusnya membuat seluruh dokumen
    yang menyebut "MCH" kehilangan pijakannya sekaligus. Karena itu identitas
    (kode) dan keadaan terbukanya dikunci di server — bukan sekadar diharapkan
    tidak ada yang menyentuhnya.

    Yang DIBIARKAN: penyuntingan tak berbahaya seperti alamat atau nama tampilan
    (dokumen menyebut KODE, bukan nama). Yang DITOLAK: ganti kode, tandai
    selesai (`isActive=false`), tandai batal (`isCancelled=true`).
    """
    if (kode or "").strip().upper() != KODE_MCH:
        return None

    kode_baru = (data.get("code") or "").strip().upper()
    if kode_baru and kode_baru != KODE_MCH:
        return {"error": "MCH_LOCKED", "code": "MCH_LOCKED", "status": 409}
    if data.get("isActive") is False or data.get("isCancelled") is True:
        return {"error": "MCH_LOCKED", "code": "MCH_LOCKED", "status": 409}
    return None


def _selaraskan_keadaan(data: dict) -> dict:
    """
    Jaga agar dua penanda keadaan tidak saling bertentangan.

    `isActive=1` bersama `isCancelled=1` tidak punya arti. Daripada
    mempercayai layar untuk selalu mengirim pasangan yang benar, aturannya
    ditegakkan di satu tempat ini:

        menandai batal      -> ikut mematikan isActive
        mengaktifkan lagi   -> ikut membatalkan penanda batal

    `isCancelled` didahulukan karena keadaannya lebih spesifik.

    Menandai SELESAI (`isActive=false` saja) sengaja tidak menyentuh
    `isCancelled`: proyek yang batal tidak berubah menjadi selesai hanya
    karena dinonaktifkan. Untuk mengubahnya, kirim `isCancelled=false`
    secara eksplisit.
    """
    if data.get("isCancelled") is True:
        data["isActive"] = False
    elif data.get("isActive") is True:
        data["isCancelled"] = False

    # Retensi hanya berlaku pada proyek yang masih berjalan.
    #
    # "Selesai sekaligus menunggu retensi" dan "batal sekaligus menunggu
    # retensi" tidak punya arti: yang pertama sudah melewati BAST 2, yang
    # kedua tidak pernah sampai ke sana. Dibiarkan, keduanya membuat proyek
    # yang sama terhitung pada dua penyaring sekaligus.
    if data.get("isCancelled") is True or data.get("isActive") is False:
        data["isRetention"] = False
    return data


async def _periksa_induk(project_id: int, induk_id) -> dict | None:
    """
    Hubungan induk-anak yang tidak masuk akal ditolak.

    Tiga hal dijaga, dan ketiganya menghasilkan laporan gabungan yang salah
    tanpa satu pun galat bila dibiarkan:

      1. Proyek tidak boleh menjadi induk DIRINYA SENDIRI. Laporan gabungan
         yang menelusuri hubungan itu menjumlahkan biayanya dua kali.

      2. Induknya tidak boleh proyek yang SUDAH menjadi anak. Kedalamannya
         dibatasi satu tingkat: rantai induk-anak-cucu membuat laporan
         gabungan harus menelusuri sedalam apa pun rantainya, dan rantai yang
         melingkar tidak pernah selesai dihitung.

      3. Proyek yang PUNYA ANAK tidak boleh dijadikan anak. Alasannya sama:
         ia akan menjadi tingkat kedua dari sebuah rantai.

    Dijaga di server, bukan cukup dengan menyaring pilihan di layar: muatan
    permintaan dapat disusun sendiri oleh siapa pun yang membuka Network tab.
    """
    if induk_id in (None, "", 0):
        return None

    try:
        induk_id = int(induk_id)
    except (TypeError, ValueError):
        return {"error": "Proyek induk tidak dikenal.", "status": 400}

    if induk_id == int(project_id):
        return {
            "error": "Proyek tidak dapat menjadi induk dirinya sendiri.",
            "status": 400,
        }

    if await ProjectRepository.get_by_id(induk_id) is None:
        return {"error": "Proyek induk tidak ditemukan.", "status": 404}

    if await ProjectRepository.induk_dari(induk_id):
        return {
            "error": (
                "Proyek yang dipilih sudah menjadi anak proyek lain. "
                "Hubungan induk-anak hanya satu tingkat."
            ),
            "status": 409,
        }

    jumlah_anak = await ProjectRepository.punya_anak(project_id)
    if jumlah_anak:
        return {
            "error": (
                f"Proyek ini sudah menjadi induk bagi {jumlah_anak} proyek, "
                f"sehingga ia tidak dapat dijadikan anak proyek lain."
            ),
            "status": 409,
        }

    return None


class ProjectController:
    # ---- Proyek -----------------------------------------------------------

    @staticmethod
    async def ringkasan_margin(page: int = 1, page_size: int = 10):
        """Ikhtisar margin seluruh proyek; penjumlahannya di basis data."""
        return await ProjectRepository.ringkasan_margin(page, page_size)

    @staticmethod
    async def create_project(data: dict, user_id: int) -> Dict[str, Any]:
        try:
            kode = (data.get("code") or "").strip().upper()
            if not kode:
                return {"error": "PROJECT_CODE_REQUIRED", "status": 400}

            # Diperiksa lebih dulu agar pesannya jelas. Batasan unik di basis
            # data tetap menjadi penjaga terakhir bila dua permintaan tiba
            # bersamaan.
            if await ProjectRepository.get_by_code(kode):
                return {"error": "PROJECT_CODE_EXISTS", "status": 409}

            data["code"] = kode
            return await ProjectRepository.create(_selaraskan_keadaan(data), user_id)
        except Exception as e:
            log_error(f"Error creating project: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_projects(
        keyword: Optional[str],
        isActive: Optional[bool],
        isCancelled: Optional[bool],
        page: int,
        pageSize: int,
        sortBy: Optional[str],
        sortByDirection: str,
        isRetention: Optional[bool] = None,
        keadaan: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await ProjectRepository.get_all(
            keyword,
            isActive,
            isCancelled,
            page,
            pageSize,
            sortBy,
            sortByDirection,
            isRetention,
            keadaan,
        )

    @staticmethod
    async def get_project(project_id: int) -> Dict[str, Any]:
        row = await ProjectRepository.get_by_id(project_id)
        if row is None:
            return {"error": "Project not found", "status": 404}
        kontrak = await ProjectRepository.list_contracts(project_id)
        return {"project": dict(row), "contracts": [dict(k) for k in kontrak]}

    @staticmethod
    async def keluarga(project_id: int) -> Dict[str, Any]:
        """Induk dan anak-anak proyek ini."""
        row = await ProjectRepository.get_by_id(project_id)
        if row is None:
            return {"error": "Project not found", "status": 404}
        return await ProjectRepository.keluarga(project_id)

    @staticmethod
    async def update_project(
        project_id: int, data: dict, user_id: int
    ) -> Dict[str, Any]:
        if not data:
            return {"error": "Nothing to update", "status": 400}

        # MCH terkunci: kode & keadaan terbukanya tidak boleh diubah.
        _mch_row = await ProjectRepository.get_by_id(project_id)
        if _mch_row is not None:
            terkunci = _mch_terkunci(_mch_row["code"], data)
            if terkunci:
                return terkunci

        # Kode boleh diganti SELAMA belum dipakai dokumen mana pun.
        #
        # Kode disimpan sebagai teks pada dokumen, bukan tautan ke baris ini.
        # Menggantinya setelah ada dokumen membuat yang lama tetap menyebut
        # kode lama — laporan per proyek terpecah dua, dan nomor SPK yang
        # sudah tercetak tidak lagi cocok dengan proyeknya.
        #
        # Selama belum dipakai, penggantian tidak merugikan siapa pun, dan
        # itulah keadaan ketika salah ketik biasanya ketahuan.
        kode_baru = (data.get("code") or "").strip().upper()
        if kode_baru:
            lama = await ProjectRepository.get_by_id(project_id)
            if lama is None:
                return {"error": "Project not found", "status": 404}

            if kode_baru != (lama["code"] or "").upper():
                dipakai = await ProjectRepository.count_documents(lama["code"])
                if dipakai:
                    return {
                        "error": (
                            f"Kode tidak dapat diubah: sudah dipakai pada "
                            f"{dipakai} dokumen. Mengubahnya membuat dokumen "
                            f"lama tetap menyebut kode lama."
                        ),
                        "status": 409,
                    }
                data["code"] = kode_baru
            else:
                data.pop("code", None)
        else:
            data.pop("code", None)

        # Hubungan induk-anak dijaga di sini.
        if "parentProjectID" in data:
            galat = await _periksa_induk(project_id, data["parentProjectID"])
            if galat:
                return galat

        return await ProjectRepository.update(
            project_id, _selaraskan_keadaan(data), user_id
        )

    @staticmethod
    async def delete_project(project_id: int, user_id: int) -> Dict[str, Any]:
        row = await ProjectRepository.get_by_id(project_id)
        if row is None:
            return {"error": "Project not found", "status": 404}
        # MCH tidak boleh dihapus — ia tempat sandaran dokumen kerjaan kecil
        # yang terus berjalan.
        if (row["code"] or "").strip().upper() == KODE_MCH:
            return {"error": "MCH_LOCKED", "code": "MCH_LOCKED", "status": 409}
        return await ProjectRepository.soft_delete(project_id, user_id)

    # ---- Kontrak ----------------------------------------------------------

    @staticmethod
    async def add_contract(
        project_id: int, data: dict, user_id: int
    ) -> Dict[str, Any]:
        if await ProjectRepository.get_by_id(project_id) is None:
            return {"error": "Project not found", "status": 404}
        return await ProjectRepository.add_contract(project_id, data, user_id)

    @staticmethod
    async def update_contract(
        contract_id: int, data: dict, user_id: int
    ) -> Dict[str, Any]:
        if not data:
            return {"error": "Nothing to update", "status": 400}
        if await ProjectRepository.get_contract(contract_id) is None:
            return {"error": "Contract not found", "status": 404}
        return await ProjectRepository.update_contract(contract_id, data, user_id)

    @staticmethod
    async def delete_contract(contract_id: int, user_id: int) -> Dict[str, Any]:
        if await ProjectRepository.get_contract(contract_id) is None:
            return {"error": "Contract not found", "status": 404}
        return await ProjectRepository.delete_contract(contract_id, user_id)
