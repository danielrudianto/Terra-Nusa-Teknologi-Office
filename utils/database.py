import os
import pymysql

pymysql.install_as_MySQLdb()

from sqlalchemy import create_engine, MetaData
from databases import Database

from utils.db_ukur import AKTIF as UKUR_AKTIF, DatabaseTerukur

# Load the database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Create a database connection
#
# `DatabaseTerukur` menghitung kueri per permintaan HTTP sehingga permintaan
# yang lambat dapat dibedakan antara SATU kueri lambat dan RATUSAN kueri cepat
# (N+1) — dua sebab yang terlihat sama persis dari waktu total saja. Lihat
# `utils/db_ukur.py`. Dapat dimatikan dengan `DB_UKUR=0`, dan saat mati yang
# dipakai `Database` biasa tanpa pembungkus apa pun.
database = (DatabaseTerukur if UKUR_AKTIF else Database)(DATABASE_URL)

# `echo` dibaca dari lingkungan, TIDAK lagi dipaksa `True`.
#
# Dengan `echo=True`, SQLAlchemy mencatat setiap pernyataan yang lewat engine
# ini pada tingkat INFO. Engine ini hanya dipakai untuk memantulkan skema
# (`autoload_with`) dan `create_all` saat mulai — jadi yang tercetak adalah
# rentetan DESCRIBE/SHOW setiap kali proses dinyalakan, memenuhi log dengan
# hal yang tidak dibaca siapa pun dan menenggelamkan baris `[lambat]` yang
# justru dicari.
#
# Dinyalakan kembali saat perlu dengan `SQL_ECHO=1`.
engine = create_engine(DATABASE_URL, echo=os.getenv("SQL_ECHO", "0") == "1")
metadata = MetaData()