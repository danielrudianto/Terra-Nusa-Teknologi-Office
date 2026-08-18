"""
Kolom model yang tidak ada di skema Update.

Sebagian skema `*Update` **tidak mewarisi** `*Base` — ia menyebut bidangnya
satu per satu supaya semuanya opsional. Akibatnya kolom baru yang ditambahkan
ke `Base` TIDAK sampai ke sana.

Pydantic membuang bidang yang tidak dikenalnya **tanpa galat apa pun**.
Muatannya benar, rutenya menjawab "updated successfully", dan nilainya
tersimpan sebagai NULL. Tidak ada satu pun tanda bahwa sesuatu dibuang.

Sudah terjadi pada `address` di proyek: dikirim benar dari layar, dijawab
sukses, hilang.
"""

import re
import sys
from glob import glob


# Bidang yang memang TIDAK boleh diubah lewat Update.
#
# Kunci utama, jejak audit, dan penanda hapus lunak diatur sistem — bukan oleh
# yang menyunting.
DIKECUALIKAN = {
    'id', 'createdAt', 'createdBy', 'updatedAt', 'updatedBy',
    'deletedAt', 'deletedBy', 'isDelete',
}


# Skema Update yang SENGAJA jauh lebih sempit daripada Base-nya.
#
# Bukan kelalaian: dokumen yang sudah terbit hanya boleh disentuh pada hal
# tertentu. Slip gaji misalnya hanya boleh ditandai lunas — angkanya tidak
# boleh berubah setelah dibayarkan.
#
# Disebut di sini supaya pemeriksa ini tetap sunyi untuk yang memang begitu,
# dan tetap menyala untuk kolom baru yang lupa ditambahkan.
DISENGAJA_SEMPIT = {
    'SalarySlip',       # hanya isPaid
    'Reimbursement',    # hanya sebagian, sisanya terkunci setelah disetujui
    'Loan',             # nilai dikunci; lihat aturan pinjaman
}


def periksa(akar: str = '.') -> list[str]:
    masalah = []

    for p in sorted(glob(f'{akar}/schemas/*_schema.py')):
        s = open(p, errors='ignore').read()

        for m in re.finditer(r'class (\w+)Update\((\w+)\):', s):
            nama, induk = m.group(1), m.group(2)
            if induk != 'BaseModel':
                # Mewarisi Base — kolom barunya ikut dengan sendirinya.
                continue
            if nama in DISENGAJA_SEMPIT:
                continue

            # bidang pada Update
            i = m.end()
            j = s.find('\nclass ', i)
            blok_u = s[i:j if j > 0 else len(s)]
            pada_update = set(re.findall(r'^\s{4}(\w+):', blok_u, re.M))

            # bidang pada Base yang sepadan
            mb = re.search(rf'class {nama}Base\(BaseModel\):', s)
            if not mb:
                continue
            i2 = mb.end()
            j2 = s.find('\nclass ', i2)
            blok_b = s[i2:j2 if j2 > 0 else len(s)]
            pada_base = set(re.findall(r'^\s{4}(\w+):', blok_b, re.M))

            kurang = sorted(pada_base - pada_update - DIKECUALIKAN)
            for k in kurang:
                masalah.append(
                    f'{p.split("/")[-1]}: `{nama}Update` tidak punya `{k}` '
                    f'yang ada di `{nama}Base` — nilainya akan dibuang diam-diam'
                )

    return masalah


if __name__ == '__main__':
    h = periksa()
    print(f'bidang hilang di skema Update: {len(h)}')
    print()
    for x in h[:20]:
        print(f'  {x}')
    sys.exit(1 if h else 0)
