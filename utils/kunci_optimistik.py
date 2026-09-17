"""
Penguncian optimistik — mencegah penyimpanan diam-diam saling menimpa.

MASALAHNYA

Dua orang membuka dokumen yang sama. Yang pertama menyimpan, lalu yang kedua
menyimpan formulir yang sudah ia buka SEBELUM perubahan pertama ada. Yang
kedua menang, dan pekerjaan yang pertama hilang.

Tidak ada galat. Tidak ada yang merah. Yang kehilangan baru tahu ketika ia
membuka kembali dokumennya dan isinya bukan yang ia tulis — dan pada saat itu
tidak ada apa pun yang dapat memberitahunya siapa yang menimpa, atau kapan.

Pada CoP ini bukan kemungkinan teoretis: alurnya empat tahap dengan dua
penyetuju, jadi memang DIRANCANG untuk disentuh lebih dari satu orang.

CARA KERJANYA

Setiap baris membawa `rowVersion`. Yang menyimpan menyebutkan versi yang ia
baca, dan penyimpanannya hanya berlaku bila versi itu masih yang terbaru:

    UPDATE ... SET ..., rowVersion = rowVersion + 1
     WHERE id = :id AND rowVersion = :versi

Bila ada yang mendahului, versinya sudah bertambah, tidak ada baris yang
cocok, dan penyimpanannya ditolak.

KENAPA JUMLAH BARIS DI SINI DAPAT DIPERCAYA

Secara bawaan MySQL melaporkan baris yang BERUBAH, bukan yang cocok. Penjaga
yang menghitung baris biasanya rapuh karena itu: menyimpan formulir tanpa
mengubah satu nilai pun menghasilkan 0, dan tidak dapat dibedakan dari "tidak
ketemu".

Yang membuatnya dapat dipercaya di sini adalah `rowVersion` yang SELALU
bertambah. Barisnya karena itu selalu berubah bila memang cocok, sehingga 0
hanya punya satu arti: tidak ada yang cocok.

    (Ini juga memperbaiki cacat yang sudah ada di `expense.update`, yang
    menjawab "Expense not found" untuk penyimpanan tanpa perubahan.)

TIGA HASIL, BUKAN DUA

"Tidak tersimpan" saja tidak cukup untuk memberi tahu penggunanya apa yang
harus ia lakukan. Dokumen yang hilang perlu jawaban yang berbeda dari dokumen
yang didahului orang lain — yang pertama berarti "muat ulang daftarnya", yang
kedua berarti "buka lagi, lihat perubahan orang itu, gabungkan".
"""

from typing import Any, Dict, Literal

from sqlalchemy import select, update

import utils.database

Hasil = Literal["tersimpan", "konflik", "hilang"]

KOLOM_VERSI = "rowVersion"


async def perbarui_terkunci(
    tabel: Any,
    id_baris: int,
    nilai: Dict[str, Any],
    versi: int | None,
    *,
    kolom_id: str = "id",
) -> Hasil:
    """
    Simpan `nilai` hanya bila `versi` masih yang terbaru.

    `versi=None` berarti pemanggilnya TIDAK menyebutkan versi, dan
    penyimpanannya dijalankan tanpa penjagaan — lihat keterangan panjang di
    bawah. Itu jalur sementara, bukan pilihan yang setara.
    """
    db = utils.database.database
    kolom = tabel.c

    nilai_baru = dict(nilai)
    # `rowVersion` tidak boleh datang dari muatan permintaan: yang menentukan
    # versinya adalah basis data, bukan yang mengirim formulirnya.
    nilai_baru.pop(KOLOM_VERSI, None)
    nilai_baru[KOLOM_VERSI] = getattr(kolom, KOLOM_VERSI) + 1

    kueri = update(tabel).where(getattr(kolom, kolom_id) == id_baris)

    """
    Tanpa versi, penjagaannya DILEWATI — dan itu disengaja.

    Backend dan frontend tidak dapat dinyalakan pada detik yang sama. Bila
    server menolak setiap penyimpanan yang tidak menyebutkan versi, maka pada
    jeda antara kedua deploy itu SELURUH penyuntingan gagal — penjaga yang
    dipasang untuk melindungi data justru menghentikan pekerjaan semua orang.

    Jadi permintaan tanpa versi diperlakukan seperti sebelumnya: tersimpan,
    dan versinya tetap bertambah supaya yang membaca berikutnya mendapat nilai
    yang benar.

    KONSEKUENSINYA HARUS DISEBUT TERANG-TERANGAN: selama frontend belum
    mengirim `rowVersion`, perlindungan ini TIDAK aktif. Ia bukan penjaga yang
    menyala sendiri — ia menunggu dipanggil.
    `scripts/kuncicek.py` memeriksa bahwa jalurnya tetap terpasang.
    """
    if versi is not None:
        kueri = kueri.where(getattr(kolom, KOLOM_VERSI) == int(versi))

    terpengaruh = await db.execute(kueri.values(**nilai_baru))

    if terpengaruh and terpengaruh > 0:
        return "tersimpan"

    # Nol baris: bedakan "didahului orang lain" dari "barisnya memang tidak
    # ada". Keduanya sama-sama nol, dan menjawabnya dengan pesan yang sama
    # membuat yang membacanya mencari di tempat yang salah.
    ada = await db.fetch_one(
        select(getattr(kolom, kolom_id)).where(getattr(kolom, kolom_id) == id_baris)
    )
    return "konflik" if ada else "hilang"


def jawaban_konflik(nama_dokumen: str = "Dokumen") -> Dict[str, Any]:
    """
    Jawaban baku untuk penyimpanan yang didahului orang lain.

    409 Conflict, bukan 400 maupun 500. Ini bukan permintaan yang salah bentuk
    dan bukan kerusakan — ini keadaan yang sah dan dapat dipulihkan, dan
    kodenya harus mengatakan begitu supaya frontend dapat menanganinya secara
    khusus alih-alih menampilkan "terjadi kesalahan".

    Pesannya menyebutkan apa yang harus dilakukan, bukan hanya apa yang
    terjadi. "Konflik versi" tidak memberi tahu siapa pun langkah berikutnya.
    """
    return {
        "error": (
            f"{nama_dokumen} ini sudah diubah orang lain sejak Anda membukanya. "
            "Muat ulang halamannya untuk melihat perubahan terbaru, lalu "
            "terapkan kembali perubahan Anda."
        ),
        "status": 409,
    }
