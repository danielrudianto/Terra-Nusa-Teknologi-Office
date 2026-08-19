/**
 * Penelusuran halaman pada pemilih purchase order.
 *
 * Yang diuji perhitungan barisnya saja — bukan komponennya secara utuh.
 * Komponen itu menuntut `MatDialogRef` dan `ApiService`, dan menyiapkan
 * keduanya di sini justru menguji kerangka pengujiannya, bukan aritmetika
 * yang pernah keliru.
 *
 * Angkanya penting karena ditulis apa adanya kepada yang memakai: "51–60 dari
 * 54" membuat seluruh daftar tidak dipercaya, walau tombolnya berfungsi.
 */

import { PurchaseOrderPickerComponent } from './purchase-order-picker.component';

/** Bentuk seperlunya: hanya bidang yang dibaca kedua getter itu. */
function pemilih(page: number, jumlah: number): any {
  const c = Object.create(PurchaseOrderPickerComponent.prototype);
  c.ukuranHalaman = 10;
  c.page = page;
  c.jumlah = jumlah;
  return c;
}

describe('pemilih purchase order — penelusuran halaman', () => {
  it('halaman pertama dimulai dari baris satu', () => {
    const c = pemilih(0, 54);
    expect(c.awalBaris).toBe(1);
    expect(c.akhirBaris).toBe(10);
  });

  it('halaman berikutnya bergeser sepuluh baris', () => {
    const c = pemilih(2, 54);
    expect(c.awalBaris).toBe(21);
    expect(c.akhirBaris).toBe(30);
  });

  it('halaman terakhir berhenti pada jumlah sebenarnya', () => {
    // 54 dokumen, halaman keenam: 51–54, BUKAN 51–60.
    const c = pemilih(5, 54);
    expect(c.awalBaris).toBe(51);
    expect(c.akhirBaris).toBe(54);
  });

  it('daftar kosong tidak menampilkan baris ke-satu', () => {
    const c = pemilih(0, 0);
    expect(c.awalBaris).toBe(0);
    expect(c.akhirBaris).toBe(0);
  });

  it('jumlah yang pas sepuluh berakhir tepat di sepuluh', () => {
    const c = pemilih(0, 10);
    expect(c.akhirBaris).toBe(10);
  });
});
