"""
Surel tidak boleh keluar atas nama akun yang salah.

APA YANG TERJADI

Alur otorisasi O365 di sini `public` — token DELEGASI. Pengirimnya karena itu
adalah akun yang MASUK saat `scripts/otorisasi_o365.py` dijalankan, dan tidak
ada satu baris pun di `services/mail_service.py` yang menyebutkan akun mana
yang seharusnya.

Otorisasi ulang dilakukan ketika client secret diganti atau tokennya rusak —
keadaan tergesa, di server, lewat SSH. Masuk dengan akun pribadi di layar itu
terasa persis sama dengan masuk dengan akun HRD: skripnya mencetak "BERHASIL"
untuk keduanya.

Sejak saat itu setiap undangan wawancara, setiap pemberitahuan PO, keluar atas
nama pribadi. Tidak ada galat, tidak ada surel yang gagal, tidak ada baris log.
Yang menerimanya tidak akan menelepon untuk menanyakan kenapa HRD berganti
nama.

YANG DIJAGA DI SINI

`MAIL_FROM` menyatakan alamatnya, dan pengiriman DITOLAK selama pemilik token
berbeda. Menolak memang berarti satu pemberitahuan tidak sampai — tetapi
pesannya menyebut sebab dan perbaikannya, dan ketahuan dalam hitungan menit.
Kebalikannya ketahuan ketika ada yang kebetulan melihat kotak masuknya.
"""

import pytest

from services import mail_service as modul
from services.mail_service import MailService, alamat_pengirim

KUNCI = {
    "MICROSOFT_CLIENT_ID": "id-uji",
    "MICROSOFT_CLIENT_SECRET": "rahasia-uji",
}


class _Cache:
    def __init__(self, username):
        self.username = username

    def get_account(self, **_):
        if self.username is None:
            return None
        return {"username": self.username, "environment": "login.windows.net"}


class _Con:
    def __init__(self, username):
        self.token_backend = _Cache(username)


class _Pesan:
    def __init__(self, kotak):
        self.kotak = kotak
        self.to = self
        self.subject = None
        self.body = None
        self.attachments = self

    def add(self, x):
        self.kotak.ditambahkan.append(x)

    def send(self):
        self.kotak.terkirim += 1


class _Kotak:
    def __init__(self):
        self.terkirim = 0
        self.ditambahkan = []

    def new_message(self):
        return _Pesan(self)


class _Akun:
    """Menggantikan `O365.Account`."""

    def __init__(self, username, terotentikasi=True):
        self.con = _Con(username)
        self.is_authenticated = terotentikasi
        self.kotak = _Kotak()

    def mailbox(self):
        return self.kotak


@pytest.fixture
def pasang(monkeypatch):
    """Menyiapkan env + `Account` tiruan; mengembalikan akun yang dipakai."""

    def _pasang(username, mail_from=None, terotentikasi=True):
        for k, v in KUNCI.items():
            monkeypatch.setenv(k, v)
        if mail_from is None:
            monkeypatch.delenv("MAIL_FROM", raising=False)
        else:
            monkeypatch.setenv("MAIL_FROM", mail_from)

        akun = _Akun(username, terotentikasi)
        monkeypatch.setattr(modul, "Account", lambda *a, **k: akun)
        monkeypatch.setattr(
            modul, "FileSystemTokenBackend", lambda *a, **k: object()
        )
        return akun

    return _pasang


# ----------------------------------------------------------------------


def test_menolak_kirim_saat_pemilik_token_bukan_MAIL_FROM(pasang):
    akun = pasang("daniel@alphakonstruksi.com", mail_from="hrd@alphakonstruksi.com")

    with pytest.raises(RuntimeError) as galat:
        MailService.send_email("vendor@contoh.com", "Undangan", "Halo")

    pesan = str(galat.value)
    assert akun.kotak.terkirim == 0, "surelnya tetap dikirim"
    # Pesannya harus menyebut KEDUA alamatnya. Menyebut satu saja membuat yang
    # membacanya menebak mana yang perlu diubah — dan menebak di sini berarti
    # mengubah `.env` padahal yang salah tokennya.
    assert "daniel@alphakonstruksi.com" in pesan
    assert "hrd@alphakonstruksi.com" in pesan
    assert "otorisasi_o365.py" in pesan, "pesannya tidak menyebut perbaikannya"


def test_mengirim_saat_pemiliknya_cocok(pasang):
    akun = pasang("hrd@alphakonstruksi.com", mail_from="hrd@alphakonstruksi.com")

    MailService.send_email("vendor@contoh.com", "Undangan", "Halo")

    assert akun.kotak.terkirim == 1


def test_perbandingannya_tidak_peduli_huruf_besar_kecil(pasang):
    """
    Alamat surel tidak peka huruf.

    Penjaga yang menolak `HRD@...` terhadap `hrd@...` akan mematikan seluruh
    surel sistem atas perbedaan yang tidak ada artinya — dan yang paling mungkin
    dilakukan orang saat itu adalah mengosongkan `MAIL_FROM`.
    """
    akun = pasang("HRD@Alphakonstruksi.com", mail_from="  hrd@alphakonstruksi.com  ")

    MailService.send_email("vendor@contoh.com", "Undangan", "Halo")

    assert akun.kotak.terkirim == 1


def test_tanpa_MAIL_FROM_tidak_ada_pemeriksaan(pasang):
    """
    Perilaku lama dipertahankan selama `.env` belum diisi.

    Deploy backend dan penyuntingan `.env` adalah dua langkah terpisah. Bila
    pemeriksaannya menyala tanpa nilai, seluruh surel berhenti pada jeda di
    antara keduanya.
    """
    akun = pasang("siapa-saja@contoh.com", mail_from=None)

    MailService.send_email("vendor@contoh.com", "Undangan", "Halo")

    assert akun.kotak.terkirim == 1


def test_token_tak_terbaca_tidak_menghentikan_surel(pasang):
    """
    `None` = bentuk tokennya tidak dikenali, BUKAN alamat yang salah.

    Menolak kirim untuk keadaan ini berarti pemutakhiran pustaka O365 yang
    mengubah bentuk singgahannya akan mematikan seluruh surel sistem —
    kegagalan yang jauh lebih besar daripada yang sedang dijaga.
    """
    akun = pasang(None, mail_from="hrd@alphakonstruksi.com")

    MailService.send_email("vendor@contoh.com", "Undangan", "Halo")

    assert akun.kotak.terkirim == 1


def test_alamat_pengirim_membaca_singgahan_bukan_jaringan(pasang):
    akun = pasang("hrd@alphakonstruksi.com", mail_from=None)

    assert alamat_pengirim(akun) == "hrd@alphakonstruksi.com"


def test_alamat_pengirim_tidak_melempar_saat_bentuknya_asing():
    """Pembacaan yang gagal harus mengembalikan `None`, bukan menjatuhkan surel."""

    class _Rusak:
        class con:
            class token_backend:
                @staticmethod
                def get_account(**_):
                    raise KeyError("bentuk lain")

    assert alamat_pengirim(_Rusak()) is None


def test_token_kedaluwarsa_tetap_ditolak_lebih_dulu(pasang):
    """Urutannya penting: token mati disebut sebagai token mati, bukan salah akun."""
    pasang("daniel@alphakonstruksi.com", mail_from="hrd@alphakonstruksi.com",
           terotentikasi=False)

    with pytest.raises(RuntimeError) as galat:
        MailService.send_email("vendor@contoh.com", "Undangan", "Halo")

    assert "kedaluwarsa" in str(galat.value)
