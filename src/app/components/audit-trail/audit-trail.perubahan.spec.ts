/*
 * Perubahan bersarang pada riwayat.
 *
 * `customData` pada purchase order adalah objek berisi puluhan kunci. Dulu ia
 * dirangkai `JSON.stringify` menjadi satu baris sepanjang ribuan aksara —
 * untaian tanpa spasi yang tidak dapat dipatahkan peramban, sehingga seluruh
 * dialog melebar dan muncul penggulung mendatar.
 *
 * Yang diuji di sini bukan tampilannya, melainkan yang menentukannya: berapa
 * baris yang dihasilkan, dan apakah barisnya menunjuk kunci yang benar-benar
 * berubah.
 */
import { AuditTrailComponent } from './audit-trail.component';

function komponen(): AuditTrailComponent {
  // ApiService tidak dipanggil oleh `changeList`; pengujian ini murni
  // memeriksa pengolahan nilai, bukan pemuatannya.
  return new AuditTrailComponent({} as any);
}

function entri(changes: any): any {
  return {
    id: 1,
    entity: 'purchase_orders',
    entityID: 1,
    action: 'update',
    userID: 1,
    userName: 'Daniel',
    changes,
    note: null,
    createdAt: '2026-02-07T20:58:00Z',
  };
}

describe('AuditTrailComponent.changeList', () => {
  it('hanya menampilkan kunci yang berubah di dalam objek', () => {
    const lama = { workStart: '08:00', workEnd: '17:00', shiftHours: 8 };
    const baru = { workStart: '08:00', workEnd: '18:00', shiftHours: 8 };

    const hasil = komponen().changeList(
      entri({ customData: { from: lama, to: baru } }),
    );

    expect(hasil.length).toBe(1);
    expect(hasil[0].field).toBe('customData.workEnd');
    expect(hasil[0].from).toBe('17:00');
    expect(hasil[0].to).toBe('18:00');
  });

  it('menunjuk baris tepat pada daftar yang panjang', () => {
    const klausa = (x: string) => ['Klausa satu.', x, 'Klausa tiga.'];

    const hasil = komponen().changeList(
      entri({
        customData: {
          from: { additionalClauses: klausa('Klausa dua.') },
          to: { additionalClauses: klausa('Klausa dua yang diperbaiki.') },
        },
      }),
    );

    expect(hasil.length).toBe(1);
    expect(hasil[0].field).toBe('customData.additionalClauses[1]');
  });

  it('tidak menghasilkan baris bila isinya sama persis', () => {
    const isi = { workEnd: '17:00', nested: { a: 1 } };
    const hasil = komponen().changeList(
      entri({ customData: { from: isi, to: { ...isi, nested: { a: 1 } } } }),
    );
    expect(hasil.length).toBe(0);
  });

  it('memotong daftar yang terlalu panjang dan menyebutkan sisanya', () => {
    const dari: any = {};
    const ke: any = {};
    for (let i = 0; i < 30; i++) {
      dari[`k${i}`] = i;
      ke[`k${i}`] = i + 1;
    }

    const hasil = komponen().changeList(entri({ customData: { from: dari, to: ke } }));

    // Dua belas baris perubahan ditambah satu baris rangkuman.
    expect(hasil.length).toBe(13);
    expect(hasil[hasil.length - 1].sisa).toBe(18);
  });

  it('memotong nilai yang sangat panjang', () => {
    const panjang = 'a'.repeat(500);
    const hasil = komponen().changeList(
      entri({ note: { from: '', to: panjang } }),
    );

    expect(hasil.length).toBe(1);
    expect(hasil[0].to.length).toBeLessThan(200);
    expect(hasil[0].to.endsWith('…')).toBe(true);
  });

  /*
   * Perbandingan dilakukan atas nilai UTUH, pemotongan hanya untuk tampilan.
   *
   * Dulu keduanya dipotong lebih dulu, sehingga dua paragraf yang seratus
   * enam puluh aksara pertamanya sama dianggap tidak berubah. Pada catatan
   * dan klausul tambahan PO-D — keduanya paragraf bebas — membetulkan kalimat
   * TERAKHIR tidak menghasilkan satu baris pun, dan entri riwayatnya berbunyi
   * "Ubah, oleh Daniel, jam sekian" tanpa menyebut apa yang diubah.
   */
  it('menemukan perubahan pada bagian AKHIR nilai yang panjang', () => {
    const awalan = 'x'.repeat(300);
    const hasil = komponen().changeList(
      entri({
        customData: {
          from: { notes: `${awalan} kalimat lama.` },
          to: { notes: `${awalan} kalimat baru.` },
        },
      }),
    );

    expect(hasil.length).toBe(1);
    expect(hasil[0].field).toBe('customData.notes');
    // Tetap dipotong saat ditampilkan; yang berubah hanya kapan ia dipotong.
    expect(hasil[0].to.endsWith('…')).toBeTrue();
  });

  it('menemukan perubahan akhir pada nilai datar yang panjang', () => {
    const awalan = 'y'.repeat(300);
    const hasil = komponen().changeList(
      entri({ note: { from: `${awalan} satu`, to: `${awalan} dua` } }),
    );
    expect(hasil.length).toBe(1);
  });

  it('nilai sederhana tetap tampil apa adanya', () => {
    const hasil = komponen().changeList(
      entri({ isApproved: { from: false, to: true } }),
    );
    expect(hasil[0].field).toBe('isApproved');
    expect(hasil[0].from).toBe('Tidak');
    expect(hasil[0].to).toBe('Ya');
  });
});
