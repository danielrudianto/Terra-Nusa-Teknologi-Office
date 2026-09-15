# Draf tender jadi BERARTI — BACKEND

**Tidak ada perubahan skema.** Tapi **ada perubahan izin**: menyebarkan tender
naik dari level 1 ke level 3.

> `tender_repository.py` di sini sudah termasuk perubahan nomor dokumen dari
> zip sebelumnya. Kalau yang itu sudah dipasang, timpa saja.

---

## Apa yang sebenarnya salah

`STATUS_DAPAT_DISUNTING = ("draft", "berjalan")` — dan **set yang sama persis**
dipakai untuk dua pertanyaan berbeda: boleh menyunting tendernya, dan boleh
mencatat penawaran.

Artinya `draft` dan `berjalan` diperlakukan **identik** untuk penawaran.
Tombol "sebarkan" praktis cuma mengganti label; tidak ada satu pun aturan yang
berubah karenanya. **Statusnya ada, tetapi tidak membedakan apa pun.**

Anda benar menyebutnya aneh — tapi sebabnya bukan kelonggaran, melainkan dua
pertanyaan yang kebetulan sama jawabannya lalu disatukan jadi satu konstanta.

## Yang berubah

**1. `STATUS_MENERIMA_PENAWARAN = ("berjalan",)`** — konstanta TERSENDIRI.
Draf menolak penawaran dengan 409 dan kalimat yang menyebut sebabnya, bukan
sekadar "tidak boleh".

Dipisahkan dari `STATUS_DAPAT_DISUNTING` supaya perubahan pada yang satu tidak
lagi diam-diam mengubah yang lain — itu akar masalahnya.

**2. Menyebarkan perlu `tender:approve` (level 3)**, bukan `update` (level 1).
Sejak penawaran ditolak selama draf, tombol inilah yang membuka pintunya — ia
bukan lagi penanda, melainkan keputusan bahwa daftar permintaannya sudah
selesai dan boleh dikirim ke pemasok. Dibiarkan di `update`, siapa pun yang
boleh menyunting juga dapat menyatakan tendernya siap, dan pemisahan yang baru
saja dibuat tidak menahan apa pun.

**3. Daftar menerima BEBERAPA status**, dipisah koma (`draft,berjalan`).
Tautan lama `?status=berjalan` tetap berarti sama — `.in_()` dengan satu
anggota sama saja dengan `==`.

**4. Lencana tender**: hitungan draf yang menunggu disetujui, dijaga
`tender:approve` — penjaga yang sama dengan tombolnya.

> Pembuatnya **tidak** dikecualikan di sini, berbeda dari modul lain. Menyetujui
> tender bukan memeriksa pekerjaan orang lain; ia keputusan bahwa daftar
> permintaannya sudah selesai, dan yang paling tahu itu justru yang
> menyusunnya. Aturan pembuat ≠ penyetuju ada untuk menghadirkan mata kedua
> atas UANG — di sini belum ada angka sama sekali.

---

## Uji

**Backend lengkap lolos.** `test/tender_test.py` +4 uji, dibuktikan menggigit:

```
draft boleh menerima penawaran lagi → "test_penawaran_ditolak_selama_draf" GAGAL
sebarkan diturunkan ke update       → 2 uji izin GAGAL
saringan status kembali satu nilai  → "menerima beberapa status" GAGAL
```

`test/lencana_test.py` ikut diperbarui: daftar kuncinya ditulis LENGKAP dan
sengaja harus ikut berubah tiap ada modul baru. Modul yang ditambahkan tanpa
memperbarui uji ini akan lolos diam-diam — dan kalau modul itu melempar, layar
menerima jawaban yang kekurangan satu kolom tanpa ada yang menandainya.

> Satu uji saya sempat merah padahal kodenya benar: regexnya saya batasi
> `{0,700}` sementara docstring rutenya lebih panjang dari itu, jadi
> lookahead-nya tidak pernah sampai ke dekorator berikutnya. Batasnya dibuang.
