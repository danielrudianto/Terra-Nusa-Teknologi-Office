"""
Berkas ini dikosongkan dengan sengaja.

Dulu isinya dua hal, dan keduanya tidak pernah dipakai:

1. Deklarasi KEDUA tabel "bank_accounts" lewat Table(...) — untuk tabel yang
   sama, pada `metadata` yang sama dengan `models/bank_model.py`. SQLAlchemy
   melempar InvalidRequestError bila dua Table bernama sama didaftarkan pada
   satu MetaData, jadi berkas ini memang tidak pernah diimpor siapa pun —
   kalau pernah, aplikasinya tidak akan hidup.

   Meskipun mati, deklarasi itu tetap merusak dari jauh: `kolom_model()` di
   `scripts/cek_skema.py` menyimpan petanya dengan `hasil[nama_tabel] = kolom`
   — MENIMPA, lintas berkas, urut nama berkas. Karena "bank_mutation_model"
   urut sesudah "bank_model", daftar 11 kolom di sini menimpa daftar 12 kolom
   yang sebenarnya. Kolom `excludeFromCalendar` lalu dilaporkan "BERLEBIH",
   seolah ada di basis data tetapi tidak ada di model — padahal ada di
   dua-duanya. Laporannya menunjuk basis data; sumbernya berkas ini.

2. `class BankAccount(BaseModel)` dengan `__init__` yang memanggil
   `self.createdAt`, padahal bidangnya hanya id, bankAccountID, dan amount.
   Siapa pun yang memakainya langsung kena AttributeError.

Mutasi rekening yang sungguh dipakai ada di `models/mutation_model.py` —
itu yang diimpor `controllers/bank_controller.py`.

Namanya dipertahankan sebagai re-export supaya import lama (kalau masih ada
yang tersisa di suatu tempat) tidak mendadak putus. Aman dihapus sama sekali
bila `grep -rn "bank_mutation_model" --include=*.py .` sudah kosong.
"""

from models.bank_model import bank_accounts_table  # noqa: F401

__all__ = ["bank_accounts_table"]
