from typing import Any, Dict, Optional

from repository.project_repository import ProjectRepository
from utils.logger_utils import log_error


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
    return data


class ProjectController:
    # ---- Proyek -----------------------------------------------------------

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
    ) -> Dict[str, Any]:
        return await ProjectRepository.get_all(
            keyword, isActive, isCancelled, page, pageSize, sortBy, sortByDirection
        )

    @staticmethod
    async def get_project(project_id: int) -> Dict[str, Any]:
        row = await ProjectRepository.get_by_id(project_id)
        if row is None:
            return {"error": "Project not found", "status": 404}
        kontrak = await ProjectRepository.list_contracts(project_id)
        return {"project": dict(row), "contracts": [dict(k) for k in kontrak]}

    @staticmethod
    async def update_project(
        project_id: int, data: dict, user_id: int
    ) -> Dict[str, Any]:
        if not data:
            return {"error": "Nothing to update", "status": 400}
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

        return await ProjectRepository.update(
            project_id, _selaraskan_keadaan(data), user_id
        )

    @staticmethod
    async def delete_project(project_id: int, user_id: int) -> Dict[str, Any]:
        row = await ProjectRepository.get_by_id(project_id)
        if row is None:
            return {"error": "Project not found", "status": 404}
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
