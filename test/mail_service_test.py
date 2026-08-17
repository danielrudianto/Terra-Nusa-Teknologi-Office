"""
Layanan surel.

Kegagalan mengirim tidak boleh menggagalkan pekerjaan yang sudah benar —
undangan yang tokennya sudah terbit tetap sah, dan yang menerbitkannya masih
dapat menyalin tautannya untuk dikirim lewat jalan lain.

Yang harus dijaga adalah SEBABNYA terbaca. `invalid_client` dari Microsoft
muncul untuk tiga hal berbeda: kredensial kosong, salah, atau kedaluwarsa —
dan ketiganya perlu penanganan berbeda.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERKAS = os.path.join(AKAR, 'services', 'mail_service.py')


def test_lampiran_opsional():
    """
    Sebagian besar surel TerraBot tidak berlampiran. `attachments.add(None)`
    melempar galat pada sebagian versi pustaka O365 — dan undangan yang
    seharusnya terkirim gagal tanpa sebab yang terlihat.
    """
    s = open(BERKAS).read()
    assert 'attachment_path=None' in s


def test_lampiran_diperiksa_ada():
    s = open(BERKAS).read()
    assert 'os.path.exists(attachment_path)' in s


def test_kredensial_kosong_disebut_terpisah():
    """
    Kredensial kosong menghasilkan pesan Microsoft yang sama persis dengan
    secret yang salah. Membedakannya harus dilakukan sebelum memanggil.
    """
    s = open(BERKAS).read()
    assert 'belum' in s and 'diisi di .env' in s


def test_tidak_memanggil_authenticate_interaktif():
    """
    `authenticate()` menunggu masukan di konsol. Di dalam proses server, yang
    menunggu itu menggantung selamanya — permintaannya tidak pernah menjawab.
    """
    s = open(BERKAS).read()
    assert 'account.authenticate(' not in s
