/**
 * Pembacaan nama pemasok dari satu baris jawaban purchase order.
 *
 * Ada karena penamaannya pernah berbeda antara kueri daftar dan kueri satu
 * dokumen — `supplierName` di satu sisi, `supplier_name` di sisi lain — dan
 * perbedaan itu TIDAK menimbulkan galat apa pun. Bidang yang salah nama hanya
 * bernilai `undefined`, sehingga seluruh kolom pemasok berubah menjadi "—"
 * berikut lencana "?", seolah datanya yang hilang.
 *
 * Backend kini seragam camelCase dan dijaga pengujian di sana. Bentuk
 * bergaris bawah tetap dibaca sebagai jaring pengaman: backend dan frontend
 * disebar terpisah, dan di antara kedua penyebaran itu jawaban lama masih
 * beredar.
 */

import { namaPemasokBaris } from './purchase-order-shared.helper';

describe('namaPemasokBaris', () => {
  it('membaca bentuk camelCase — bentuk yang dikirim backend sekarang', () => {
    expect(
      namaPemasokBaris({ supplierName: 'Adhimix', supplierPrefix: 'PT' }),
    ).toBe('PT Adhimix');
  });

  it('masih membaca bentuk bergaris bawah', () => {
    // Jawaban lama yang masih beredar di antara dua penyebaran.
    expect(
      namaPemasokBaris({ supplier_name: 'Adhimix', supplier_prefix: 'PT' }),
    ).toBe('PT Adhimix');
  });

  it('camelCase didahulukan bila keduanya ada', () => {
    expect(
      namaPemasokBaris({ supplierName: 'Baru', supplier_name: 'Lama' }),
    ).toBe('Baru');
  });

  it('awalan non-entitas tidak ikut dicetak', () => {
    // "Pribadi" penanda jenis pemasok di sistem, bukan bagian dari namanya.
    expect(
      namaPemasokBaris({ supplierName: 'Dedi', supplierPrefix: 'Pribadi' }),
    ).toBe('Dedi');
  });

  it('baris tanpa pemasok menghasilkan penanda kosong', () => {
    expect(namaPemasokBaris({})).toBe('-');
    expect(namaPemasokBaris(null)).toBe('-');
  });
});
