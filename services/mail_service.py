import os

from O365 import Account, FileSystemTokenBackend

from utils.logger_utils import log_error


class MailService:
    """
    Pengiriman surel lewat Microsoft 365.

    Kredensialnya dari `MICROSOFT_CLIENT_ID` dan `MICROSOFT_CLIENT_SECRET`;
    tokennya disimpan sebagai berkas di `storage/tokens`.
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
