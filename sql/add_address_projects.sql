-- Alamat lokasi proyek.
--
-- Dipakai mengisi alamat pengiriman pada purchase order Franco: barang
-- dikirim ke lokasi proyeknya, dan mengetiknya ulang pada setiap PO berarti
-- menyalin dari catatan lain yang cepat atau lambat berbeda dari sumbernya.
--
-- `TEXT`, bukan `VARCHAR`: alamat proyek kerap beberapa baris — nama lokasi,
-- jalan, kota, patokan — dan batas panjang membuatnya terpotong justru pada
-- bagian yang menolong pengemudi menemukannya.
--
-- Boleh kosong: proyek yang sudah ada belum punya alamat, dan mewajibkannya
-- membuat seluruhnya tidak dapat disunting sampai satu per satu diisi.

ALTER TABLE projects
  ADD COLUMN `address` text DEFAULT NULL AFTER `name`;

-- Proyek yang perlu diisi alamatnya.
--
-- Sekali kerja; setelah terisi, PO Franco mengambilnya sendiri.
SELECT id, code, name
FROM projects
WHERE isDelete = 0
  AND isActive = 1
  AND (address IS NULL OR address = '')
ORDER BY code;
