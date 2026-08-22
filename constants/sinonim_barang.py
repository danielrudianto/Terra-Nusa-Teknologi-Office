"""
Sinonim pencarian katalog barang.

Disusun dari 2.107 barang AKTIF pada katalog AKN, bukan dari daftar istilah
umum: yang dimasukkan hanya kata yang benar-benar dipakai — pada nama
barangnya maupun oleh orang yang mencarinya.

Tiga kelas persoalan yang ditangani, dan ketiganya nyata:

  1. DUA BAHASA. `wrench` dan `kunci` sama-sama muncul 175 kali pada katalog
     yang sama. Yang mengetik salah satunya hanya menemukan separuhnya, lalu
     menyimpulkan barangnya belum terdaftar.

  2. SALAH EJA YANG TERLANJUR TERSIMPAN. `stanless` tertulis 191 kali,
     `stainless` hanya 31 — yang mengeja dengan BENAR justru menemukan paling
     sedikit. Membetulkan 191 baris berarti mengubah nama barang yang sudah
     tercetak di ratusan purchase order, sehingga diperlakukan sebagai
     sinonim, bukan sebagai kekeliruan yang diperbaiki.

  3. SEBUTAN LAPANGAN. "kuku macan" tidak menyerupai "wire rope clip" sama
     sekali; tanpa sinonim, yang mencarinya tidak akan pernah menemukannya.

Ditempatkan di BACKEND karena pencariannya memang di sini — Meilisearch pada
jalur utama, `ILIKE` pada jalur cadangan. Menaruhnya di layar hanya menyaring
apa yang sudah terlanjur tersaring server.
"""

#: Setiap baris adalah SATU kelompok kata yang setara.
#:
#: Arahnya dua arah: mengetik bentuk mana pun menemukan seluruh anggotanya.
#: Ditulis sebagai kelompok, bukan pasangan `dari -> ke`, supaya tiap arah
#: tidak perlu disebut sendiri-sendiri.
SINONIM: list[list[str]] = [

  # ---------- salah eja yang terlanjur tersimpan ----------
  # Jumlahnya disebut supaya yang meninjau tahu ini bukan dugaan.
  ['stainless', 'stanless', 'stainles', 'stainlees'],  # 31 vs 191 pada katalog
  ['sekrup', 'skrup', 'screw'],
  ['stopkontak', 'stop kontak', 'stop-kontak'],
  ['saklar', 'sakelar', 'switch'],
  ['seling', 'sling'],
  ['konektor', 'connector'],

  # ---------- warna ----------
  ['black', 'hitam'],
  ['white', 'putih'],
  ['red', 'merah'],
  ['blue', 'biru'],
  ['green', 'hijau'],
  ['yellow', 'kuning'],
  ['orange', 'oranye', 'jingga'],
  ['grey', 'gray', 'abu', 'abu-abu'],
  ['brown', 'coklat', 'cokelat'],
  ['silver', 'perak'],
  ['gold', 'emas'],
  ['clear', 'bening', 'transparan'],

  # ---------- perkakas ----------
  # `wrench` 175 · `kunci` 175 — keduanya dipakai pada katalog yang sama.
  ['wrench', 'kunci'],
  ['combination wrench', 'kunci ring pas', 'kunci combination'],
  ['open end wrench', 'kunci pas', 'kunci pas terbuka'],
  ['ring wrench', 'kunci ring'],
  ['socket wrench', 'kunci sok', 'kunci soket'],
  ['adjustable wrench', 'kunci inggris'],
  ['allen key', 'hex key', 'kunci l', 'kunci hexagon'],
  ['plier', 'tang'],
  ['screwdriver', 'obeng'],
  ['hammer', 'palu'],
  ['saw', 'gergaji'],
  ['grinding', 'gerinda'],
  ['drill bit', 'mata bor'],
  ['measuring tape', 'meteran', 'meteran rol'],

  # ---------- pengikat ----------
  ['bolt', 'baut'],
  ['nut', 'mur'],
  ['washer', 'ring', 'ring plat'],
  ['spring washer', 'ring per', 'ring pegas'],
  ['anchor bolt', 'baut angkur', 'angkur'],
  # "kuku macan" — sebutan lapangan yang tidak menyerupai istilah resminya.
  ['wire rope clip', 'kuku macan', 'klem seling', 'klem sling'],
  ['turnbuckle', 'span sekrup', 'spanskrup'],
  ['shackle', 'segel', 'sekel'],

  # ---------- kelistrikan ----------
  # 968 barang; kelompok terbesar pada katalog ini.
  ['cable', 'kabel'],
  ['wire', 'kawat'],
  ['industrial plug', 'colokan industrial', 'steker industrial'],
  ['wall socket', 'socket', 'soket', 'stopkontak', 'stop kontak'],
  ['industrial socket', 'soket industrial', 'socket industrial'],
  ['fitting lampu', 'dudukan lampu', 'lamp holder'],
  ['lamp', 'lampu'],
  ['circuit breaker', 'mcb', 'pemutus arus'],
  ['contactor', 'kontaktor'],
  ['fuse', 'sikring', 'sekring'],
  ['cable lug', 'sekun', 'skun', 'sepatu kabel'],
  ['cable tie', 'tie rap', 'tirap', 'pengikat kabel'],
  ['insulation tape', 'isolasi', 'lakban listrik'],
  ['conduit', 'pipa kabel'],
  ['busbar', 'bus bar'],
  ['terminal block', 'terminal', 'blok terminal'],
  ['grounding', 'pentanahan', 'arde'],

  # ---------- material ----------
  ['rebar', 'besi beton', 'besi tulangan', 'tulangan'],
  ['deformed', 'ulir', 'sirip'],
  ['plain bar', 'besi polos', 'polos'],
  ['plate', 'plat', 'pelat'],
  ['angle bar', 'besi siku', 'siku'],
  ['hollow', 'besi hollow'],
  ['wire mesh', 'kawat anyam', 'wiremesh'],
  ['tarpaulin', 'terpal'],
  ['concrete', 'beton'],
  ['cement', 'semen'],

  # ---------- pengelasan ----------
  ['welding electrode', 'elektroda', 'kawat las'],
  ['welding mask', 'topeng las', 'kedok las'],
  ['regulator', 'regulator gas'],

  # ---------- pelindung diri ----------
  ['glove', 'sarung tangan'],
  ['helmet', 'helm', 'helm proyek'],
  ['safety shoes', 'sepatu safety', 'sepatu proyek'],
  ['goggle', 'kacamata', 'kacamata safety'],
  ['mask', 'masker'],
  ['vest', 'rompi'],
  ['body harness', 'sabuk pengaman', 'full body harness'],
  ['ear plug', 'penyumbat telinga', 'sumbat telinga'],

  # ---------- cairan & pelumas ----------
  ['oil', 'oli'],
  ['grease', 'gemuk'],
  ['hydraulic oil', 'oli hidrolik'],
  ['coolant', 'air radiator'],
  ['diesel', 'solar', 'bahan bakar diesel'],

  # ---------- lain ----------
  ['hose', 'selang'],
  ['clamp', 'klem'],
  ['rope', 'tali', 'tambang'],
  ['chain', 'rantai'],
  ['filter', 'saringan'],
  ['bearing', 'laher', 'klaher'],
  ['seal', 'sil', 'perapat'],
  ['belt', 'sabuk', 'van belt', 'vanbelt'],
  ['battery', 'baterai', 'aki'],

  # ---------- tambahan dari katalog terkini ----------
  # Hanya istilah yang benar-benar muncul di katalog sekarang.
  ['sandpaper', 'amplas'],
  ['nail', 'paku'],
  ['padlock', 'gembok'],
  ['kran', 'keran'],
  ['pipe', 'pipa'],
  ['nozzle', 'nosel'],
  ['glue', 'lem', 'adhesive'],
  ['paper', 'kertas'],
  ['marker', 'spidol'],
  ['stapler', 'staples', 'hekter', 'jekter'],
  ['compressor', 'kompresor'],
  ['flashlight', 'senter', 'lampu senter'],

  # ---------- merchandise & souvenir ----------
  ['t-shirt', 'kaos', 'kaus', 'tshirt', 'baju kaos'],
  ['polo shirt', 'kaos polo', 'polo'],
  ['jacket', 'jaket'],
  ['topi', 'hat'],
  ['mug', 'gelas', 'cangkir'],
  ['sticker', 'stiker'],
  ['keychain', 'gantungan kunci'],
  ['boots', 'sepatu boot', 'sepatu boots'],
]


def _bangun_peta() -> dict[str, list[str]]:
    """
    Peta pencarian: setiap bentuk menunjuk ke seluruh anggota kelompoknya.

    Disusun SEKALI saat modulnya dimuat. Menyusunnya pada tiap pencarian
    berarti menelusuri ratusan baris setiap kali orang mengetik satu huruf.
    """
    peta: dict[str, list[str]] = {}
    for kelompok in SINONIM:
        bawah = [k.lower() for k in kelompok]
        for kata in bawah:
            # Satu kata dapat berada di DUA kelompok — `socket` ada pada
            # kelistrikan dan pada perkakas. Keduanya digabung, bukan yang
            # terakhir menang: yang mengetik `socket` boleh bermaksud keduanya.
            gabung = peta.get(kata, [])
            peta[kata] = list(dict.fromkeys(gabung + bawah))
    return peta


_PETA = _bangun_peta()


def perluas_kata_kunci(kunci: str) -> list[str]:
    """
    Seluruh bentuk yang setara dengan kata kunci yang diketik.

    Kata kunci ASLI selalu ikut dikembalikan, bahkan bila tidak dikenal:
    pencarian yang kehilangan kata aslinya gagal menemukan barang yang namanya
    memang persis seperti yang diketik.

    Frasa utuh diperiksa LEBIH DULU. "kuku macan" hanya bermakna sebagai
    frasa; memecahnya per kata menghasilkan "kuku" dan "macan" yang tidak
    berhubungan dengan apa pun di katalog.
    """
    asli = str(kunci or "").strip().lower()
    if not asli:
        return []

    hasil: list[str] = [asli]

    for x in _PETA.get(asli, []):
        if x not in hasil:
            hasil.append(x)

    for kata in asli.split():
        if kata not in hasil:
            hasil.append(kata)
        for x in _PETA.get(kata, []):
            if x not in hasil:
                hasil.append(x)

    return hasil


def punya_sinonim(kunci: str) -> bool:
    """
    Apakah kata kunci ini punya bentuk lain.

    Dipakai memutuskan apakah pencarian perlu diperluas sama sekali —
    sebagian besar kata kunci tidak punya sinonim, dan menjalankan pencarian
    berlapis untuk semuanya membuat yang biasa ikut melambat.
    """
    return len(perluas_kata_kunci(kunci)) > 1
