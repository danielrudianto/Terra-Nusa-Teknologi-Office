import os

from O365 import Account, FileSystemTokenBackend

from utils.logger_utils import log_error


def alamat_pengirim(account) -> str | None:
    """
    Alamat surel PEMILIK TOKEN — yaitu pengirim yang sebenarnya.

    Dibaca dari singgahan token di disk, bukan dari Microsoft. Pemeriksaan
    identitas yang menambah satu permintaan jaringan pada setiap surel akan
    dilepas orang pertama kali ia melambat, dan penjaga yang dilepas tidak
    menjaga apa pun.

    Mengembalikan `None` bila bentuk tokennya tidak dikenali. Itu disengaja:
    lihat alasannya di `send_email`.
    """
    try:
        akun = account.con.token_backend.get_account()
    except Exception:
        return None
    if not akun:
        return None
    alamat = (akun.get("username") or "").strip().lower()
    return alamat or None


class MailService:
    """
    Pengiriman surel lewat Microsoft 365.

    Kredensialnya dari `MICROSOFT_CLIENT_ID` dan `MICROSOFT_CLIENT_SECRET`;
    tokennya disimpan sebagai berkas di `storage/tokens`.

    PENGIRIMNYA ADALAH PEMILIK TOKEN — dan tidak ada satu baris pun di berkas
    ini yang menentukannya.

    Alur otorisasinya `public` (lihat `scripts/otorisasi_o365.py`): tokennya
    milik akun yang MASUK saat skrip itu dijalankan. Siapa pun yang menjalankan
    otorisasi ulang — karena secret di Azure diganti, atau tokennya rusak —
    diam-diam memindahkan alamat pengirim seluruh sistem ke akunnya sendiri.

    Kegagalannya tidak menghasilkan galat apa pun. Surelnya terkirim, sampai,
    dan terbaca; hanya namanya yang berubah. Yang menerima undangan wawancara
    dari nama pribadi alih-alih HRD tidak akan menghubungi siapa pun untuk
    menanyakannya.

    `MAIL_FROM` di `.env` adalah satu-satunya tempat alamat itu DINYATAKAN,
    sehingga ia dapat dibandingkan.
    """

    @staticmethod
    def send_email(to_email, subject, body, attachment_path=None):
        """
        Kirim satu surel.

        `attachment_path` OPSIONAL — sebagian besar surel yang dikirim
        TerraBot tidak berlampiran.

        Melempar `RuntimeError` dengan pesan yang menyebut sebabnya bila
        gagal. Pemanggilnya sudah membungkus dengan `try`, dan pesan yang
        jelas menghemat waktu menelusuri log.
        """
        client_id = os.getenv("MICROSOFT_CLIENT_ID")
        client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")

        # Diperiksa lebih dulu, bukan dibiarkan gagal di dalam pustaka.
        #
        # Kredensial KOSONG menghasilkan `invalid_client` dari Microsoft —
        # pesan yang sama persis dengan secret yang SALAH atau KEDALUWARSA.
        # Ketiganya perlu penanganan berbeda, dan membedakannya dari pesan
        # Microsoft saja tidak mungkin.
        if not client_id or not client_secret:
            raise RuntimeError(
                "MICROSOFT_CLIENT_ID atau MICROSOFT_CLIENT_SECRET belum "
                "diisi di .env — surel tidak dapat dikirim."
            )

        token_backend = FileSystemTokenBackend(
            token_path="storage/tokens",
            token_filename="o365_token.txt",
        )

        account = Account(
            (client_id, client_secret), token_backend=token_backend
        )

        # `authenticate()` TIDAK dipanggil di sini.
        #
        # Ia membuka alur otorisasi yang menunggu masukan di konsol — dan di
        # dalam proses server, yang menunggu itu menggantung selamanya:
        # permintaannya tidak pernah menjawab, dan yang menekan tombol hanya
        # melihat layar berputar tanpa akhir.
        #
        # Otorisasi dilakukan SEKALI di server lewat skrip terpisah; di sini
        # cukup dilaporkan bahwa tokennya perlu diperbarui.
        if not account.is_authenticated:
            raise RuntimeError(
                "Token Microsoft 365 tidak sah atau sudah kedaluwarsa. "
                "Periksa masa berlaku client secret di Azure, lalu jalankan "
                "ulang otorisasi di server."
            )

        # Pengirimnya diperiksa SEBELUM mengirim.
        #
        # Menolak mengirim terasa keras — satu pemberitahuan tidak sampai. Tapi
        # yang dicegahnya lebih mahal: surel resmi ke vendor dan pelamar yang
        # keluar atas nama orang lain, berhari-hari, tanpa satu pun tanda.
        # Yang pertama ketahuan dalam hitungan menit dan pesannya menyebutkan
        # perbaikannya; yang kedua ketahuan ketika ada yang kebetulan melihat
        # kotak masuknya.
        diharapkan = (os.getenv("MAIL_FROM") or "").strip().lower()
        if diharapkan:
            sebenarnya = alamat_pengirim(account)
            # `None` = bentuk tokennya tidak terbaca, BUKAN alamat yang salah.
            #
            # Menolak kirim untuk keadaan ini berarti pemutakhiran pustaka O365
            # yang mengubah bentuk singgahannya akan mematikan seluruh surel
            # sistem — kegagalan yang jauh lebih besar daripada yang dijaga.
            if sebenarnya and sebenarnya != diharapkan:
                raise RuntimeError(
                    f"Token Microsoft 365 milik `{sebenarnya}`, sedangkan "
                    f"MAIL_FROM menyebut `{diharapkan}`. Surel tidak dikirim "
                    f"supaya tidak keluar atas nama akun yang salah.\n"
                    f"Perbaikan: hapus `storage/tokens/o365_token.txt`, "
                    f"jalankan `python scripts/otorisasi_o365.py`, dan MASUK "
                    f"dengan `{diharapkan}`."
                )

        try:
            mailbox = account.mailbox()
            message = mailbox.new_message()
            message.to.add(to_email)
            message.subject = subject
            message.body = body

            # Lampiran hanya ditambahkan bila memang ada DAN berkasnya nyata.
            #
            # Sebelumnya `attachments.add(None)` dipanggil pada SETIAP surel
            # tanpa lampiran — dan sebagian versi pustaka O365 melempar galat
            # untuk itu, sehingga undangan yang seharusnya terkirim gagal
            # tanpa sebab yang terlihat pada pesannya.
            if attachment_path and os.path.exists(attachment_path):
                message.attachments.add(attachment_path)
            elif attachment_path:
                # Berkasnya disebut tetapi tidak ada.
                #
                # Surelnya tetap dikirim: isi pesannya sudah benar, dan
                # menggagalkan seluruh pengiriman karena lampiran yang hilang
                # membuat pemberitahuan yang mendesak tidak pernah sampai.
                log_error(
                    f"Lampiran tidak ditemukan, surel dikirim tanpa "
                    f"lampiran: {attachment_path}"
                )

            message.send()
        except Exception as e:
            raise RuntimeError(f"Gagal mengirim surel: {str(e)}") from e
