from pydantic import BaseModel


class UserSignatureSave(BaseModel):
    """Muatan penyimpanan tanda tangan: satu data-URI PNG.

    Isinya diperiksa di controller (bita ajaib PNG, ukuran, batas piksel) —
    bukan di sini. Pemeriksaan bentuk teks saja tidak membuktikan apa pun
    tentang berkasnya.
    """

    image: str
