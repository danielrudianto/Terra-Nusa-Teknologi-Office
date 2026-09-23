-- ---------------------------------------------------------------------------
-- Baris LEMBUR untuk SPK D yang sudah terbit sebelum lembur menjadi baris.
--
-- Dulu lembur HANYA klausul: `customData.overtimeRate` dan `overtimeUnit`
-- tersimpan di tingkat dokumen, tanpa baris di `purchase_order_items`.
-- Akibatnya CoP — yang menyertifikasi per BARIS — tidak punya tempat mengisi
-- volume lembur, dan lembur hanya dapat ditagih di luar CoP.
--
-- Skrip ini membuat barisnya untuk SPK D yang tarif lemburnya sudah terisi
-- tetapi barisnya belum ada. Aman diulang: baris yang sudah ada tidak
-- digandakan (lihat NOT EXISTS).
--
-- `remarks_2 = 'LEMBUR'` adalah PENANDA MESIN yang dipakai layar SPK untuk
-- memisahkan baris ini dari komponen upah biasa; jangan diterjemahkan.
-- `remarks_3` label yang dibaca orang.
-- ---------------------------------------------------------------------------

-- 1) LIHAT DULU apa yang akan dibuat (tidak mengubah apa pun).
SELECT po.id,
       po.name                                                        AS spk,
       po.projectName                                                 AS proyek,
       JSON_UNQUOTE(JSON_EXTRACT(po.customData, '$.overtimeRate'))     AS tarif,
       JSON_UNQUOTE(JSON_EXTRACT(po.customData, '$.overtimeUnit'))     AS satuan,
       JSON_UNQUOTE(JSON_EXTRACT(po.customData, '$.overtimeVolume'))   AS volume
FROM purchase_orders po
WHERE po.isDelete = 0
  AND po.purchaseType = 'D'
  AND CAST(JSON_UNQUOTE(JSON_EXTRACT(po.customData, '$.overtimeRate')) AS DECIMAL(14,4)) > 0
  AND NOT EXISTS (
        SELECT 1 FROM purchase_order_items i
        WHERE i.purchaseOrderID = po.id AND i.remarks_2 = 'LEMBUR'
      );

-- 2) Buat barisnya.
--
-- `task` disalin dari baris upah pertama SPK itu: seluruh baris satu SPK D
-- memakai nama pekerjaan yang sama, dan yang membedakannya `remarks_3`.
-- `quantity` = volume lembur yang disepakati; 0 berarti tanpa plafon, sama
-- seperti yang dibuat layar sekarang.
INSERT INTO purchase_order_items
       (purchaseOrderID, task, quantity, price, unit,
        remarks_1, remarks_2, remarks_3)
SELECT po.id,
       COALESCE((SELECT i2.task
                   FROM purchase_order_items i2
                  WHERE i2.purchaseOrderID = po.id
                  ORDER BY i2.id
                  LIMIT 1), ''),
       COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(po.customData, '$.overtimeVolume')) AS DECIMAL(12,2)), 0),
       CAST(JSON_UNQUOTE(JSON_EXTRACT(po.customData, '$.overtimeRate')) AS DECIMAL(14,4)),
       COALESCE(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(po.customData, '$.overtimeUnit')), 'null'), 'jam'),
       s.name,
       'LEMBUR',
       'Lembur'
FROM purchase_orders po
JOIN suppliers s ON s.id = po.supplierID
WHERE po.isDelete = 0
  AND po.purchaseType = 'D'
  AND CAST(JSON_UNQUOTE(JSON_EXTRACT(po.customData, '$.overtimeRate')) AS DECIMAL(14,4)) > 0
  AND NOT EXISTS (
        SELECT 1 FROM purchase_order_items i
        WHERE i.purchaseOrderID = po.id AND i.remarks_2 = 'LEMBUR'
      );
