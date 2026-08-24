# Pengujian Backend

## Penempatan berkas

Semua berkas di folder ini disalin ke folder `test/` pada akar backend —
folder yang sama dengan `main.py`:

```
Terra-Nusa-Teknologi-Office/
├── main.py
├── requirements.txt        <- timpa (menambah pytest & pytest-asyncio)
├── pytest.ini              <- taruh di akar, sejajar main.py
└── test/
    ├── client_test.py      <- milik lama, biarkan
    ├── conftest.py
    ├── _fake_db.py
    └── *_test.py
```

`client_test.py` yang lama **tidak perlu dihapus**. Berkas itu memanggil
endpoint sungguhan sehingga butuh server dan basis data hidup; bila gagal
dimuat, pytest menghentikan seluruh pengumpulan berkas. Karena itu ia
dilewati secara bawaan, dan bisa dijalankan khusus bila server siap:

```bash
pytest test/client_test.py
```

## Menjalankan

Menjalankan seluruh pengujian:

```bash
pip install pytest pytest-asyncio
pytest
```

## Cara kerjanya

Pengujian di folder ini **tidak membutuhkan MySQL**. Objek `database` yang
dipakai repository diganti tiruan (`_fake_db.py`) lewat fixture `fake_db`,
sehingga bisa dijalankan kapan saja dan selesai dalam hitungan detik.

```python
async def test_contoh(fake_db):
    db = fake_db('repository.purchase_order_repository')
    db.queue('fetch_val', 157)          # nilai balikan kueri berikutnya
    ...
    assert db.executed('fetch_all') == 1  # memastikan kueri dijalankan
```

`fake_db` menerima beberapa modul sekaligus bila satu fungsi menyentuh lebih
dari satu repository.

## Isi

| Berkas | Cakupan |
|---|---|
| `purchase_order_schema_test.py` | Skema sebagai penyaring: field yang tidak dideklarasikan dibuang diam-diam |
| `purchase_order_repository_test.py` | `_normalize_row` — penguraian kolom JSON |
| `purchase_order_repository_db_test.py` | Penomoran PO per proyek, kontrak balikan daftar, penanganan galat |
| `purchase_order_item_repository_test.py` | `_clean_item` (item_id vs equipment_id) dan penyimpanan baris item |

## Menambah repository lain

Salin pola pada `purchase_order_repository_db_test.py`: tetapkan konstanta
`MODULE` berisi jalur modul repository, minta fixture `fake_db`, antrekan
nilai balikan, lalu periksa bentuk balikan dan penanganan galatnya.

Yang paling layak diuji lebih dulu pada tiap repository:

1. **Bentuk balikan** yang dijanjikan ke controller (`data`/`count`, atau
   `error`/`status`).
2. **Penanganan galat** — repository sebaiknya mengembalikan pesan, bukan
   melempar, kecuali kegagalan itu memang harus menghentikan proses.
3. **Aturan bisnis** yang mudah salah, mis. penomoran berjalan.
