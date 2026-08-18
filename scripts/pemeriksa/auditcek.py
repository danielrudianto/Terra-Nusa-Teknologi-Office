"""
Jalur pengubah data yang tidak mencatat jejak audit.

Setiap tindakan yang membuat, mengubah, atau menghapus dokumen perlu
meninggalkan jejak — bukan demi kerapian, melainkan karena jejak itulah
satu-satunya cara menjawab "siapa mengubah ini, kapan" setelah kejadiannya
berlalu.

Yang tidak mencatat tidak menimbulkan galat apa pun: dokumennya tersimpan,
layarnya bekerja, dan ketiadaannya baru terlihat ketika ada yang mencari.

Sudah terjadi pada draf pembelian: dibuat, dikonversi, dan dihapus tanpa satu
baris pun di Aktivitas.

Diperiksa pada CONTROLLER dan REPOSITORY sekaligus — sebagian modul mencatat
di satu lapis, sebagian di lapis lain, dan yang penting adalah jejaknya ada
pada salah satunya.
"""

import os
import re
import sys
from glob import glob

AKAR = '.'

#: Modul yang memang tidak menyimpan apa pun.
DIKECUALIKAN = {
    'audit_log',        # pencatatnya sendiri
    'finance_status',   # hanya membaca
    'purchase_order_item',  # dicatat bersama purchase_order induknya
    'reminder',         # milik pengguna sendiri, bukan dokumen perusahaan
    # Agenda hanya membungkus `reminder` — seluruh penulisannya menuju
    # tabel yang sama, dan mencatat dua kali membuat riwayatnya ganda.
    'agenda',
    # Avatar pengguna: milik orangnya sendiri, seperti pengingat.
    'user_avatar',
}

TINDAKAN = ('create', 'update', 'delete', 'convert', 'approve')


def periksa(akar: str = AKAR) -> list[str]:
    kurang = []
    for p in sorted(glob(f'{akar}/controllers/*.py')):
        modul = os.path.basename(p).replace('_controller.py', '')
        if modul in DIKECUALIKAN:
            continue

        s = open(p).read()

        # Nama repository tidak selalu sama dengan controllernya —
        # `payment_incoming_controller` memakai `payment_income_repository`.
        # Mencocokkan nama saja membuat modul yang sudah mencatat dilaporkan
        # sebagai belum, dan laporan palsu membuat pemeriksa ini diabaikan.
        t = ''
        for kandidat in (f'{modul}_repository.py',
                         f'{modul.rstrip("ing")}_repository.py',
                         f'{modul}s_repository.py'):
            repo = os.path.join(akar, 'repository', kandidat)
            if os.path.exists(repo):
                t = open(repo).read()
                break

        # Repository apa pun yang DIIMPOR controller ini juga dihitung.
        #
        # Ditelusuri dari baris impornya, bukan dari nama kelasnya: kelas
        # `PaymentIncomingRepository` berada di berkas `payment_income_...`,
        # dan menebak nama berkas dari nama kelas meleset.
        for m in re.finditer(r'from repository\.(\w+) import', s):
            f = os.path.join(akar, 'repository', f'{m.group(1)}.py')
            if os.path.exists(f):
                t += open(f).read()

        # Diperiksa PER TINDAKAN, bukan sekadar "modulnya pernah mencatat".
        #
        # Pemeriksaan per modul terlalu longgar: satu `record()` pada
        # pembuatan membuat penghapusan yang tidak tercatat ikut lolos.
        # Sudah terjadi pada beberapa modul sekaligus — jejaknya ada saat
        # dokumen dibuat, hilang saat dihapus.
        aksi_tercatat = set(re.findall(r'action="(\w+)"', s + t))
        for k in ('create', 'update', 'delete'):
            # Hanya diperiksa bila modulnya memang punya jalur itu.
            punya = re.search(
                r'async def \w*' + k + r'\w*\(|async def '
                + {'create': '(buat|tambah)', 'update': '(ubah|sunting)',
                   'delete': '(hapus)'}[k]
                + r'\w*\(',
                s,
            )
            if not punya:
                continue
            # Nama aksi yang dipakai boleh berimbuhan — `update_status`,
            # `create_items` — asalkan berpangkal pada tindakan yang sama.
            if any(a.startswith(k) for a in aksi_tercatat):
                continue
            kurang.append(
                f'{modul}: jalur `{k}` ada tetapi tidak ada '
                f'`action="{k}..."` yang tercatat'
            )

        # apakah modul ini benar-benar mengubah data?
        mengubah = any(
            re.search(r'async def \w*' + k + r'\w*\(', s) for k in TINDAKAN
        )
        if not mengubah:
            continue

        if 'AuditLogRepository.record' in s or 'AuditLogRepository.record' in t:
            continue
        kurang.append(modul)
    return kurang


if __name__ == '__main__':
    h = periksa()
    print(f'modul tanpa jejak audit: {len(h)}')
    print()
    for m in h:
        print(f'  {m}')
        print('     mengubah data, tetapi tidak mencatat apa pun')
    sys.exit(1 if h else 0)
