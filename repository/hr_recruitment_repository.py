"""
Bank soal ujian rekrutmen.

Soalnya esai dan dinilai orang; tidak ada kunci jawaban di sini. Yang disimpan
hanya pertanyaan, catatan, lampiran, dan nilai maksimalnya.
"""

import hashlib
import random
import secrets
from datetime import datetime as dt, timedelta

from sqlalchemy import and_, case, func, insert, or_, select, update

from models.hr_recruitment_model import (
    hr_answers_table,
    hr_candidates_table,
    hr_questions_table,
    hr_tests_table,
)
from models.user_model import users_table
from utils.database import database
from utils.errors import ErrorCode, app_error
from utils.logger_utils import log_error


#: Panjang kode peserta.
#:
#: Enam cukup: kodenya hanya perlu unik di antara pelamar satu gelombang
#: (puluhan, bukan jutaan), dan yang mengetiknya di subjek surel adalah
#: pelamar, dari ponsel.
PANJANG_KODE = 6


def kode_peserta(token: str) -> str:
    """
    Kode pendek untuk MENYORTIR, diturunkan dari token — bukan tokennya.

    KENAPA BUKAN TOKENNYA LANGSUNG. Token adalah kunci ujian itu: selama
    pelamar belum mengirim jawabannya, siapa pun yang memegangnya dapat
    membuka lembar itu dan mengubah isinya. Subjek surel adalah tempat yang
    paling mudah diteruskan, dikutip, dan dibaca orang lain — menaruh kunci
    di sana meniadakan seluruh gunanya token yang diacak.

    Hash SATU ARAH, jadi kode ini tidak dapat dikembalikan menjadi token.
    Ia juga tidak perlu disimpan: HR menghitungnya dari token yang sudah ada
    di barisnya, pelamar membacanya dari layar ujiannya, dan keduanya selalu
    mendapat kode yang sama.
    """
    if not token:
        return ""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[
        :PANJANG_KODE
    ].upper()


#: Status yang DIPUTUSKAN MANUSIA, satu-satunya yang boleh disetel lewat
#: rute status.
#:
#: Sisanya (`baru`, `mengerjakan`, `selesai`, `dinilai`) disimpulkan dari
#: keadaan dokumennya sendiri. Membiarkannya disetel manual berarti daftar
#: dapat menyatakan "sudah dinilai" atas lembar yang kosong.
STATUS_MANUAL = ("diwawancara", "diterima", "ditolak", "gagal_wawancara")

#: DUA jenis gagal, dibedakan menurut TAHAPNYA:
#:   `ditolak`         — gagal sebelum wawancara (hasil ujiannya);
#:   `gagal_wawancara` — sudah diwawancarai, lalu tidak dilanjutkan.
#: Keduanya masuk ember "ditolak"; yang membedakannya adalah pertanyaan
#: "sampai tahap mana ia sempat maju", yang dicari saat menimbang pelamar
#: yang sama di lowongan berikutnya.
STATUS_GAGAL = ("ditolak", "gagal_wawancara")

#: Status yang berarti pengerjaannya sudah selesai dan sudah dinilai penuh.
STATUS_DINILAI = "dinilai"

#: Status sesudah mengirim, sebelum dinilai penuh.
STATUS_SELESAI = "selesai"


#: EMBER DAFTAR PELAMAR — enam kelompok di menu samping.
#:
#: Bukan sekadar nama lain untuk `status`. Tangganya punya tujuh anak
#: tangga, dan menampilkan tujuh angka kepada yang bertanya "sudah sampai
#: mana rekrutmen ini" bukan jawaban, melainkan pekerjaan menjumlahkan yang
#: dilimpahkan kepadanya.
#:
#: `terbit` adalah SELURUH pelamar yang tautannya sudah terbit — ia
#: TUMPANG TINDIH dengan yang lain dengan sengaja, sebagai penyebut. Lima
#: sisanya SALING LEPAS: satu pelamar hanya dapat berada di satu ember.
#: Tanpa sifat itu, lencana-lencananya dijumlahkan orang dan hasilnya
#: melebihi jumlah pelamarnya sendiri.
#:
#: `submit` sengaja BERHENTI sebelum keputusan: yang sudah diwawancarai,
#: diterima, atau ditolak tentu sudah mengirim juga, tetapi memasukkannya
#: ke sini membuat angkanya tidak pernah turun dan karena itu tidak pernah
#: berguna. Yang ditanyakan sebenarnya "berapa yang menunggu ditangani".
EMBER = ("terbit", "submit", "wawancara", "diterima", "ditolak", "dihapus")


def _syarat_ember(ember: str):
    """Syarat SQL untuk satu ember; `None` bila namanya tidak dikenal."""
    aktif = hr_candidates_table.c.isDelete == False  # noqa: E712
    st = hr_candidates_table.c.status

    if ember == "terbit":
        return [aktif]
    if ember == "submit":
        return [
            aktif,
            hr_candidates_table.c.submittedAt.isnot(None),
            st.in_((STATUS_SELESAI, STATUS_DINILAI)),
        ]
    if ember == "wawancara":
        return [aktif, st == "diwawancara"]
    if ember == "diterima":
        return [aktif, st == "diterima"]
    if ember == "ditolak":
        return [aktif, st.in_(STATUS_GAGAL)]
    if ember == "dihapus":
        return [hr_candidates_table.c.isDelete == True]  # noqa: E712
    return None


def urutan_acak(soal: list, token: str) -> list:
    """
    Acak urutan soal — TETAP SAMA untuk pelamar yang sama.

    KENAPA DIACAK. Sebelum ini setiap pelamar menerima soal yang sama persis
    dalam urutan yang sama persis. Dikerjakan serentak di satu ruangan, nomor
    soal menjadi bahasa bersama: "nomor 7 jawabannya apa" cukup untuk
    menyontek tanpa melihat layar orang lain.

    KENAPA HARUS STABIL. Pengacakan yang berubah tiap panggilan jauh lebih
    buruk daripada tidak mengacak sama sekali: pelamar yang memuat ulang
    halamannya — atau yang autosave-nya memicu pemuatan ulang — mendapat
    urutan baru, dan soal yang sedang ia kerjakan berpindah tempat di tengah
    kalimat. Benihnya karena itu diambil dari TOKEN pelamar, yang tidak
    berubah sepanjang hidup lembar itu.

    URUTAN ASLINYA TIDAK HILANG. `sortOrder` ikut dikembalikan, dan lembar
    penilaian HR membacanya dengan `ORDER BY sortOrder` — yang memeriksa
    selalu melihat urutan yang sama untuk semua pelamar, apa pun urutan yang
    mereka kerjakan.
    """
    if not token or len(soal) < 2:
        return list(soal)
    # Benih diturunkan dari token lewat hash, bukan `hash()` bawaan Python:
    # `hash()` untuk `str` diacak per proses (PYTHONHASHSEED), jadi urutannya
    # akan berbeda setelah server di-restart — persis kegagalan yang hendak
    # dicegah, hanya lebih jarang terlihat.
    benih = int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:16], 16)
    hasil = list(soal)
    random.Random(benih).shuffle(hasil)
    return hasil


class HrRecruitmentRepository:
    # ------------------------------------------------------------ paket ujian

    # ------------------------------------------------------- ujian (publik)

    @staticmethod
    async def pelamar_dari_token(token: str):
        """
        Baca pelamar dari tokennya, untuk halaman ujian.

        Mengembalikan `None` bila tokennya tidak dikenal, sudah dihapus, atau
        lewat masa berlakunya — ketiganya diperlakukan sama, dan pemanggil
        menjawab dengan pesan yang sama pula. Membedakannya memberi tahu
        penebak bahwa tokennya PERNAH ada.
        """
        try:
            baris = await database.fetch_one(
                select(
                    hr_candidates_table.c.id,
                    hr_candidates_table.c.name,
                    hr_candidates_table.c.gender,
                    hr_candidates_table.c.testID,
                    hr_candidates_table.c.expiresAt,
                    hr_candidates_table.c.startedAt,
                    hr_candidates_table.c.submittedAt,
                    hr_candidates_table.c.status,
                    # Biodata ikut dibaca supaya formulirnya terisi saat
                    # pelamar membuka tautannya kembali — tanpa ini ia
                    # mengetik ulang seluruhnya setiap kali.
                    hr_candidates_table.c.nickName,
                    hr_candidates_table.c.dateOfBirth,
                    hr_candidates_table.c.address,
                    hr_candidates_table.c.city,
                    hr_candidates_table.c.phoneNumber,
                    hr_candidates_table.c.email,
                    hr_tests_table.c.name.label("testName"),
                    hr_tests_table.c.description.label("testDescription"),
                    hr_tests_table.c.durationMinutes,
                )
                .select_from(
                    hr_candidates_table.join(
                        hr_tests_table,
                        hr_candidates_table.c.testID == hr_tests_table.c.id,
                    )
                )
                .where(hr_candidates_table.c.token == token)
                .where(hr_candidates_table.c.isDelete == False)  # noqa: E712
                .where(hr_candidates_table.c.expiresAt > dt.now())
            )
            if baris is None:
                return None

            jumlah = await database.fetch_val(
                select(func.count()).where(
                    hr_questions_table.c.testID == baris["testID"],
                    hr_questions_table.c.isDelete == False,  # noqa: E712
                )
            )

            return {
                "name": baris["name"],
                "gender": baris["gender"],
                "testName": baris["testName"],
                "testDescription": baris["testDescription"],
                "durationMinutes": baris["durationMinutes"],
                "jumlahSoal": int(jumlah or 0),
                "expiresAt": baris["expiresAt"],
                "startedAt": baris["startedAt"],
                "submittedAt": baris["submittedAt"],
                "status": baris["status"],
                "biodata": {
                    "nickName": baris["nickName"],
                    "dateOfBirth": baris["dateOfBirth"],
                    "address": baris["address"],
                    "city": baris["city"],
                    "phoneNumber": baris["phoneNumber"],
                    "email": baris["email"],
                },
                # `id` TIDAK dikembalikan.
                #
                # Halaman ujian tidak memerlukannya — seluruh rutenya
                # menerima token, bukan id — dan nomor pelamar adalah
                # keterangan yang tidak perlu diberikan kepada yang
                # mengerjakan.
            }
        except Exception as e:
            log_error(f"Error reading candidate by token: {str(e)}")
            return None

    @staticmethod
    async def mulai_ujian(token: str):
        """
        Tandai pesertanya MULAI, lalu kembalikan soalnya.

        Waktu mulai dicatat DI SINI, bukan dikirim layar. Waktu dari layar
        dapat diubah siapa pun yang membuka DevTools — dan ujian yang
        timernya dapat diatur peserta tidak mengukur apa pun.

        Bila sudah pernah mulai, `startedAt` TIDAK ditimpa: menutup peramban
        lalu membukanya kembali tidak memberi tambahan waktu. Itu justru
        celah yang paling mudah ditemukan sendiri.
        """
        try:
            baris = await database.fetch_one(
                select(
                    hr_candidates_table.c.id,
                    hr_candidates_table.c.testID,
                    hr_candidates_table.c.startedAt,
                    hr_candidates_table.c.submittedAt,
                    hr_tests_table.c.durationMinutes,
                )
                .select_from(
                    hr_candidates_table.join(
                        hr_tests_table,
                        hr_candidates_table.c.testID == hr_tests_table.c.id,
                    )
                )
                .where(hr_candidates_table.c.token == token)
                .where(hr_candidates_table.c.isDelete == False)  # noqa: E712
                .where(hr_candidates_table.c.expiresAt > dt.now())
            )
            if baris is None:
                return None

            if baris["submittedAt"]:
                return {"error": "Ujian sudah dikirim.", "status": 409}

            mulai = baris["startedAt"]
            if not mulai:
                mulai = dt.now()
                await database.execute(
                    update(hr_candidates_table)
                    .where(hr_candidates_table.c.id == baris["id"])
                    .values(startedAt=mulai, status="mengerjakan")
                )

            durasi = int(baris["durationMinutes"] or 90)
            batas = mulai + timedelta(minutes=durasi)
            sisa = int((batas - dt.now()).total_seconds())

            soal = await database.fetch_all(
                select(
                    hr_questions_table.c.id,
                    hr_questions_table.c.sortOrder,
                    hr_questions_table.c.question,
                    hr_questions_table.c.notes,
                    hr_questions_table.c.attachment,
                    hr_questions_table.c.category,
                    hr_questions_table.c.maxScore,
                    hr_questions_table.c.allowsUpload,
                )
                .where(hr_questions_table.c.testID == baris["testID"])
                .where(hr_questions_table.c.isDelete == False)  # noqa: E712
                .order_by(hr_questions_table.c.sortOrder)
            )

            jawaban = await database.fetch_all(
                select(
                    hr_answers_table.c.questionID,
                    hr_answers_table.c.answer,
                ).where(hr_answers_table.c.candidateID == baris["id"])
            )

            return {
                "startedAt": mulai,
                # Sisa waktu dalam DETIK, dihitung server.
                #
                # Layar menampilkan hitungan mundurnya sendiri, tetapi yang
                # menentukan tetap angka ini — ia diperiksa ulang setiap kali
                # jawaban disimpan.
                "sisaDetik": max(sisa, 0),
                "durationMinutes": durasi,
                # Urutannya DIACAK per pelamar, stabil sepanjang lembar
                # itu — lihat `urutan_acak`. Urutan aslinya tetap terbawa
                # sebagai `sortOrder`, dan lembar penilaian HR memakai itu.
                # Tokennya diambil dari PARAMETER, bukan dari `baris`:
                # kueri di atas tidak memilih kolom `token`, dan
                # `Record["token"]` untuk kolom yang tidak dipilih melempar
                # KeyError — galatnya tertelan `except` dan seluruh ujian
                # gagal dimuat dengan pesan 500 yang tidak menyebut sebabnya.
                "questions": urutan_acak([dict(r) for r in soal], token),
                "answers": {
                    str(r["questionID"]): r["answer"] for r in jawaban
                },
            }
        except Exception as e:
            log_error(f"Error starting exam: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def sisa_waktu(candidate_id: int):
        """
        Sisa waktu dalam detik; negatif berarti sudah lewat.

        Dihitung ulang dari basis data setiap kali, bukan disimpan — nilai
        yang disimpan akan basi begitu ada yang menyentuh jam sistemnya.
        """
        baris = await database.fetch_one(
            select(
                hr_candidates_table.c.startedAt,
                hr_tests_table.c.durationMinutes,
            )
            .select_from(
                hr_candidates_table.join(
                    hr_tests_table,
                    hr_candidates_table.c.testID == hr_tests_table.c.id,
                )
            )
            .where(hr_candidates_table.c.id == candidate_id)
        )
        if baris is None or not baris["startedAt"]:
            return None
        batas = baris["startedAt"] + timedelta(
            minutes=int(baris["durationMinutes"] or 90)
        )
        return int((batas - dt.now()).total_seconds())

    @staticmethod
    async def simpan_jawaban(token: str, jawaban: dict):
        """
        Simpan jawaban yang sedang dikerjakan.

        Dipanggil berkala oleh layar, bukan hanya saat mengirim: koneksi di
        rumah pelamar kerap putus, dan kehilangan satu jam pengerjaan karena
        satu kali putus adalah kegagalan yang tidak dapat diperbaiki
        sesudahnya.

        Waktu diperiksa DI SINI juga. Layar boleh saja tetap terbuka setelah
        timernya habis — yang menentukan adalah jam server.
        """
        try:
            # KEDALUWARSA TAUTAN MENENTUKAN BOLEH-TIDAKNYA **MULAI**,
            # bukan boleh-tidaknya melanjutkan.
            #
            # Sebelumnya syaratnya `expiresAt > now` polos, sama seperti pada
            # pintu masuknya. Akibatnya pelamar yang mulai sepuluh menit
            # sebelum tautannya kedaluwarsa tetap melihat sisa 90 menit di
            # layarnya — lalu SETIAP autosave sesudah menit kesepuluh dijawab
            # 404, dan tidak satu pun jawabannya tersimpan lagi. Ia terus
            # mengetik selama 80 menit ke dalam kekosongan.
            #
            # Lebih jauh: lima kegagalan beruntun memicu pembatas laju, jadi
            # IP-nya ikut terkunci lima belas menit. Dengan autosave berkala,
            # lima kegagalan itu tercapai dalam waktu di bawah satu menit.
            #
            # Yang membatasi lamanya mengerjakan adalah `durationMinutes`,
            # dan itu sudah diperiksa di bawah lewat `sisa_waktu`.
            pelamar = await database.fetch_one(
                select(
                    hr_candidates_table.c.id,
                    hr_candidates_table.c.testID,
                    hr_candidates_table.c.submittedAt,
                )
                .where(hr_candidates_table.c.token == token)
                .where(hr_candidates_table.c.isDelete == False)  # noqa: E712
                .where(
                    or_(
                        hr_candidates_table.c.expiresAt > dt.now(),
                        hr_candidates_table.c.startedAt.isnot(None),
                    )
                )
            )
            if pelamar is None:
                return None
            if pelamar["submittedAt"]:
                return {"error": "Ujian sudah dikirim.", "status": 409}

            sisa = await HrRecruitmentRepository.sisa_waktu(pelamar["id"])
            if sisa is None:
                return {"error": "Ujian belum dimulai.", "status": 400}
            if sisa <= 0:
                return {"error": "Waktu pengerjaan sudah habis.", "status": 410}

            # Hanya soal MILIK paket ujiannya yang diterima.
            #
            # Muatan dapat disusun sendiri oleh siapa pun; tanpa penyaringan
            # ini, jawaban dapat ditulis ke soal paket lain — dan lembar
            # jawaban pelamar lain ikut tersentuh.
            sah = {
                r["id"]
                for r in await database.fetch_all(
                    select(hr_questions_table.c.id)
                    .where(hr_questions_table.c.testID == pelamar["testID"])
                    .where(hr_questions_table.c.isDelete == False)  # noqa: E712
                )
            }

            sekarang = dt.now()
            for kunci, isi in (jawaban or {}).items():
                try:
                    qid = int(kunci)
                except (TypeError, ValueError):
                    continue
                if qid not in sah:
                    continue

                ada = await database.fetch_val(
                    select(hr_answers_table.c.id)
                    .where(hr_answers_table.c.candidateID == pelamar["id"])
                    .where(hr_answers_table.c.questionID == qid)
                )
                if ada:
                    await database.execute(
                        update(hr_answers_table)
                        .where(hr_answers_table.c.id == ada)
                        .values(answer=isi, updatedAt=sekarang)
                    )
                else:
                    await database.execute(
                        insert(hr_answers_table).values(
                            candidateID=pelamar["id"],
                            questionID=qid,
                            answer=isi,
                            updatedAt=sekarang,
                        )
                    )

            return {"tersimpan": True, "sisaDetik": sisa}
        except Exception as e:
            log_error(f"Error saving exam answers: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def kirim_ujian(token: str, jawaban: dict = None):
        """
        Kirim jawaban akhir; setelah ini tidak dapat disunting lagi.

        Jawaban terakhir ikut disimpan lebih dulu — yang menekan Kirim kerap
        baru saja mengetik sesuatu, dan menyimpannya terpisah membuat ketikan
        terakhir hilang.
        """
        try:
            if jawaban:
                hasil = await HrRecruitmentRepository.simpan_jawaban(
                    token, jawaban
                )
                # Waktu habis tidak menghalangi pengiriman: yang sudah
                # tersimpan tetap dikirim, dan penilailah yang memutuskan.
                if isinstance(hasil, dict) and hasil.get("status") == 500:
                    return hasil

            pelamar = await database.fetch_one(
                select(
                    hr_candidates_table.c.id,
                    hr_candidates_table.c.submittedAt,
                )
                .where(hr_candidates_table.c.token == token)
                .where(hr_candidates_table.c.isDelete == False)  # noqa: E712
            )
            if pelamar is None:
                return None
            if pelamar["submittedAt"]:
                return {"error": "Ujian sudah dikirim.", "status": 409}

            await database.execute(
                update(hr_candidates_table)
                .where(hr_candidates_table.c.id == pelamar["id"])
                .values(submittedAt=dt.now(), status="selesai")
            )
            return {"terkirim": True}
        except Exception as e:
            log_error(f"Error submitting exam: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    # -------------------------------------------------------------- pelamar

    @staticmethod
    async def daftarkan_pelamar(
        test_id: int, orang: list[dict], user_id: int, berlaku_hari: int = 7
    ):
        """
        Daftarkan beberapa pelamar sekaligus, masing-masing dengan tokennya.

        Yang diminta hanya nama dan jenis kelamin. Sisanya — panggilan,
        tanggal lahir, alamat, kontak — diisi pelamar sendiri lewat tautan;
        mengumpulkannya lebih dulu justru pekerjaan yang hendak dihilangkan.

        Berlaku tujuh hari, bukan tiga seperti formulir karyawan: pelamar
        belum terikat apa pun pada perusahaan, dan yang sedang mencari kerja
        kerap baru membuka surel di akhir pekan.
        """
        try:
            sekarang = dt.now()
            kedaluwarsa = sekarang + timedelta(days=berlaku_hari)

            hasil = []
            for o in orang:
                nama = str(o.get("name") or "").strip()
                if not nama:
                    # Baris kosong dilewati diam-diam.
                    #
                    # Menempel daftar nama kerap membawa baris kosong di
                    # ujungnya, dan menolak seluruh permintaan karenanya
                    # memaksa yang menempelnya merapikan dulu.
                    continue

                jk = str(o.get("gender") or "").strip().upper()[:1]
                token = secrets.token_urlsafe(32)

                pelamar_id = await database.execute(
                    insert(hr_candidates_table).values(
                        testID=test_id,
                        name=nama,
                        gender=jk if jk in ("L", "P") else None,
                        token=token,
                        expiresAt=kedaluwarsa,
                        status="baru",
                        createdAt=sekarang,
                        createdBy=user_id,
                    )
                )
                hasil.append(
                    {
                        "id": pelamar_id,
                        "name": nama,
                        "gender": jk if jk in ("L", "P") else None,
                        "token": token,
                        "expiresAt": kedaluwarsa,
                    }
                )

            return {"dibuat": len(hasil), "pelamar": hasil}
        except Exception as e:
            log_error(f"Error registering candidates: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def daftar_pelamar(
        test_id: int = None,
        status: str = None,
        ember: str = None,
        cari: str = None,
    ):
        """
        Pelamar beserta paket ujiannya.

        `ember` memilih kelompok menu samping; `status` yang lama tetap
        diterima supaya pemanggil lain tidak ikut berubah. Bila keduanya
        diberikan, keduanya berlaku — penyaring saling mempersempit, tidak
        saling membatalkan.

        TANPA `ember`, yang dihapus TIDAK ikut: itu perilaku lama, dan
        satu-satunya cara melihatnya adalah meminta embernya sendiri.
        """
        try:
            syarat_ember = _syarat_ember(ember) if ember else None
            if ember and syarat_ember is None:
                return app_error(
                    ErrorCode.VALIDATION,
                    "Kelompok tidak dikenal: " + ", ".join(EMBER),
                    400,
                )
            syarat = list(
                syarat_ember
                if syarat_ember is not None
                else [hr_candidates_table.c.isDelete == False]  # noqa: E712
            )
            if test_id:
                syarat.append(hr_candidates_table.c.testID == test_id)
            if status:
                syarat.append(hr_candidates_table.c.status == status)

            kata = (cari or "").strip()
            if kata:
                # `%` dan `_` DILARIKAN. Tanpa ini, mengetik "_" di kotak
                # pencarian mencocokkan aksara apa pun, dan yang mencari
                # nomor telepon dengan garis bawah mendapat seluruh daftar
                # tanpa satu pun tanda bahwa pencariannya tidak dijalankan.
                aman = kata.replace("\\", "\\\\").replace("%", "\\%")
                aman = aman.replace("_", "\\_")
                pola = f"%{aman}%"
                syarat.append(
                    or_(
                        # `escape` DISEBUT: tanpa itu aksara pelarian
                        # bergantung pada mesin basis datanya, dan
                        # pelariannya di atas menjadi sia-sia diam-diam.
                        hr_candidates_table.c.name.like(pola, escape="\\"),
                        hr_candidates_table.c.nickName.like(pola, escape="\\"),
                        hr_candidates_table.c.email.like(pola, escape="\\"),
                        hr_candidates_table.c.phoneNumber.like(
                            pola, escape="\\"
                        ),
                        hr_candidates_table.c.city.like(pola, escape="\\"),
                        hr_tests_table.c.name.like(pola, escape="\\"),
                    )
                )

            baris = await database.fetch_all(
                select(
                    hr_candidates_table.c.id,
                    hr_candidates_table.c.testID,
                    hr_candidates_table.c.name,
                    hr_candidates_table.c.gender,
                    hr_candidates_table.c.email,
                    hr_candidates_table.c.phoneNumber,
                    hr_candidates_table.c.token,
                    hr_candidates_table.c.expiresAt,
                    hr_candidates_table.c.startedAt,
                    hr_candidates_table.c.submittedAt,
                    hr_candidates_table.c.status,
                    hr_candidates_table.c.isDelete,
                    hr_candidates_table.c.createdAt,
                    hr_tests_table.c.name.label("testName"),
                )
                .select_from(
                    hr_candidates_table.join(
                        hr_tests_table,
                        hr_candidates_table.c.testID == hr_tests_table.c.id,
                    )
                )
                .where(*syarat)
                .order_by(hr_candidates_table.c.id.desc())
            )
            return [dict(r) for r in baris]
        except Exception as e:
            log_error(f"Error listing candidates: {str(e)}")
            return {"error": "Internal server error.", "status": 500}


    @staticmethod
    async def ringkasan_pelamar(test_id: int = None):
        """
        Jumlah pelamar per ember, dalam SATU pertanyaan ke basis data.

        Enam hitungan berarti enam perjalanan bolak-balik bila ditanyakan
        satu per satu, dan angkanya lalu berasal dari enam saat yang
        berbeda: pelamar yang statusnya berubah di antara dua hitungan
        muncul di dua ember sekaligus, atau lenyap dari keduanya.

        Penjumlahan bersyarat menjawabnya sekali, dari satu pembacaan.
        """
        try:
            def _hitung(nama: str):
                syarat = _syarat_ember(nama)
                return func.sum(
                    case((and_(*syarat), 1), else_=0)
                ).label(nama)

            q = select(*[_hitung(n) for n in EMBER])
            if test_id:
                q = q.where(hr_candidates_table.c.testID == test_id)

            baris = await database.fetch_one(q)
            if baris is None:
                return {n: 0 for n in EMBER}
            return {n: int(baris[n] or 0) for n in EMBER}
        except Exception as e:
            log_error(f"Error summarising candidates: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def _selaraskan_status_nilai(candidate_id: int, test_id: int):
        """
        Naikkan ke `dinilai` bila SELURUH soal sudah bernilai; turunkan lagi
        bila ada yang dicabut.

        HANYA bergerak di antara `selesai` dan `dinilai`. Status yang
        diputuskan manusia — `diwawancara`, `diterima`, `ditolak`,
        `gagal_wawancara` — tidak
        pernah disentuh: seseorang yang sudah diwawancarai lalu nilainya
        diperbaiki satu angka tidak boleh mundur menjadi "baru dinilai".

        Yang belum mengirim juga tidak disentuh. Jawabannya memang boleh
        dinilai — lembar yang ditinggalkan di tengah tetap layak dibaca —
        tetapi menaikkannya ke `dinilai` akan menyembunyikan kenyataan
        bahwa pelamarnya tidak pernah menyelesaikan ujiannya.
        """
        try:
            baris = await database.fetch_one(
                select(
                    hr_candidates_table.c.status,
                    hr_candidates_table.c.submittedAt,
                ).where(hr_candidates_table.c.id == candidate_id)
            )
            if baris is None or not baris["submittedAt"]:
                return
            if baris["status"] not in (STATUS_SELESAI, STATUS_DINILAI):
                return

            jumlah_soal = await database.fetch_val(
                select(func.count(hr_questions_table.c.id))
                .where(hr_questions_table.c.testID == test_id)
                .where(hr_questions_table.c.isDelete == False)  # noqa: E712
            )
            jumlah_nilai = await database.fetch_val(
                select(func.count(hr_answers_table.c.id))
                .where(hr_answers_table.c.candidateID == candidate_id)
                .where(hr_answers_table.c.score.isnot(None))
            )

            penuh = int(jumlah_soal or 0) > 0 and int(jumlah_nilai or 0) >= int(
                jumlah_soal or 0
            )
            tujuan = STATUS_DINILAI if penuh else STATUS_SELESAI
            if tujuan != baris["status"]:
                await database.execute(
                    update(hr_candidates_table)
                    .where(hr_candidates_table.c.id == candidate_id)
                    .values(status=tujuan)
                )
        except Exception as e:  # noqa: BLE001
            # Gagal menyelaraskan status TIDAK menggagalkan penilaiannya.
            # Nilainya sudah tersimpan; yang meleset hanya label di daftar,
            # dan itu akan benar sendiri pada penyimpanan berikutnya.
            log_error(f"Gagal menyelaraskan status nilai: {str(e)}")

    @staticmethod
    async def ubah_status_pelamar(candidate_id: int, status: str, user_id: int):
        """
        Setel status yang DIPUTUSKAN MANUSIA.

        Hanya `diwawancara`, `diterima`, `ditolak`, `gagal_wawancara`. Status lainnya
        disimpulkan dari keadaan dokumennya, dan membiarkannya disetel
        lewat rute ini berarti daftar dapat menyatakan "sudah dinilai" atas
        lembar yang belum disentuh siapa pun.
        """
        try:
            if status not in STATUS_MANUAL:
                return app_error(
                    ErrorCode.VALIDATION,
                    "Status ini ditentukan sistem dari keadaan dokumennya, "
                    "jadi tidak dapat disetel dari sini. Yang dapat disetel: "
                    + ", ".join(STATUS_MANUAL)
                    + ".",
                    400,
                )

            baris = await database.fetch_one(
                select(
                    hr_candidates_table.c.id,
                    hr_candidates_table.c.submittedAt,
                )
                .where(hr_candidates_table.c.id == candidate_id)
                .where(hr_candidates_table.c.isDelete == False)  # noqa: E712
            )
            if baris is None:
                return app_error(
                    ErrorCode.NOT_FOUND, "Pelamar tidak ditemukan.", 404
                )

            nilai = {"status": status, "decidedAt": dt.now(), "decidedBy": user_id}
            await database.execute(
                update(hr_candidates_table)
                .where(hr_candidates_table.c.id == candidate_id)
                .values(**nilai)
            )
            return {"id": candidate_id, "status": status}
        except Exception as e:  # noqa: BLE001
            log_error(f"Error updating candidate status: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def hapus_hasil(candidate_id: int, user_id: int):
        """
        Hapus HASIL ujiannya, kembalikan pelamarnya ke awal.

        BUKAN menghapus pelamarnya. Jawabannya dibuang, `startedAt` dan
        `submittedAt` dikosongkan, statusnya kembali `baru` — dan tautan
        yang SAMA dapat dipakai mengerjakan lagi.

        Itu yang diperlukan untuk mencoba alurnya berulang kali. Menghapus
        pelamarnya berarti mendaftarkan yang baru dan menyalin tautan baru
        setiap kali.

        TIDAK DAPAT DIBATALKAN, dan karena itu dijaga `delete` — yang pada
        modul ini bernilai 5, hanya pemilik usaha.
        """
        try:
            baris = await database.fetch_one(
                select(hr_candidates_table.c.id)
                .where(hr_candidates_table.c.id == candidate_id)
                .where(hr_candidates_table.c.isDelete == False)  # noqa: E712
            )
            if baris is None:
                return app_error(
                    ErrorCode.NOT_FOUND, "Pelamar tidak ditemukan.", 404
                )

            terhapus = await database.execute(
                hr_answers_table.delete().where(
                    hr_answers_table.c.candidateID == candidate_id
                )
            )
            await database.execute(
                update(hr_candidates_table)
                .where(hr_candidates_table.c.id == candidate_id)
                .values(
                    startedAt=None,
                    submittedAt=None,
                    status="baru",
                    decidedAt=None,
                    decidedBy=None,
                )
            )

            from repository.audit_log_repository import AuditLogRepository

            # DICATAT. Ini satu-satunya tindakan di modul ini yang membuang
            # pekerjaan orang lain tanpa dapat dikembalikan.
            await AuditLogRepository.record(
                entity="hr_candidates",
                entityID=candidate_id,
                action="hapus_hasil",
                userID=user_id,
                changes={"jawabanDihapus": terhapus},
            )
            return {"id": candidate_id, "jawabanDihapus": terhapus}
        except Exception as e:  # noqa: BLE001
            log_error(f"Error resetting candidate result: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def hapus_pelamar(candidate_id: int, user_id: int):
        """
        Hapus PELAMARNYA — bukan hanya hasilnya. Tautannya mati seketika.

        KENAPA INI PERLU. Ember "Dihapus" di menu samping menghitung
        `isDelete = 1`, dan sebelum ini tidak ada satu pun tindakan yang
        menyetelnya: "Hapus hasil & ulangi" hanya membuang jawaban. Embernya
        terpasang, lencananya tampil, dan angkanya nol selamanya — satu
        kelompok yang tidak mungkin terisi.

        LUNAK, bukan dibuang dari tabel. Jawaban dan nilainya DIPERTAHANKAN:
        pelamar yang terhapus karena salah pencet dapat dipulihkan utuh,
        dengan lembar yang sama, lewat `pulihkan_pelamar`.

        TAUTANNYA MATI karena setiap pintu masuk bertoken — membuka, mulai,
        menyimpan, mengirim, biodata — menyaring `isDelete = 0`. Termasuk
        yang sedang mengerjakan: simpanan otomatis berikutnya ditolak.

        ATOMIK: syarat `isDelete = 0` berada DI DALAM `UPDATE`, bukan dibaca
        lebih dulu. Dua orang yang menekan hapus bersamaan tidak sama-sama
        menerima "berhasil"; yang kedua mendapat 404.
        """
        try:
            terpengaruh = await database.execute(
                update(hr_candidates_table)
                .where(hr_candidates_table.c.id == candidate_id)
                .where(hr_candidates_table.c.isDelete == False)  # noqa: E712
                .values(isDelete=True)
            )
            if not terpengaruh:
                return app_error(
                    ErrorCode.NOT_FOUND,
                    "Pelamar tidak ditemukan atau sudah dihapus.",
                    404,
                )

            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="hr_candidates",
                entityID=candidate_id,
                action="hapus_pelamar",
                userID=user_id,
                changes={"isDelete": True},
            )
            return {"id": candidate_id, "isDelete": True}
        except Exception as e:  # noqa: BLE001
            log_error(f"Error deleting candidate: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def pulihkan_pelamar(candidate_id: int, user_id: int):
        """
        Kembalikan pelamar yang terhapus — tautan, jawaban, dan nilainya utuh.

        Ember "Dihapus" tanpa jalan pulang adalah jebakan: yang terhapus
        karena salah pencet hanya dapat dikembalikan lewat SQL langsung.
        Penghapusannya lunak justru supaya pintu ini ada.

        Masa berlaku tautannya TIDAK diperpanjang. Tautan yang sudah lewat
        tetap lewat; memulihkan bukan menerbitkan ulang.
        """
        try:
            terpengaruh = await database.execute(
                update(hr_candidates_table)
                .where(hr_candidates_table.c.id == candidate_id)
                .where(hr_candidates_table.c.isDelete == True)  # noqa: E712
                .values(isDelete=False)
            )
            if not terpengaruh:
                return app_error(
                    ErrorCode.NOT_FOUND,
                    "Pelamar tidak ditemukan atau tidak sedang terhapus.",
                    404,
                )

            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="hr_candidates",
                entityID=candidate_id,
                action="pulihkan_pelamar",
                userID=user_id,
                changes={"isDelete": False},
            )
            return {"id": candidate_id, "isDelete": False}
        except Exception as e:  # noqa: BLE001
            log_error(f"Error restoring candidate: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def lembar_jawaban(candidate_id: int):
        """
        Seluruh soal paket ini beserta jawaban dan nilai pelamarnya.

        SOAL DULU, JAWABAN MENYUSUL — bukan sebaliknya.

        Kalau yang dibaca daftar `hr_answers`, soal yang TIDAK DIJAWAB hilang
        dari lembar penilaian; yang memeriksa lalu memberi nilai atas 18 soal
        dan mengira itu seluruhnya, padahal paketnya 24. Soal kosong justru
        keterangan: ia berarti pelamarnya tidak sempat atau tidak bisa.

        Nilai `None` DIPERTAHANKAN apa adanya, tidak diubah jadi nol. Nol
        adalah keputusan bahwa jawabannya salah; belum diperiksa adalah
        keadaan lain, dan keduanya tidak boleh tertukar saat menghitung yang
        masih harus dikerjakan.
        """
        try:
            pelamar = await database.fetch_one(
                select(
                    hr_candidates_table.c.id,
                    hr_candidates_table.c.testID,
                    hr_candidates_table.c.name,
                    hr_candidates_table.c.gender,
                    hr_candidates_table.c.token,
                    hr_candidates_table.c.status,
                    hr_candidates_table.c.startedAt,
                    hr_candidates_table.c.submittedAt,
                    hr_tests_table.c.name.label("testName"),
                    hr_tests_table.c.durationMinutes,
                )
                .select_from(
                    hr_candidates_table.join(
                        hr_tests_table,
                        hr_candidates_table.c.testID == hr_tests_table.c.id,
                    )
                )
                .where(hr_candidates_table.c.id == candidate_id)
                .where(hr_candidates_table.c.isDelete == False)  # noqa: E712
            )
            if not pelamar:
                return app_error(
                    ErrorCode.NOT_FOUND, "Pelamar tidak ditemukan.", 404
                )

            soal = await database.fetch_all(
                select(
                    hr_questions_table.c.id,
                    hr_questions_table.c.question,
                    hr_questions_table.c.notes,
                    hr_questions_table.c.attachment,
                    hr_questions_table.c.category,
                    hr_questions_table.c.maxScore,
                    hr_questions_table.c.allowsUpload,
                    hr_questions_table.c.sortOrder,
                )
                .where(hr_questions_table.c.testID == pelamar["testID"])
                .where(hr_questions_table.c.isDelete == False)  # noqa: E712
                .order_by(hr_questions_table.c.sortOrder)
            )

            jawaban = await database.fetch_all(
                select(
                    hr_answers_table.c.id,
                    hr_answers_table.c.questionID,
                    hr_answers_table.c.answer,
                    hr_answers_table.c.score,
                    hr_answers_table.c.checkerNote,
                    hr_answers_table.c.checkedAt,
                    hr_answers_table.c.checkedBy,
                    users_table.c.name.label("checkedByName"),
                )
                .select_from(
                    hr_answers_table.outerjoin(
                        users_table,
                        hr_answers_table.c.checkedBy == users_table.c.id,
                    )
                )
                .where(hr_answers_table.c.candidateID == candidate_id)
            )
            peta = {int(r["questionID"]): r for r in jawaban}

            baris = []
            total_nilai = 0
            total_maks = 0
            belum_dinilai = 0
            for q in soal:
                j = peta.get(int(q["id"]))
                nilai = j["score"] if j is not None else None
                maks = int(q["maxScore"] or 0)
                total_maks += maks
                if nilai is None:
                    belum_dinilai += 1
                else:
                    total_nilai += int(nilai)
                baris.append(
                    {
                        "questionID": int(q["id"]),
                        "question": q["question"],
                        "notes": q["notes"],
                        "attachment": q["attachment"],
                        "category": q["category"],
                        "maxScore": maks,
                        "allowsUpload": bool(q["allowsUpload"]),
                        "answerID": (j["id"] if j is not None else None),
                        # Dibedakan dari string kosong: tidak ada baris
                        # jawaban sama sekali berarti soal ini tidak pernah
                        # disentuh, dan itu bukan hal yang sama dengan
                        # dijawab lalu dikosongkan.
                        "answer": (j["answer"] if j is not None else None),
                        "score": nilai,
                        "checkerNote": (
                            j["checkerNote"] if j is not None else None
                        ),
                        "checkedAt": (j["checkedAt"] if j is not None else None),
                        "checkedByName": (
                            j["checkedByName"] if j is not None else None
                        ),
                    }
                )

            return {
                "pelamar": {
                    "id": int(pelamar["id"]),
                    "name": pelamar["name"],
                    "gender": pelamar["gender"],
                    "kodePeserta": kode_peserta(pelamar["token"]),
                    "status": pelamar["status"],
                    "startedAt": pelamar["startedAt"],
                    "submittedAt": pelamar["submittedAt"],
                    "testName": pelamar["testName"],
                    "durationMinutes": pelamar["durationMinutes"],
                },
                "soal": baris,
                "rekap": {
                    "jumlahSoal": len(baris),
                    "belumDinilai": belum_dinilai,
                    "totalNilai": total_nilai,
                    "totalMaks": total_maks,
                },
            }
        except Exception as e:  # noqa: BLE001
            log_error(f"Error reading answer sheet: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def nilai_jawaban(
        candidate_id: int, nilai: list, user_id: int
    ):
        """
        Simpan nilai & catatan pemeriksa untuk beberapa soal sekaligus.

        SEKALIGUS, bukan satu per satu: yang memeriksa membaca 24 jawaban lalu
        menekan Simpan satu kali. Menyimpan per soal berarti 24 permintaan,
        dan bila yang kesepuluh gagal, lembar itu separuh dinilai tanpa ada
        yang tahu bagian mana.

        Nilai `None` MENGHAPUS penilaian, bukan menyimpan nol — itu cara
        membatalkan penilaian yang terlanjur keliru. Nol tetap tersimpan
        sebagai nol: ia keputusan bahwa jawabannya salah.

        Baris jawaban DIBUAT bila belum ada. Soal yang tidak dijawab tetap
        harus dapat dinilai — nol untuk yang dikosongkan adalah penilaian
        yang sah, dan tanpa ini soal itu tidak dapat dinilai sama sekali.
        """
        try:
            pelamar = await database.fetch_one(
                select(
                    hr_candidates_table.c.id,
                    hr_candidates_table.c.testID,
                )
                .where(hr_candidates_table.c.id == candidate_id)
                .where(hr_candidates_table.c.isDelete == False)  # noqa: E712
            )
            if not pelamar:
                return app_error(
                    ErrorCode.NOT_FOUND, "Pelamar tidak ditemukan.", 404
                )

            # Soal yang SAH untuk pelamar ini — dan nilai maksimumnya.
            #
            # Dibaca dari basis data, tidak dipercaya dari muatan: tanpa ini,
            # permintaan yang disusun sendiri dapat memberi nilai pada soal
            # milik paket lain, atau nilai 999 pada soal bernilai maksimum 5.
            soal = await database.fetch_all(
                select(
                    hr_questions_table.c.id,
                    hr_questions_table.c.maxScore,
                )
                .where(hr_questions_table.c.testID == pelamar["testID"])
                .where(hr_questions_table.c.isDelete == False)  # noqa: E712
            )
            maks = {int(r["id"]): int(r["maxScore"] or 0) for r in soal}

            sekarang = dt.now()
            tersimpan = 0
            ditolak = []

            for item in nilai or []:
                try:
                    qid = int(item.get("questionID"))
                except (TypeError, ValueError):
                    continue
                if qid not in maks:
                    ditolak.append(qid)
                    continue

                skor = item.get("score", None)
                if skor is not None:
                    try:
                        skor = int(skor)
                    except (TypeError, ValueError):
                        ditolak.append(qid)
                        continue
                    if skor < 0 or skor > maks[qid]:
                        ditolak.append(qid)
                        continue

                catatan = item.get("checkerNote")
                if catatan is not None:
                    catatan = str(catatan)[:500]

                isi = {
                    "score": skor,
                    "checkerNote": catatan,
                    # Jejak pemeriksaannya ikut DICABUT saat nilainya
                    # dihapus: "diperiksa oleh X" pada baris tanpa nilai
                    # menyatakan pemeriksaan yang hasilnya tidak ada.
                    "checkedAt": (sekarang if skor is not None else None),
                    "checkedBy": (user_id if skor is not None else None),
                }

                ada = await database.fetch_val(
                    select(hr_answers_table.c.id)
                    .where(hr_answers_table.c.candidateID == candidate_id)
                    .where(hr_answers_table.c.questionID == qid)
                )
                if ada:
                    await database.execute(
                        update(hr_answers_table)
                        .where(hr_answers_table.c.id == ada)
                        .values(**isi)
                    )
                else:
                    await database.execute(
                        insert(hr_answers_table).values(
                            candidateID=candidate_id,
                            questionID=qid,
                            answer=None,
                            # `hr_answers` TIDAK punya `createdAt` — hanya
                            # `updatedAt`. Menyebut kolom yang tidak ada
                            # membuat SQLAlchemy menolak seluruh pernyataan
                            # dengan "Unconsumed column names", galatnya
                            # tertelan `except`, dan jawabannya 500 tanpa
                            # menyebut sebabnya. Persis cacat yang sudah ada
                            # di `expense_repository.approve`.
                            updatedAt=sekarang,
                            **isi,
                        )
                    )
                tersimpan += 1

            await HrRecruitmentRepository._selaraskan_status_nilai(
                candidate_id, pelamar["testID"]
            )
            return {"tersimpan": tersimpan, "ditolak": ditolak}
        except Exception as e:  # noqa: BLE001
            log_error(f"Error scoring answers: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def _sedang_mengerjakan(test_id: int) -> int:
        """
        Berapa pelamar yang SEDANG mengerjakan paket ini saat ini juga.

        "Sedang" berarti sudah menekan Mulai, belum mengirim, dan waktunya
        belum habis. Yang sudah lewat waktunya tidak dihitung: mengubah
        durasi tidak lagi berpengaruh apa pun baginya.
        """
        baris = await database.fetch_all(
            select(
                hr_candidates_table.c.startedAt,
                hr_tests_table.c.durationMinutes,
            )
            .select_from(
                hr_candidates_table.join(
                    hr_tests_table,
                    hr_candidates_table.c.testID == hr_tests_table.c.id,
                )
            )
            .where(hr_candidates_table.c.testID == test_id)
            .where(hr_candidates_table.c.isDelete == False)  # noqa: E712
            .where(hr_candidates_table.c.startedAt.isnot(None))
            .where(hr_candidates_table.c.submittedAt.is_(None))
        )
        sekarang = dt.now()
        n = 0
        for r in baris:
            batas = r["startedAt"] + timedelta(
                minutes=int(r["durationMinutes"] or 90)
            )
            if batas > sekarang:
                n += 1
        return n

    @staticmethod
    async def simpan_biodata(token: str, data: dict):
        """
        Biodata yang diisi PELAMAR sendiri lewat tautannya.

        Kolomnya sudah ada di `hr_candidates` sejak awal, dengan keterangan
        "diisi sendiri lewat tautan" — dan tidak pernah ada satu pun
        formulir yang mengisinya. Seluruhnya tetap NULL.

        Diisi SEBELUM menekan Mulai, jadi tidak memakan waktu ujian. Setelah
        itu formulirnya tidak ditampilkan lagi — layar pengerjaan tidak
        memuatnya — sehingga penjagaan kedaluwarsa di sini menutup jendela
        yang sama dengan tombol Mulai, bukan jendela yang lebih sempit.

        Tidak ada kolom BARU untuk ini: keenam kolomnya sudah ada di
        `hr_candidates` sejak tabelnya dibuat, dengan keterangan "diisi
        sendiri lewat tautan", dan selama ini tidak pernah ada formulir yang
        mengisinya.

        Nama TIDAK ikut diubah di sini. Ia dimasukkan HR saat mendaftarkan,
        dan dipakai mencocokkan lembar dengan orangnya; membiarkan pelamar
        menggantinya membuat pencocokan itu putus.
        """
        try:
            baris = await database.fetch_one(
                select(
                    hr_candidates_table.c.id,
                    hr_candidates_table.c.submittedAt,
                )
                .where(hr_candidates_table.c.token == token)
                .where(hr_candidates_table.c.isDelete == False)  # noqa: E712
                .where(hr_candidates_table.c.expiresAt > dt.now())
            )
            if baris is None:
                return None
            if baris["submittedAt"]:
                return {"error": "Ujian sudah dikirim.", "status": 409}

            BIDANG = (
                "nickName",
                "dateOfBirth",
                "address",
                "city",
                "phoneNumber",
                "email",
            )
            nilai = {}
            for k in BIDANG:
                if k not in data:
                    continue
                v = data[k]
                if isinstance(v, str):
                    v = v.strip() or None
                nilai[k] = v
            if not nilai:
                return {"message": "No changes"}

            await database.execute(
                update(hr_candidates_table)
                .where(hr_candidates_table.c.id == baris["id"])
                .values(**nilai)
            )
            return {"tersimpan": True}
        except Exception as e:  # noqa: BLE001
            log_error(f"Error saving candidate bio: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def buat_ujian(data: dict, user_id: int):
        """
        Paket ujian baru.

        `createdAt` DIISI DI SINI, bukan diserahkan ke bawaan kolom: pustaka
        `databases` menjalankan kueri yang sudah terkompilasi, sehingga
        bawaan sisi-Python (`default=dt.now`) tidak pernah berjalan dan
        kolomnya menolak NULL.
        """
        try:
            nilai = {
                "name": (data.get("name") or "").strip(),
                "description": (data.get("description") or None),
                "durationMinutes": int(data.get("durationMinutes") or 90),
                "isActive": bool(data.get("isActive", True)),
                "isDelete": False,
                "createdAt": dt.now(),
                "createdBy": user_id,
            }
            if not nilai["name"]:
                return app_error(
                    ErrorCode.VALIDATION, "Nama paket ujian wajib diisi.", 400
                )

            test_id = await database.execute(
                insert(hr_tests_table).values(**nilai)
            )
            return {"id": test_id}
        except Exception as e:  # noqa: BLE001
            log_error(f"Error creating exam package: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def ubah_ujian(test_id: int, data: dict, user_id: int):
        """
        Ubah paket ujian.

        DURASI TIDAK BOLEH DIUBAH SELAGI ADA YANG MENGERJAKAN.

        `sisa_waktu` membaca `durationMinutes` LANGSUNG dari tabel ini pada
        setiap kali jawaban disimpan — bukan dari nilai yang disalin saat
        pelamarnya mulai. Memendekkan durasi karena itu memangkas sisa waktu
        setiap orang yang sedang mengerjakan, seketika, di tengah kalimat;
        memanjangkannya membuat penghitung waktu mereka melompat naik tanpa
        sebab yang terlihat. Keduanya terjadi tanpa satu pun tanda di layar
        pelamar.

        Ditolak, bukan diperingatkan: yang mengubahnya ada di layar lain dan
        tidak akan melihat akibatnya.

        Perubahan LAIN — nama, keterangan, aktif/tidak — tetap boleh, karena
        tidak satu pun menyentuh ujian yang sedang berjalan.
        """
        try:
            sebelum = await database.fetch_one(
                select(
                    hr_tests_table.c.id,
                    hr_tests_table.c.durationMinutes,
                )
                .where(hr_tests_table.c.id == test_id)
                .where(hr_tests_table.c.isDelete == False)  # noqa: E712
            )
            if sebelum is None:
                return app_error(
                    ErrorCode.NOT_FOUND, "Paket ujian tidak ditemukan.", 404
                )

            nilai = {}
            if "name" in data and data["name"] is not None:
                nama = str(data["name"]).strip()
                if not nama:
                    return app_error(
                        ErrorCode.VALIDATION,
                        "Nama paket ujian wajib diisi.",
                        400,
                    )
                nilai["name"] = nama
            if "description" in data:
                nilai["description"] = data["description"] or None
            if "isActive" in data and data["isActive"] is not None:
                nilai["isActive"] = bool(data["isActive"])

            if (
                "durationMinutes" in data
                and data["durationMinutes"] is not None
                and int(data["durationMinutes"])
                != int(sebelum["durationMinutes"] or 90)
            ):
                berjalan = await HrRecruitmentRepository._sedang_mengerjakan(
                    test_id
                )
                if berjalan:
                    return app_error(
                        ErrorCode.VALIDATION,
                        f"Durasi tidak dapat diubah: ada {berjalan} pelamar "
                        f"yang sedang mengerjakan paket ini. Sisa waktu "
                        f"mereka dihitung dari durasi ini, jadi mengubahnya "
                        f"sekarang akan memotong atau memanjangkan waktu "
                        f"mereka seketika. Tunggu sampai selesai.",
                        409,
                    )
                nilai["durationMinutes"] = int(data["durationMinutes"])

            if not nilai:
                return {"message": "No changes"}

            nilai["updatedAt"] = dt.now()
            nilai["updatedBy"] = user_id

            await database.execute(
                update(hr_tests_table)
                .where(hr_tests_table.c.id == test_id)
                .values(**nilai)
            )
            return {"id": test_id}
        except Exception as e:  # noqa: BLE001
            log_error(f"Error updating exam package: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def daftar_ujian():
        """
        Seluruh paket ujian beserta jumlah soalnya.

        Jumlah soal dihitung di sini, bukan di layar: menghitungnya di layar
        menuntut seluruh soal ikut dikirim, dan tujuh puluh lima pertanyaan
        esai jauh lebih besar daripada daftar yang hendak ditampilkan.
        """
        try:
            baris = await database.fetch_all(
                select(
                    hr_tests_table.c.id,
                    hr_tests_table.c.name,
                    hr_tests_table.c.description,
                    hr_tests_table.c.durationMinutes,
                    hr_tests_table.c.isActive,
                    func.count(hr_questions_table.c.id).label("jumlahSoal"),
                )
                .select_from(
                    hr_tests_table.outerjoin(
                        hr_questions_table,
                        (hr_questions_table.c.testID == hr_tests_table.c.id)
                        & (hr_questions_table.c.isDelete == False),  # noqa: E712
                    )
                )
                .where(hr_tests_table.c.isDelete == False)  # noqa: E712
                .group_by(
                    hr_tests_table.c.id,
                    hr_tests_table.c.name,
                    hr_tests_table.c.description,
                    hr_tests_table.c.durationMinutes,
                    hr_tests_table.c.isActive,
                )
                .order_by(hr_tests_table.c.name)
            )
            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "description": r["description"],
                    "durationMinutes": r["durationMinutes"],
                    "isActive": bool(r["isActive"]),
                    "jumlahSoal": int(r["jumlahSoal"] or 0),
                }
                for r in baris
            ]
        except Exception as e:
            log_error(f"Error listing hr tests: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    # ----------------------------------------------------------------- soal

    @staticmethod
    async def daftar_soal(test_id: int = None, keyword: str = None):
        """
        Soal, disaring paket ujian dan kata pencarian.

        Pencarian menyentuh pertanyaan DAN catatannya: sebagian soal hanya
        dapat ditemukan lewat standar yang disebut di catatannya — "SNI-03"
        tidak muncul di pertanyaannya sama sekali.
        """
        try:
            syarat = [hr_questions_table.c.isDelete == False]  # noqa: E712
            if test_id:
                syarat.append(hr_questions_table.c.testID == test_id)
            if keyword:
                pola = f"%{keyword}%"
                syarat.append(
                    hr_questions_table.c.question.ilike(pola)
                    | hr_questions_table.c.notes.ilike(pola)
                )

            baris = await database.fetch_all(
                select(
                    hr_questions_table.c.id,
                    hr_questions_table.c.testID,
                    hr_questions_table.c.sortOrder,
                    hr_questions_table.c.question,
                    hr_questions_table.c.notes,
                    hr_questions_table.c.attachment,
                    hr_questions_table.c.category,
                    hr_questions_table.c.maxScore,
                    hr_questions_table.c.allowsUpload,
                    hr_tests_table.c.name.label("testName"),
                )
                .select_from(
                    hr_questions_table.join(
                        hr_tests_table,
                        hr_questions_table.c.testID == hr_tests_table.c.id,
                    )
                )
                .where(*syarat)
                .order_by(
                    hr_questions_table.c.testID,
                    hr_questions_table.c.sortOrder,
                )
            )
            return [dict(r) for r in baris]
        except Exception as e:
            log_error(f"Error listing hr questions: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def buat_soal(data: dict):
        """
        Tambah satu soal ke paket ujian.

        Urutannya diisi otomatis di belakang yang sudah ada; yang membuat soal
        memikirkan isinya, bukan nomor ke berapa ia muncul.
        """
        try:
            terakhir = await database.fetch_val(
                select(func.max(hr_questions_table.c.sortOrder)).where(
                    hr_questions_table.c.testID == data["testID"]
                )
            )

            soal_id = await database.execute(
                insert(hr_questions_table).values(
                    testID=data["testID"],
                    sortOrder=int(terakhir or 0) + 1,
                    question=data["question"],
                    notes=data.get("notes") or None,
                    attachment=data.get("attachment") or None,
                    category=data.get("category") or "civil",
                    maxScore=int(data.get("maxScore") or 5),
                    allowsUpload=bool(data.get("allowsUpload")),
                    # `createdAt` diisi manual.
                    #
                    # Default kolom sisi-Python tidak pernah berlaku pada
                    # pustaka `databases`: kueri yang dieksekusi sudah
                    # terkompilasi, sehingga langkah itu dilewati dan nilainya
                    # sampai ke MySQL sebagai NULL.
                    createdAt=dt.now(),
                )
            )
            # Penggunanya diambil dari konteks permintaan: fungsi ini
            # tidak menerima `user_id` pada tanda tangannya, dan menambahkannya
            # berarti mengubah seluruh pemanggilnya.
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="hr_questions",
                entityID=int(soal_id),
                action="create",
            )
            return {"id": soal_id}
        except Exception as e:
            log_error(f"Error creating hr question: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def ubah_soal(question_id: int, data: dict):
        """Ubah satu soal; hanya kolom yang dikirim yang tersentuh."""
        try:
            boleh = (
                "question",
                "notes",
                "attachment",
                "category",
                "maxScore",
                "allowsUpload",
                "sortOrder",
            )
            nilai = {k: data[k] for k in boleh if k in data}
            if not nilai:
                # Penggunanya diambil dari konteks permintaan: fungsi ini
                # tidak menerima `user_id` pada tanda tangannya, dan menambahkannya
                # berarti mengubah seluruh pemanggilnya.
                from repository.audit_log_repository import AuditLogRepository

                await AuditLogRepository.record(
                    entity="hr_questions",
                    entityID=int(question_id),
                    action="update",
                )
                return {"id": question_id}

            await database.execute(
                update(hr_questions_table)
                .where(hr_questions_table.c.id == question_id)
                .values(**nilai)
            )
            return {"id": question_id}
        except Exception as e:
            log_error(f"Error updating hr question: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def hapus_soal(question_id: int):
        """
        Tandai soal terhapus; barisnya tetap ada.

        Jawaban lama menunjuk ke soal ini. Menghapus barisnya membuat lembar
        jawaban pelamar yang sudah dinilai kehilangan pertanyaannya — dan
        nilai tanpa pertanyaan tidak dapat ditinjau ulang oleh siapa pun.
        """
        try:
            await database.execute(
                update(hr_questions_table)
                .where(hr_questions_table.c.id == question_id)
                .values(isDelete=True)
            )
            # Penggunanya diambil dari konteks permintaan: fungsi ini
            # tidak menerima `user_id` pada tanda tangannya, dan menambahkannya
            # berarti mengubah seluruh pemanggilnya.
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="hr_questions",
                entityID=int(question_id),
                action="delete",
            )
            return {"id": question_id}
        except Exception as e:
            log_error(f"Error deleting hr question: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
