"""
Matriks izin: level minimum tiap modul untuk tiap aksi.

Urutan nilai: (read, create, update, delete, approve)

Arti nilai khusus:
    0  -> aksi tidak berlaku pada modul ini
    9  -> tidak pernah diberikan lewat level; hanya lewat izin khusus
          (dipakai untuk slip gaji: seorang supervisor tidak otomatis boleh
          melihat gaji rekannya hanya karena levelnya lebih tinggi)

Level pengguna disimpan pada kolom users.authenticationLevel (1-5).
"""

ACTIONS = ("read", "create", "update", "delete", "approve")

# Aksi yang tidak berlaku / hanya lewat izin khusus.
NOT_APPLICABLE = 0
SPECIAL_ONLY = 9

MATRIX: dict[str, tuple[int, int, int, int, int]] = {
    "asset": (1, 3, 3, 5, 0),
    "audit_log": (5, 0, 0, 0, 0),
    "bank": (3, 5, 5, 5, 0),
    "calendar": (1, 0, 0, 0, 0),
    "client": (1, 3, 3, 5, 0),
    "dashboard": (1, 0, 0, 0, 0),
    "employees": (1, 9, 9, 5, 0),
    "expense_opponent": (1, 3, 3, 5, 0),
    "expenses": (1, 1, 1, 2, 3),
    "income": (1, 3, 3, 3, 3),
    "interpayment": (3, 3, 3, 3, 3),
    "loan": (3, 5, 5, 5, 5),
    "master_equipment": (1, 3, 3, 5, 0),
    "master_item": (1, 3, 3, 5, 0),
    "payment_incoming": (3, 3, 3, 3, 3),
    "payment_outgoing": (3, 3, 3, 3, 5),
    "purchase": (1, 1, 1, 2, 3),
    "purchase_draft": (1, 1, 1, 2, 3),
    "purchase_order": (1, 1, 1, 2, 3),
    "reimbursement": (1, 1, 1, 2, 3),
    "salary_slip": (9, 9, 9, 9, 9),
    "sales_invoice": (1, 1, 1, 2, 3),
    "supplier": (1, 3, 3, 5, 0),
    "tax": (3, 3, 3, 5, 0),
    "user": (5, 5, 5, 5, 0),
    # Foto profil dipisahkan dari modul "user": avatar tampil di hampir
    # semua layar (aktivitas, riwayat dokumen), sehingga membacanya tidak
    # bisa dibatasi level 5. Mengubahnya terbuka di level 1 karena rutenya
    # sudah menjaga sendiri bahwa seseorang hanya boleh mengubah avatarnya.
    "user_avatar": (1, 0, 1, 0, 0),
}


def required_level(module: str, action: str) -> int:
    """
    Level minimum untuk sebuah aksi.

    Modul yang tidak terdaftar dianggap milik superadmin: lebih aman menolak
    modul baru yang belum sempat dipetakan daripada membiarkannya terbuka.
    """
    if action not in ACTIONS:
        return 5
    baris = MATRIX.get(module)
    if baris is None:
        return 5
    return baris[ACTIONS.index(action)]