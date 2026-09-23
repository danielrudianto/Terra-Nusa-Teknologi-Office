"""
Bentuk muatan untuk mengubah draf pembelian.

Rutenya dahulu menerima `dict` mentah, sehingga apa pun yang dikirim
masuk apa adanya ke kolom — teks ke kolom uang, tanggal ngawur ke kolom
tanggal. Yang gagal di MySQL menjadi galat 500 tanpa menyebut bidang mana,
dan yang berhasil diam-diam merusak angkanya.

Seluruh bidang OPSIONAL, dan `exclude_unset` yang membedakan "tidak
dikirim" dari "dikosongkan": periode memang boleh dihapus kembali.
"""
from datetime import date as tanggal
from typing import Annotated

from pydantic import BaseModel, Field, model_validator


class UbahDrafPembelian(BaseModel):
    dpp: Annotated[float, Field(ge=0)] | None = None
    ppn: Annotated[float, Field(ge=0, le=100)] | None = None
    pbbkb: Annotated[float, Field(ge=0)] | None = None
    description: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    date: tanggal | None = None
    periodStart: tanggal | None = None
    periodEnd: tanggal | None = None

    @model_validator(mode="after")
    def periode_masuk_akal(self):
        """
        Periode yang terbalik membuat penyaringan diam-diam tidak menemukan
        apa pun — drafnya ada, tetapi tidak pernah muncul pada rentang mana
        pun. Lebih baik ditolak di pintu.
        """
        if self.periodStart and self.periodEnd and self.periodEnd < self.periodStart:
            raise ValueError(
                "Periode selesai tidak boleh mendahului periode mulai."
            )
        return self

    @model_validator(mode="after")
    def tanggal_dokumen_tidak_boleh_kosong(self):
        """
        Kolom `date` NOT NULL. Mengirimnya sebagai null menjatuhkan
        penyimpanan dengan galat 500 yang tidak menyebut bidangnya —
        lebih baik ditolak di pintu dengan sebutan yang jelas.
        """
        if "date" in self.model_fields_set and self.date is None:
            raise ValueError("Tanggal dokumen tidak boleh dikosongkan.")
        return self

    @model_validator(mode="after")
    def bukan_muatan_kosong(self):
        if not self.model_fields_set:
            raise ValueError("Tidak ada bidang yang dikirim.")
        return self
