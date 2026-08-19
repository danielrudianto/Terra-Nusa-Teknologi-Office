import { Alignment, Margins, PageSize } from 'pdfmake/interfaces';
import {
  APPROVAL_BOX,
  FOOTER_RULE,
  LETTERHEAD,
  OFFICE_FOOTER,
} from '../constants/letterhead.constant';
// Alamat & email kantor tinggal di clause-templates, bukan di letterhead.
import { OFFICE_CONTACT } from '../constants/clause-templates';

/**
 * Bagian dokumen PO yang dipakai bersama semua jenis PO (G, C, dst):
 * kop surat, footer, lampiran tata cara penagihan, dan util format.
 *
 * Dipisahkan agar perubahan tata letak cukup dilakukan sekali, tidak
 * diulang di tiap helper jenis PO.
 */

/** Cara dokumen dibuka: tab baru (default), dialog print, atau unduh. */
/**
 * Cara dokumen dikeluarkan.
 *
 * `dataurl` mengembalikan Promise berisi data URL alih-alih membuka apa pun
 * — dipakai untuk menampilkan dokumen di dalam dialog.
 *
 * Definisi ini TERPISAH dari yang di `invoice.helper.ts`, dan seluruh helper
 * purchase order memakai yang di sini. Menambah nilai baru harus dilakukan
 * di kedua tempat, atau salah satunya menolak nilai itu saat kompilasi.
 */
/**
 * Cara dokumen dikeluarkan.
 *
 * `docdef` mengembalikan definisi dokumennya TANPA membuat PDF. Dipakai saat
 * beberapa dokumen harus terbit sebagai satu berkas — mencetak adendum wajib
 * menyertakan induk dan adendum sebelumnya, dan vendor harus menerima satu
 * berkas, bukan tiga yang harus disatukan sendiri.
 */
export type PdfOutput =
  | 'open'
  | 'print'
  | 'download'
  | 'dataurl'
  | 'docdef';

const MONTHS = [
  'Januari',
  'Februari',
  'Maret',
  'April',
  'Mei',
  'Juni',
  'Juli',
  'Agustus',
  'September',
  'Oktober',
  'November',
  'Desember',
];

/**
 * Kalimat pengantar sebelum tabel, mengikuti bentuk pekerjaannya.
 *
 * Sebelumnya seluruh dokumen berbunyi "untuk melakukan pekerjaan", termasuk
 * yang isinya menyewa alat atau menutup pertanggungan — dan itu terbaca
 * janggal karena yang dipesan bukan pekerjaan dalam arti itu.
 */
export function workIntroSentence(
  poType?: string,
  isAdendum?: boolean,
): string {
  /*
   * Dokumen ADENDUM memakai kalimat pembukanya sendiri.
   *
   * Bentuknya diverifikasi terhadap delapan dokumen yang sudah terbit;
   * ketiganya berbunyi sedikit berbeda dan satu di antaranya salah ketik,
   * sehingga diseragamkan menjadi satu.
   *
   * Kalimat biasa TIDAK dipakai di sini: "untuk melakukan pekerjaan" pada
   * lembar adendum terbaca seolah pekerjaannya baru dimulai, padahal yang
   * dimaksud perubahan atas perjanjian yang sudah berjalan.
   */
  if (isAdendum) {
    return (
      'Berdasarkan kondisi lapangan, bersama ini kami bermaksud untuk ' +
      'melakukan addendum terhadap dokumen bernomor sama, dengan ketentuan ' +
      'sebagai berikut:'
    );
  }

  const t = String(poType || '').toUpperCase();

  if (t === 'B') {
    return (
      'Berdasarkan permintaan kami, bersama ini kami bermaksud untuk ' +
      'melakukan penyewaan barang dengan ketentuan sebagai berikut:'
    );
  }
  if (t === '6.4.2') {
    return 'Untuk melakukan penutupan pertanggungan dengan ketentuan-ketentuan sebagai berikut:';
  }
  if (t === '6.5.2') {
    return 'Untuk menyelenggarakan pelatihan dengan ketentuan-ketentuan sebagai berikut:';
  }
  if (t === '5.1.12') {
    return 'Untuk melakukan pengadaan perangkat lunak dengan ketentuan-ketentuan sebagai berikut:';
  }
  // Sisanya memang pemesanan pekerjaan: jasa, tenaga kerja, subkontraktor.
  return 'Untuk melakukan pekerjaan dengan ketentuan-ketentuan sebagai berikut:';
}

export function formatDate(value: Date | string): string {
  const d = value instanceof Date ? value : new Date(value);
  if (isNaN(d.getTime())) return '-';
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export function rupiah(value: number): string {
  return (Number(value) || 0).toLocaleString('id-ID', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
}

/** Baris tabel barang + baris Sub Total / PPN / Total. */

/**
 * Lampiran "Tata cara penagihan dan pembayaran" (lembar terpisah).
 *
 * Ada dua versi: PEMBELIAN BARANG CASH dan PEMBELIAN BARANG TEMPO. Isinya
 * hampir sama; yang membedakan hanya dokumen penagihan awal (Proforma
 * Invoice vs Invoice) dan redaksi ketentuan pengiriman via kurir.
 */
export function buildBillingTerms(tempo: boolean): any[] {
  const firstDocument = tempo
    ? `Invoice yang menyatakan jumlah yang harus dibayar dan nomor rekening penerima (soft copy) via email ke ${OFFICE_CONTACT.email} atau via hardcopy ke alamat yang tertera dibawah;`
    : `Proforma Invoice yang menyatakan jumlah yang harus dibayar dan nomor rekening penerima (soft copy) via email ke ${OFFICE_CONTACT.email} atau via hardcopy ke alamat yang tertera dibawah;`;

  const courierClause = tempo
    ? 'Khusus untuk penerima kontrak yang berada diluar Jabodetabek, pengiriman dokumen penagihan dapat dilakukan melalui jasa Kurir dan dilakukan khusus di hari SENIN-RABU. Apabila terjadi kehilangan akibat kesalahan hari pengiriman, PIHAK PERTAMA tidak dapat bertanggung jawab.'
    : 'Khusus untuk penerima kontrak yang berada diluar Jabodetabek, pengiriman dokumen penagihan dapat dilakukan melalui jasa Kurir dan dilakukan khusus di antara hari Senin dan Rabu. PIHAK PERTAMA tidak bertanggung jawab atas kehilangan dokumen pada saat proses pengiriman.';

  return [
    {
      stack: [
        {
          text: 'PIHAK PENJUAL berhak menagihkan barang penjualannya sebelum pengambilan/pengiriman barang dengan mengirimkan dokumen-dokumen sebagai berikut:',
        },
        {
          ul: [
            firstDocument,
            'Purchase Order (PO) yang telah ditandatangani (salinan);',
          ],
          margin: [0, 2, 0, 0] as Margins,
        },
      ],
    },
    {
      stack: [
        {
          text: 'PIHAK PENJUAL berkewajiban untuk mengirimkan dokumen-dokumen penjualan asli selambat-lambatnya 3 (tiga) hari kerja setelah transaksi pembayaran dilakukan. Adapun dokumen yang diperlukan adalah sebagai berikut:',
        },
        {
          ul: [
            'Invoice yang menyatakan jumlah yang harus dibayar dan nomor rekening penerima (asli);',
            'Kwitansi bermaterai (asli);',
            'Purchase Order (PO) yang telah ditandatangani (salinan);',
            'Dokumentasi (video) penyerahterimaan barang beserta kondisi pada saat serah terima;',
            'Surat Jalan yang sudah ditandatangani oleh perwakilan PIHAK PEMBELI;',
            'Faktur Pajak (bila ada);',
            'Surat Keaslian Barang (bila ada); dan',
            'Sertifikat Garansi (bila ada).',
          ],
          margin: [0, 2, 0, 0] as Margins,
        },
      ],
    },
    {
      stack: [
        {
          text: 'Dokumen dapat dikirimkan ke alamat kantor PT. Alpha Konstruksi Nusantara, yaitu:',
        },
        {
          text: 'KANTOR PT. ALPHA KONSTRUKSI NUSANTARA',
          bold: true,
          decoration: 'underline' as any,
          alignment: 'center' as Alignment,
          margin: [0, 10, 0, 0] as Margins,
        },
        {
          text: 'RUKO ASIA TROPIS AT 12 NO. 21',
          alignment: 'center' as Alignment,
        },
        {
          text: 'KOTA HARAPAN INDAH - BEKASI',
          alignment: 'center' as Alignment,
          margin: [0, 0, 0, 10] as Margins,
        },
      ],
    },
    'Proses pembayaran tagihan vendor dilakukan melalui Transfer Bank ke nomor rekening yang tercantum dalam dokumen penagihan (WAJIB sesuai dengan nama penandatangan kontrak kerja). Bilamana ditemukan perbedaan nama penerima, vendor WAJIB memberikan surat kuasa asli dan bermaterai yang ditandatangani oleh penerima kontrak.',
    courierClause,
    'Tata cara pembayaran ini merupakan sebuah kesatuan dengan kontrak yang diterima dan menjadi syarat dalam pengajuan pembayaran.',
  ];
}

/** Termin berjangka (kredit/prepaid) memakai lampiran versi TEMPO. */
export function isTempoTerm(paymentTerm?: string): boolean {
  return ['CR', 'CRD', 'PPD'].includes(String(paymentTerm || '').toUpperCase());
}

/** Kop surat: dipasang sebagai header di setiap halaman. */
export function documentHeader() {
  return {
    stack: [
      { image: LETTERHEAD, width: 505 },
      { image: FOOTER_RULE, width: 505, margin: [0, 4, 0, 0] as Margins },
    ],
    margin: [45, 18, 45, 0] as Margins,
  };
}

/** Footer: garis, alamat kantor, dan kotak paraf PROC/PM/DIR. */
export function documentFooter() {
  return {
    stack: [
      { image: FOOTER_RULE, width: 505, margin: [0, 0, 0, 5] as Margins },
      {
        columns: [
          { text: '', width: 60 },
          {
            width: '*',
            stack: [
              { text: `Office : ${OFFICE_FOOTER.office}` },
              { text: `Phone : ${OFFICE_FOOTER.phone}` },
              { text: `Email : ${OFFICE_FOOTER.email}` },
            ],
            alignment: 'center' as Alignment,
            fontSize: 9,
            lineHeight: 1.15,
          },
          { image: APPROVAL_BOX, width: 60 },
        ],
      },
    ],
    margin: [45, 8, 45, 0] as Margins,
  };
}

/**
 * Baris nama pada blok tanda tangan.
 *
 * DIKOSONGKAN selama dokumennya belum disetujui, lalu diisi nama penyetuju
 * setelah ada persetujuan.
 *
 * Sebelumnya satu nama ditulis tetap di enam helper. Yang menandatangani
 * tidak selalu orang itu, sehingga dokumen tercetak atas nama seseorang yang
 * tidak menyetujuinya — dan pada dokumen yang mengikat, itu bukan sekadar
 * salah tulis.
 *
 * Jabatan diambil dari kolom `position` pada pengguna, BUKAN diturunkan dari
 * level akses: level menentukan apa yang boleh dilakukan, bukan apa
 * jabatannya. Pengguna yang belum mengisi jabatannya dicetak tanpa baris itu.
 */
/** Lebar garis tanda tangan, disamakan di seluruh dokumen. */
const LEBAR_GARIS_TTD = 170;

/** Abu-abu penunjuk; cukup terbaca, tetapi jelas bukan isi dokumen. */
const ABU_PENUNJUK = '#B8BCC4';

/**
 * Lebar satu kolom tanda tangan pada susunan dua kolom.
 *
 * A4 tegak 595,28pt dikurangi margin kiri-kanan 45+45, dibagi dua, lalu
 * dikurangi jarak antar kolom bawaan pdfmake. Dihitung sekali di sini karena
 * `canvas` TIDAK menghormati `alignment` — garisnya selalu digambar dari tepi
 * kiri kolomnya, dan meratakannya ke kanan hanya bisa lewat margin.
 */
const LEBAR_KOLOM_TTD = (595.28 - 90) / 2 - 10;

export function signerLines(
  approvedByName?: string | null,
  approvedByPosition?: string | null,
  rataKanan = false,
) {
  const nama = (approvedByName || '').trim();
  // Perataan yang sama dipakai seluruh baris blok ini, supaya nama, garis,
  // dan jabatannya tidak pernah tercecer ke sisi yang berbeda.
  const rata = (rataKanan ? 'right' : 'left') as Alignment;
  const jabatan = (approvedByPosition || '').trim();
  const belumSetuju = !nama;

  return [
    /*
     * Ruang tanda tangan, di ATAS baris nama.
     *
     * Urutannya mengikuti dokumen resmi: tanda tangan dibubuhkan lebih dulu,
     * lalu nama tertulis di atas garis, dan jabatan di bawahnya. Garis itulah
     * yang menggarisbawahi namanya — bukan pemisah antara tanda tangan dan
     * nama.
     */
    {
      text: belumSetuju ? 'Sign Here' : ' ',
      alignment: rata,
      color: ABU_PENUNJUK,
      fontSize: 9,
      italics: true,
      margin: [0, 12, 0, 0] as Margins,
    },
    // Ruang kosong tempat tanda tangan dibubuhkan.
    { text: ' ', margin: [0, 0, 0, 12] as Margins },

    /*
     * Nama, tepat di atas garis.
     *
     * Belum disetujui, yang tercetak penunjuk abu-abu "Nama" — supaya yang
     * mengisi tahu apa yang harus ditulis, dan tidak menuliskan jabatannya
     * di baris yang salah.
     */
    belumSetuju
      ? {
          text: 'Nama',
          alignment: rata,
          color: ABU_PENUNJUK,
          fontSize: 9,
          italics: true,
        }
      : { text: nama, alignment: rata, bold: true },

    // Garis digambar, bukan garis bawah pada teks: teks kosong tidak
    // menghasilkan garis bawah, sedangkan panjangnya harus tetap sama pada
    // kedua keadaan.
    {
      canvas: [
        {
          type: 'line',
          x1: 0,
          y1: 0,
          x2: LEBAR_GARIS_TTD,
          y2: 0,
          lineWidth: 0.8,
          lineColor: '#16181D',
        },
      ],
      // Garis digeser ke kanan lewat margin: `canvas` tidak menghormati
      // `alignment`, sehingga tanpa ini ia tetap menempel di tepi kiri
      // sementara nama di atasnya sudah pindah ke kanan.
      margin: [
        rataKanan ? LEBAR_KOLOM_TTD - LEBAR_GARIS_TTD : 0,
        2,
        0,
        4,
      ] as Margins,
    },

    // Jabatan, di bawah garis. Penunjuknya juga abu-abu bila belum diisi.
    belumSetuju || !jabatan
      ? {
          text: 'Jabatan',
          alignment: rata,
          color: ABU_PENUNJUK,
          fontSize: 9,
          italics: true,
        }
      : { text: jabatan, alignment: rata },
  ];
}

/** Blok tanda tangan; unbreakable agar tidak terpotong antar halaman. */
/**
 * Keterangan penelusuran di bawah blok tanda tangan.
 *
 * BUKAN pengganti tanda tangan basah. Tanda tangan elektronik baru
 * menggantikannya bila tersertifikasi dari penyelenggara resmi, dan vendor
 * pun harus punya akun di penyelenggara yang sama untuk menandatangani balik.
 *
 * Nilainya penelusuran: ketika vendor menanyakan sebuah dokumen setahun
 * kemudian, atau ketika ada pertanyaan siapa menyetujui apa, keterangannya
 * ada di lembarnya sendiri — tanpa perlu membuka sistem.
 *
 * Tidak tercetak sama sekali bila dokumennya belum disetujui. Menuliskan
 * "disetujui" pada lembar draf, walau dengan tanggal kosong, membuat lembar
 * yang belum sah terbaca seperti sudah.
 */
function keteranganPersetujuan(
  approvedAt?: string | Date | null,
  checkedByName?: string | null,
  documentNumber?: string | null,
) {
  if (!approvedAt) return [];

  const t = approvedAt instanceof Date ? approvedAt : new Date(approvedAt);
  if (isNaN(t.getTime())) return [];

  /*
   * Tanggal disusun dari bagian waktu SETEMPAT.
   *
   * `toISOString()` mengubahnya ke UTC lebih dulu, dan bagi WIB itu
   * memundurkan tanggalnya tujuh jam — dokumen yang disetujui pukul 05.00
   * akan tercetak disetujui sehari sebelumnya.
   */
  const BULAN = [
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
  ];
  const dd = (n: number) => String(n).padStart(2, '0');
  const tanggal =
    `${t.getDate()} ${BULAN[t.getMonth()]} ${t.getFullYear()}, ` +
    `${dd(t.getHours())}.${dd(t.getMinutes())} WIB`;

  const baris: string[] = [`Disetujui secara elektronik pada ${tanggal}`];

  const kedua: string[] = [];
  if (checkedByName) kedua.push(`Diperiksa oleh ${checkedByName}`);
  if (documentNumber) kedua.push(documentNumber);
  if (kedua.length) baris.push(kedua.join(' \u00b7 '));

  return [
    {
      text: baris.join('\n'),
      fontSize: 7,
      color: ABU_PENUNJUK,
      margin: [0, 10, 0, 0] as Margins,
    },
  ];
}

export function signatureBlock(
  approvedByName?: string | null,
  approvedByPosition?: string | null,
  approvedAt?: string | Date | null,
  checkedByName?: string | null,
  documentNumber?: string | null,
) {
  return {
    unbreakable: true,
    stack: [
      { text: 'Hormat kami,' },
      { text: 'PT. Alpha Konstruksi Nusantara' },
      // Jarak ke garis diatur `signerLines` lewat margin penandanya, bukan
      // lewat baris kosong: baris kosong menambah tinggi yang tidak sama
      // pada kedua keadaan.
      ...signerLines(approvedByName, approvedByPosition),
      // Ketiganya opsional: pemanggil lama yang belum mengirimnya tetap
      // menghasilkan dokumen yang sama seperti sebelumnya.
      ...keteranganPersetujuan(approvedAt, checkedByName, documentNumber),
    ],
  };
}

/** Gaya teks yang dipakai seluruh dokumen PO. */
export const DOCUMENT_STYLES = {
  docTitle: {
    fontSize: 16,
    bold: true,
    alignment: 'center' as Alignment,
    lineHeight: 1,
    margin: [0, 0, 0, 2] as Margins,
  },
  docSubTitle: {
    alignment: 'center' as Alignment,
    lineHeight: 1,
  },
  // Header tabel tanpa warna latar: hemat tinta saat dicetak, dan
  // pembeda barisnya sudah cukup dari huruf tebal + garis tabel.
  th: { bold: true, fontSize: 11, lineHeight: 1 },
  td: { fontSize: 11, lineHeight: 1 },
};

export const DOCUMENT_DEFAULT_STYLE = {
  font: 'Calibri',
  fontSize: 11,
  lineHeight: 1.15,
};

/**
 * Cap air DRAFT untuk dokumen yang belum disetujui.
 *
 * Purchase order yang belum disetujui masih dapat dicetak — dan memang perlu,
 * untuk diperiksa sebelum disahkan. Persoalannya lembar itu tidak dapat
 * dibedakan dari yang sudah sah begitu keluar dari pencetak: bentuknya sama
 * persis, lengkap dengan blok tanda tangan.
 *
 * Sudah cukup bagi satu lembar draf untuk sampai ke vendor dan dianggap
 * mengikat.
 *
 * `pdfmake` menempatkan `watermark` di BELAKANG isi halaman, sehingga
 * teksnya tidak menutupi angka maupun uraian pekerjaan. Warnanya sengaja
 * pucat: cukup terbaca untuk menyadarkan, tidak sampai mengganggu pembacaan.
 *
 * Dikembalikan `undefined` bila sudah disetujui — `pdfmake` mengabaikan
 * bidang yang tidak ada, sehingga dokumen sah tercetak tanpa perubahan
 * apa pun.
 */
export function draftWatermark(isApproved?: boolean, status?: string):
  | { text: string; color: string; opacity: number; bold: boolean; angle: number }
  | undefined {
  /*
   * Memeriksa DUA sumber, bukan satu.
   *
   * Sebagian dokumen tersimpan dengan `status: "approved"` sementara
   * `isApproved` masih `false`. Memeriksa `isApproved` saja membubuhkan cap
   * DRAFT pada dokumen yang sudah sah — dan itu justru membuat lembar yang
   * benar tampak tidak berlaku.
   */
  const sah = !!isApproved || String(status || '').toLowerCase() === 'approved';
  if (sah) return undefined;

  return {
    text: 'DRAFT',
    color: '#9aa3b2',
    opacity: 0.18,
    bold: true,
    angle: -45,
  };
}

export const DOCUMENT_PAGE = {
  pageSize: 'A4' as PageSize,
  pageMargins: [45, 86, 45, 80] as Margins,
};

/** Layout garis + padding tabel barang. */
export const TABLE_LAYOUT = {
  hLineWidth: () => 0.5,
  vLineWidth: () => 0.5,
  hLineColor: () => '#9aa1ad',
  vLineColor: () => '#9aa1ad',
  paddingTop: () => 4,
  paddingBottom: () => 4,
};

/**
 * Ubah baris klausul menjadi objek teks pdfmake.
 *
 * Template klausul menandai poin yang dinonaktifkan dengan tag <s>…</s>
 * (dipakai apa adanya oleh preview HTML di formulir). pdfmake tidak
 * membaca HTML, jadi tag itu harus diterjemahkan menjadi properti
 * `decoration: 'lineThrough'` — kalau tidak, tagnya ikut tercetak.
 */
/**
 * Daftar poin perjanjian, termasuk sub-poin bersarang.
 *
 * Anggota berupa array menjadi daftar huruf (a, b, c) di bawah poin
 * sebelumnya. Dipakai bersama oleh seluruh helper agar penomoran bersarang
 * tampil sama di setiap dokumen.
 */
export function clauseList(lines: (string | string[])[]): any {
  return {
    ol: (lines || []).map((x) =>
      Array.isArray(x)
        ? {
            // Sub-poin dirapatkan: jaraknya cukup dari poin induknya, dan
            // jeda penuh di sini membuat rinciannya tampak terpisah dari
            // ketentuan yang menaunginya.
            ol: x.map(subClauseToPdf),
            type: 'lower-alpha' as any,
            margin: [0, 0, 0, CLAUSE_GAP] as Margins,
          }
        : clauseToPdf(x),
    ),
  };
}

/** Sub-poin: sama seperti poin biasa, tetapi jaraknya lebih rapat. */
function subClauseToPdf(line: string): any {
  return { ...clauseToPdf(line), margin: [0, 0, 0, 2] as Margins };
}

/**
 * Jarak bawah tiap poin perjanjian, dalam satuan pt.
 *
 * Kira-kira setengah tinggi barisnya (teks 11pt), cukup untuk memisahkan
 * poin tanpa membuat dokumen bertambah halaman. Tanpa jeda ini, poin yang
 * panjang menyambung ke poin berikutnya dan sulit dibaca di lapangan.
 */
export const CLAUSE_GAP = 6;

export function clauseToPdf(line: string): any {
  const match = /^\s*<s>([\s\S]*)<\/s>\s*$/i.exec(line || '');
  if (match) {
    return {
      text: stripHtmlTags(match[1]),
      decoration: 'lineThrough' as any,
      color: '#6b7280',
      margin: [0, 0, 0, CLAUSE_GAP] as Margins,
    };
  }
  return {
    text: stripHtmlTags(line),
    margin: [0, 0, 0, CLAUSE_GAP] as Margins,
  };
}

/** Buang sisa tag HTML sederhana agar tidak ikut tercetak. */
export function stripHtmlTags(value: string): string {
  return (value || '')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&nbsp;/g, ' ')
    .trim();
}

/**
 * Susun nama vendor untuk dokumen.
 *
 * Prefix badan usaha (PT., CV., UD., Yayasan, dst) tetap ditulis karena
 * bagian dari nama resminya. Sebaliknya "Pribadi" dan "Lainnya" hanya
 * penanda jenis supplier di sistem, bukan nama — sehingga tidak dicetak.
 *
 * Nama dari pemilih supplier bisa sudah memuat prefix di belakang
 * ("Dedi, Pribadi"); bagian itu dibersihkan lebih dulu agar tidak dobel.
 */
const NON_ENTITY_PREFIXES = ['pribadi', 'lainnya', 'perorangan'];

export function vendorDisplayName(name?: string, prefix?: string): string {
  const bersih = String(name || '')
    // buang ", Pribadi" / ", PT." yang ikut terbawa dari pemilih supplier
    .replace(
      /,\s*(pribadi|lainnya|perorangan|pt\.?|cv\.?|ud\.?|yayasan)\s*$/i,
      '',
    )
    .trim();

  const p = String(prefix || '').trim();
  if (!p || NON_ENTITY_PREFIXES.includes(p.toLowerCase())) return bersih || '-';

  // Hindari penulisan ganda bila nama sudah diawali prefiksnya.
  if (bersih.toLowerCase().startsWith(p.toLowerCase())) return bersih;
  return `${p} ${bersih}`.trim();
}

/**
 * Nama pemasok dari SATU BARIS jawaban purchase order.
 *
 * Ada karena penamaannya pernah berbeda antara kueri daftar dan kueri satu
 * dokumen: yang satu `supplierName`, yang lain `supplier_name`. Perbedaan itu
 * tidak menimbulkan galat apa pun — bidang yang salah nama hanya bernilai
 * `undefined`, dan seluruh kolom pemasok berubah menjadi "—" berikut lencana
 * "?" seolah datanya yang hilang.
 *
 * Backend kini seragam camelCase dan dijaga pengujian di sana. Bentuk
 * bergaris bawah tetap dibaca di sini sebagai jaring pengaman: backend dan
 * frontend disebar terpisah, dan di antara kedua penyebaran itu jawaban lama
 * masih beredar.
 *
 * Satu fungsi untuk seluruh layar — daftar, pemilih, cetak — supaya nama
 * bidangnya hanya disebut di SATU tempat.
 */
export function namaPemasokBaris(po: any): string {
  return vendorDisplayName(
    po?.supplierName ?? po?.supplier_name,
    po?.supplierPrefix ?? po?.supplier_prefix,
  );
}
