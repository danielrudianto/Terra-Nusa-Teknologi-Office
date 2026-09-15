-- Mobilisasi dan demobilisasi menjadi BARIS SUNGGUHAN.
--
-- ----------------------------------------------------------------------
-- Duduk perkaranya
-- ----------------------------------------------------------------------
--
-- Selama ini mobilisasi dan demobilisasi bukan baris. Keduanya dua kolom
-- uang yang menempel pada baris alatnya: `remarks_4` dan `remarks_5`.
-- Baris "Mobilisasi Crane 25T sesuai pada nomor 1" yang tercetak pada SPK
-- tidak pernah ada di basis data — ia DIKARANG saat mencetak, oleh
-- `perluasItemMobilisasi()` di frontend.
--
-- Akibatnya certificate of payment tidak dapat menyentuhnya sama sekali.
-- CoP menyertifikasi per `purchase_order_items.id`: satu kotak volume per
-- baris, diadu dengan pagunya. Mobilisasi tidak punya `id`, sehingga tidak
-- ada tempat untuk menaruh volumenya.
--
-- Yang membuatnya lebih dari sekadar layar yang kurang lengkap:
-- `purchase_orders.dpp` SUDAH memuat mobilisasi (lihat `lineTotal()` pada
-- formulir PO-B). Jadi SPK sewa Rp 100 juta yang Rp 30 juta di antaranya
-- mobilisasi hanya dapat disertifikasi sampai Rp 70 juta — SELAMANYA, bukan
-- karena pagunya habis melainkan karena barisnya tidak pernah ada. Sisanya
-- tercetak pada dokumen yang ditandatangani kedua pihak, dan vendor akan
-- menagihkannya.
--
-- ----------------------------------------------------------------------
-- RANJAU: `remarks_4` BERBEDA ARTI menurut jenis PO
-- ----------------------------------------------------------------------
--
-- Pada PO-B  : `remarks_4` = nilai mobilisasi, `remarks_5` = demobilisasi.
-- Pada PO-A  : `remarks_4` = NAMA SUPIR atau nomor rujukan (teks),
--              `remarks_5` = nama penanggung jawab.
--
-- Migrasi yang tidak menyaring jenis PO akan mengubah nama supir menjadi
-- baris pekerjaan bernilai nol dan MENGHAPUS namanya dari dokumen
-- angkutan. Karena itu setiap pernyataan di bawah menyaring
-- `po.purchaseType = 'B'`, dan tambahan lagi menuntut isinya berupa angka.
--
-- ----------------------------------------------------------------------
-- 1. Dua kolom baru
-- ----------------------------------------------------------------------
--
-- Kolom SUNGGUHAN, bukan menumpang `remarks_` yang ketujuh. Seluruh enam
-- kolom keterangan sudah terpakai pada PO-B (tanggal, lokasi, mobilisasi,
-- jumlah unit) — dan justru menumpangkan arti pada kolom serbaguna itulah
-- yang melahirkan persoalan ini. Mengulanginya sekali lagi berarti membuat
-- bug berikutnya sambil membetulkan yang sekarang.

ALTER TABLE purchase_order_items
    ADD COLUMN itemKind VARCHAR(20) NULL AFTER unit,
    ADD COLUMN parentItemID INT NULL AFTER itemKind;

-- `ON DELETE CASCADE`: baris mobilisasi tidak punya arti sendiri. Alat yang
-- dihapus dari SPK harus membawa serta biaya mobilisasinya — kalau tidak,
-- yang tertinggal adalah baris bernama "Mobilisasi" yang tidak menunjuk
-- apa pun dan tetap ikut menjumlah nilai dokumen.
ALTER TABLE purchase_order_items
    ADD CONSTRAINT fk_poi_parent
        FOREIGN KEY (parentItemID) REFERENCES purchase_order_items (id)
        ON DELETE CASCADE;

CREATE INDEX idx_poi_parent ON purchase_order_items (parentItemID);

-- ----------------------------------------------------------------------
-- 2. Pindahkan yang sudah ada
-- ----------------------------------------------------------------------
--
-- IDEMPOTEN: dijalankan dua kali tidak menggandakan apa pun. Penjaganya
-- `parentItemID IS NULL` pada induk yang dicari, digabung dengan daftar
-- induk yang sudah punya anak — dijalankan ulang, daftar itu sudah memuat
-- semuanya dan tidak ada yang tersisa untuk dipindahkan.
--
-- Nilai NOL tidak dipindahkan. SPK tanpa mobilisasi menyimpan "0" di
-- `remarks_4`, dan `perluasItemMobilisasi` memang melewatinya
-- (`if (nilai <= 0) return`). Memindahkannya akan menambahkan baris
-- "Mobilisasi Rp 0" pada dokumen yang selama ini tidak memuatnya.

CREATE TEMPORARY TABLE _mob_induk AS
SELECT i.id            AS parentID,
       i.purchaseOrderID,
       CAST(i.remarks_4 AS DECIMAL(14, 4)) AS mob,
       CAST(i.remarks_5 AS DECIMAL(14, 4)) AS demob
FROM purchase_order_items i
JOIN purchase_orders po ON po.id = i.purchaseOrderID
WHERE po.purchaseType = 'B'
  -- Induk saja; baris anak hasil migrasi sebelumnya dilewati.
  AND i.parentItemID IS NULL
  AND i.itemKind IS NULL
  -- Isinya harus ANGKA. Penjaga kedua setelah `purchaseType`: bila suatu
  -- saat ada jenis PO lain yang bernilai 'B' pada kolom itu, teks tetap
  -- tidak akan ikut terbawa.
  AND (
        (i.remarks_4 REGEXP '^[0-9]+(\\.[0-9]+)?$' AND CAST(i.remarks_4 AS DECIMAL(14,4)) > 0)
     OR (i.remarks_5 REGEXP '^[0-9]+(\\.[0-9]+)?$' AND CAST(i.remarks_5 AS DECIMAL(14,4)) > 0)
      )
  AND i.id NOT IN (
        SELECT COALESCE(parentItemID, 0) FROM (
            SELECT parentItemID FROM purchase_order_items WHERE parentItemID IS NOT NULL
        ) sudah
      );

-- Mobilisasi lebih dulu, demobilisasi sesudahnya: urutan `id` yang dihasilkan
-- itulah yang menentukan urutan cetaknya di bawah baris alatnya.
--
-- `task` diisi SEPERTI ADANYA — "Mobilisasi", bukan "Mobilisasi Crane 25T
-- sesuai pada nomor 4". Nama lengkapnya disusun saat menampilkan, dari
-- `parentItemID`. Menyimpannya berarti nama alat yang kelak diperbaiki di
-- master meninggalkan salinan basi pada dokumen — persoalan yang sama sudah
-- tercatat di `purchase_order_item_repository` untuk `task` lawan
-- `master_item`.
INSERT INTO purchase_order_items
    (purchaseOrderID, task, quantity, price, unit, itemKind, parentItemID)
SELECT purchaseOrderID, 'Mobilisasi', 1, mob, 'LS', 'mobilisasi', parentID
FROM _mob_induk
WHERE mob IS NOT NULL AND mob > 0;

INSERT INTO purchase_order_items
    (purchaseOrderID, task, quantity, price, unit, itemKind, parentItemID)
SELECT purchaseOrderID, 'Demobilisasi', 1, demob, 'LS', 'demobilisasi', parentID
FROM _mob_induk
WHERE demob IS NOT NULL AND demob > 0;

-- ----------------------------------------------------------------------
-- 3. Kosongkan kolom lamanya
-- ----------------------------------------------------------------------
--
-- WAJIB, bukan kerapian. Peramban yang masih memegang bundel frontend lama
-- akan tetap memanggil `perluasItemMobilisasi` atas baris yang kini SUDAH
-- punya baris anaknya sendiri — dan mencetak mobilisasinya dua kali.
-- Dengan `remarks_4` kosong, jalur lama itu tidak menemukan apa pun dan
-- diam dengan sendirinya.

UPDATE purchase_order_items i
JOIN _mob_induk m ON m.parentID = i.id
SET i.remarks_4 = NULL,
    i.remarks_5 = NULL;

DROP TEMPORARY TABLE _mob_induk;

-- ----------------------------------------------------------------------
-- Pemeriksaan sesudah dijalankan
-- ----------------------------------------------------------------------
--
-- Nilai dokumen TIDAK boleh berubah. `purchase_orders.dpp` sejak dulu sudah
-- memuat mobilisasi; yang berubah hanya di mana angkanya disimpan. Kueri ini
-- seharusnya tidak mengembalikan satu baris pun:
--
--   SELECT po.id, po.name, po.dpp,
--          ROUND(SUM(COALESCE(i.amount, i.quantity * i.price)), 2) AS jumlahBaris
--   FROM purchase_orders po
--   JOIN purchase_order_items i ON i.purchaseOrderID = po.id
--   WHERE po.purchaseType = 'B' AND po.isDelete = 0
--   GROUP BY po.id, po.name, po.dpp
--   HAVING ABS(po.dpp - jumlahBaris) > 5;
--
-- Dan PO-A tidak boleh tersentuh — kueri ini harus tetap mengembalikan
-- nama-nama supir sebagaimana sebelumnya:
--
--   SELECT i.id, i.remarks_4, i.remarks_5
--   FROM purchase_order_items i
--   JOIN purchase_orders po ON po.id = i.purchaseOrderID
--   WHERE po.purchaseType = 'A' AND i.remarks_4 IS NOT NULL
--   LIMIT 20;
