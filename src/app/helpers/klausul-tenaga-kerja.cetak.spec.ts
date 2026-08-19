/**
 * Penjaga jalur CETAK dokumen tenaga kerja (PO-D).
 *
 * Bukan pengganti `klausul-tenaga-kerja.spec.ts`, yang menguji perakitan
 * konteksnya. Yang dijaga di sini satu hal saja, dan hal itu pernah runtuh:
 * setiap poin perjanjian yang sampai ke pdfmake HARUS berupa TEKS.
 *
 * `customData.wageSchedules` menyimpan DATA jadwal — larik objek
 * `{task, wages[]}` — sedangkan `buildManpowerClauses` menyisipkan isi
 * `ctx.wageSchedules` langsung sebagai poin. Bila konteksnya diteruskan
 * mentah, objek itu sampai ke `stripHtmlTags()`, yang memanggil `.replace()`
 * atas nilainya, dan SELURUH pencetakan berhenti dengan
 * "replace is not a function".
 *
 * Itu persis yang terjadi pada halaman invoice: ia meneruskan `customData`
 * apa adanya, sedangkan daftar purchase order merakitnya lebih dulu. Dokumen
 * yang sama gagal dicetak dari satu halaman dan berhasil dari halaman lain.
 */

import { buildManpowerClauses } from '../constants/clause-templates';
import { clauseToPdf } from './purchase-order-shared.helper';
import { konteksKlausulTenagaKerja } from './klausul-tenaga-kerja.helper';

/** Bentuk `customData` sebagaimana BENAR-BENAR tersimpan oleh PO-D. */
const CUSTOM_TERSIMPAN = {
  overtimeRate: 25000,
  shiftHours: 8,
  wageSchedules: [
    {
      task: 'Pembesian',
      wages: [
        {
          label: 'Upah harian',
          scheduleType: 'weekly',
          payDay: 'Sabtu',
          cutoffDay: 'Rabu',
        },
      ],
    },
  ],
};

/** Kumpulkan seluruh poin dari seluruh pasal menjadi satu larik datar. */
function semuaPoin(seksi: any[]): any[] {
  return seksi.flatMap((s: any) => (s?.items ?? []).flat());
}

describe('cetak klausul tenaga kerja', () => {
  it('konteks mentah menghasilkan poin yang BUKAN teks', () => {
    // Menegaskan bahaya yang dijaga itu nyata — bukan sekadar kemungkinan.
    // Bila suatu saat `buildManpowerClauses` berhenti menyisipkan
    // `wageSchedules` apa adanya, harapan ini gagal dan penjaga di bawah
    // boleh ditinjau ulang.
    const poin = semuaPoin(buildManpowerClauses(CUSTOM_TERSIMPAN as any));
    expect(poin.some((p) => typeof p !== 'string')).toBeTrue();
  });

  it('konteks mentah membuat perakitan pdf melempar galat', () => {
    const poin = semuaPoin(buildManpowerClauses(CUSTOM_TERSIMPAN as any));
    const objek = poin.find((p) => typeof p !== 'string');
    expect(() => clauseToPdf(objek as any)).toThrow();
  });

  it('konteks yang dirakit menghasilkan poin teks seluruhnya', () => {
    const ctx = konteksKlausulTenagaKerja(CUSTOM_TERSIMPAN, {});
    const poin = semuaPoin(buildManpowerClauses(ctx as any));

    expect(poin.length).toBeGreaterThan(0);
    poin.forEach((p) => expect(typeof p).toBe('string'));
  });

  it('konteks yang dirakit dapat dirakit menjadi pdf tanpa galat', () => {
    const ctx = konteksKlausulTenagaKerja(CUSTOM_TERSIMPAN, {});
    const poin = semuaPoin(buildManpowerClauses(ctx as any));

    poin.forEach((p) => expect(() => clauseToPdf(p as string)).not.toThrow());
  });

  it('jadwal upah tetap terbaca sebagai kalimat pada hasilnya', () => {
    const ctx = konteksKlausulTenagaKerja(CUSTOM_TERSIMPAN, {});
    const poin = semuaPoin(buildManpowerClauses(ctx as any)) as string[];

    // Kalimatnya ikut tercetak — bukan sekadar tidak melempar galat, tetapi
    // memang menggantikan "Upah dibayarkan sesuai kesepakatan".
    expect(poin.some((p) => p.includes('Sabtu'))).toBeTrue();
    expect(
      poin.some((p) => p === 'Upah dibayarkan sesuai kesepakatan.'),
    ).toBeFalse();
  });
});
