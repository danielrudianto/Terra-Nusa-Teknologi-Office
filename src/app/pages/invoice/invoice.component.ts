import { CommonModule } from '@angular/common';
import { vendorDisplayName } from 'src/app/helpers/purchase-order-shared.helper';
import { proxyPaymentContent } from 'src/app/helpers/proxy-payment.helper';
import { TranslateService } from '@ngx-translate/core';
import { ServerMessageService } from 'src/app/services/server-message.service';
import { Component, inject } from '@angular/core';
import {
  FormArray,
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSnackBar } from '@angular/material/snack-bar';
import { NgxMaskDirective, provideNgxMask } from 'ngx-mask';
import { TranslatePipe } from '@ngx-translate/core';
import { HeaderTitleComponent } from '../../components/header-title/header-title.component';
import { SupplierSelectorComponent } from '../../components/supplier-selector/supplier-selector.component';
import { IPPh, availablePPh } from '../../utils/pph';
import { IBank, banks } from '../../utils/bank';
import { printInvoiceDocument } from '../../helpers/invoice.helper';
import { buildPurchaseOrderDContent } from '../../helpers/purchase-order-d.helper';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { ApiService } from '../../services/api.service';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatSelectModule } from '@angular/material/select';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { tanggalLokal } from '../../utils/tanggal';
import { konteksKlausulTenagaKerja } from '../../helpers/klausul-tenaga-kerja.helper';

/**
 * Kode PPh yang berlaku untuk invoice tenaga kerja.
 *
 * Dibatasi dua pilihan agar tidak salah pilih; nama objek dan tarifnya tetap
 * diambil dari katalog `availablePPh` supaya tidak ada dua sumber data.
 */
const INVOICE_PPH_CODES = ['21-100-35', '21-100-20'];

/** Angka bulan -> angka Romawi, dipakai pada penomoran dokumen. */
const ROMAN = [
  'I',
  'II',
  'III',
  'IV',
  'V',
  'VI',
  'VII',
  'VIII',
  'IX',
  'X',
  'XI',
  'XII',
];

@Component({
  selector: 'app-invoice',
  providers: [provideNativeDateAdapter(), provideNgxMask()],
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatDatepickerModule,
    MatIconModule,
    MatCheckboxModule,
    MatAutocompleteModule,
    MatSelectModule,
    NgxMaskDirective,
    TranslatePipe,
    HeaderTitleComponent,
  ],
  templateUrl: './invoice.component.html',
  styleUrl: './invoice.component.scss',
})
export class InvoiceComponent {
  private readonly serverMessage = inject(ServerMessageService);

  private readonly translate = inject(TranslateService);
  constructor(
    private dialog: MatDialog,
    private snackBar: MatSnackBar,
    private apiService: ApiService,
  ) {}

  isSubmitting = false;

  formGroup: FormGroup = new FormGroup({
    supplierID: new FormControl('', Validators.required),
    supplierName: new FormControl('', Validators.required),
    projectCode: new FormControl('', [
      Validators.required,
      Validators.pattern(/^[A-Z0-9]{3,6}$/),
    ]),
    // Teks bebas: lokasi proyek bisa di mana saja, daftar tetap justru
    // menghambat saat ada proyek di kota baru.
    city: new FormControl('Bandung', Validators.required),
    cutOffDate: new FormControl('', Validators.required),
    date: new FormControl('', Validators.required),
    bankAccountNumber: new FormControl('', Validators.required),
    bankAccountName: new FormControl('', Validators.required),
    bankName: new FormControl('', Validators.required),
    // Opsi pencatatan pembelian sekalian
    createPurchase: new FormControl(false),
    // Cukup diisi angka urutnya; nomor lengkapnya dirakit otomatis.
    purchaseOrderNumber: new FormControl(null, [Validators.min(1)]),
    // Surat pengalihan pembayaran; hanya berlaku bila pembeliannya dicatat.
    proxyPayment: new FormControl(false),
    // Kode & objek pajak diisi lewat pemilih PPh, sama seperti halaman
    // pembelian — supaya data yang tercatat seragam dan rekap PPh lengkap.
    pphCode: new FormControl(''),
    pphTaxObject: new FormControl(''),
    pphPercentage: new FormControl(0, [Validators.min(0), Validators.max(100)]),

    // Tiga mata pekerjaan baku; nilainya diisi per periode.
    items: new FormArray([
      InvoiceComponent.buildItem('Upah Harian', 'hari'),
      InvoiceComponent.buildItem('Lembur', 'jam'),
      InvoiceComponent.buildItem('Bonus', 'hari'),
      InvoiceComponent.buildItem('Insentif Bor', 'meter'),
    ]),
  });

  private static buildItem(name: string, unit: string): FormGroup {
    return new FormGroup({
      name: new FormControl(name, Validators.required),
      quantity: new FormControl(0, [Validators.required, Validators.min(0)]),
      unit: new FormControl(unit, Validators.required),
      price: new FormControl(0, [Validators.required, Validators.min(0)]),
    });
  }

  get items(): FormArray {
    return this.formGroup.get('items') as FormArray;
  }

  itemAt(i: number): FormGroup {
    return this.items.at(i) as FormGroup;
  }

  lineTotal(i: number): number {
    const v = this.itemAt(i).getRawValue();
    return (Number(v.quantity) || 0) * (Number(v.price) || 0);
  }

  get grandTotal(): number {
    return this.items.controls.reduce(
      (acc, _c, i) => acc + this.lineTotal(i),
      0,
    );
  }

  /** Upah tenaga kerja tidak dikenai PPN; DPP = nilai invoice apa adanya. */
  get pphValue(): number {
    const pct = Number(this.formGroup.get('pphPercentage')?.value) || 0;
    return (this.grandTotal * pct) / 100;
  }

  /** Nilai yang dibayarkan setelah PPh dipotong. */
  get netTotal(): number {
    return this.grandTotal - this.pphValue;
  }

  get willCreatePurchase(): boolean {
    return !!this.formGroup.get('createPurchase')?.value;
  }

  // --- supplier ------------------------------------------------------------
  openSupplierSelector() {
    this.dialog
      .open(SupplierSelectorComponent, {})
      .afterClosed()
      .subscribe((data: any) => {
        if (!data) return;
        this.formGroup.patchValue({
          supplierID: data.id,
          /*
           * Nama disusun helper yang sama dengan seluruh dokumen lain.
           *
           * Dua hal ditangani sekaligus: prefix badan usaha (PT., CV., UD.)
           * ikut ditulis karena bagian dari nama resminya, sedangkan
           * "Pribadi" dan "Lainnya" tidak — keduanya penanda jenis supplier
           * di sistem, bukan nama. Nama yang sudah terlanjur membawa
           * ", Pribadi" dari pemilih juga dibersihkan di sana.
           */
          supplierName: vendorDisplayName(data.name, data.prefix),
        });
        this.applyFrequentBank(data.id);
      });
  }

  /**
   * Isi rekening dari pembayaran yang paling sering/terakhir dipakai
   * supplier ini — memakai endpoint yang sama dengan halaman pembelian,
   * sehingga riwayatnya konsisten dan berlaku lintas perangkat.
   */
  private applyFrequentBank(supplierID: number) {
    this.apiService
      .get(`purchases/frequent-payment/${supplierID}`, {})
      .subscribe({
        next: (data: any) => {
          if (!data) return;
          this.formGroup.patchValue({
            bankName: data.bankName ?? '',
            bankAccountName: data.bankAccountName ?? '',
            bankAccountNumber: data.bankAccountNumber ?? '',
          });
        },
        // Tidak ada riwayat bukan kondisi galat: rekening cukup diisi manual.
        error: () => {},
      });
  }

  /**
   * Nama bank dipilih dari daftar baku, bukan diketik bebas — supaya
   * penulisannya seragam pada seluruh dokumen dan rekap.
   */
  readonly bankOptions: IBank[] = banks;
  filteredBanks: IBank[] = banks;

  /**
   * Saring daftar bank.
   *
   * Kata kuncinya dibaca dari elemen masukan, BUKAN dari nilai formulir.
   * Autocomplete di sini memakai `requireSelection`, yang menahan nilai
   * formulir sampai ada pilihan yang benar-benar dipilih — sehingga selama
   * pengguna mengetik, nilai formulirnya masih yang lama dan daftarnya
   * tidak pernah menyaring apa pun.
   */
  filterBanks(event?: Event): void {
    const dariElemen = (event?.target as HTMLInputElement | undefined)?.value;
    const keyword = String(
      dariElemen ?? this.formGroup.get('bankName')?.value ?? '',
    )
      .toLowerCase()
      .trim();

    // Kosong atau persis salah satu pilihan: tampilkan semua agar mudah
    // diganti.
    const exact = this.bankOptions.some(
      (b) => b.name.toLowerCase() === keyword,
    );
    if (!keyword || exact) {
      this.filteredBanks = this.bankOptions.slice();
      return;
    }

    this.filteredBanks = this.bankOptions.filter(
      (b) =>
        b.name.toLowerCase().includes(keyword) ||
        (b.alias ?? '').toLowerCase().includes(keyword),
    );
  }

  /** Dua kode PPh yang boleh dipakai pada invoice tenaga kerja. */
  readonly pphOptions: IPPh[] = INVOICE_PPH_CODES.map((code) =>
    availablePPh.find((p) => p.code === code),
  ).filter((p): p is IPPh => !!p);

  /** Tarif mengikuti kode terpilih, tidak diketik manual. */
  onPphSelected(code: string) {
    const pph = this.pphOptions.find((p) => p.code === code);
    this.formGroup.patchValue({
      pphTaxObject: pph?.taxObjectName ?? '',
      pphPercentage: pph?.tariff ?? 0,
    });
  }

  clearPph() {
    this.formGroup.patchValue({
      pphCode: '',
      pphTaxObject: '',
      pphPercentage: 0,
    });
  }

  // --- penomoran -----------------------------------------------------------
  /**
   * Format: [tgl cut-off 2 digit]-[id supplier 3 digit]-INV-[kode proyek]-
   * [bulan Romawi dari tanggal invoice]-[tahun].
   * Contoh: 05-021-INV-R501-VIII-2026
   */
  get invoiceNumber(): string {
    const v = this.formGroup.getRawValue();
    if (!v.cutOffDate || !v.date || !v.supplierID || !v.projectCode) return '—';

    const cut = new Date(v.cutOffDate);
    const inv = new Date(v.date);
    const dd = String(cut.getDate()).padStart(2, '0');
    const id = String(v.supplierID).padStart(3, '0');
    const bulan = ROMAN[inv.getMonth()];

    const nomor = `${dd}-${id}-INV-${v.projectCode}-${bulan}-${inv.getFullYear()}`;
    // Pekerjaan pengeboran ditandai (B) di akhir nomor.
    return this.adaInsentifBor ? `${nomor} (B)` : nomor;
  }

  /**
   * Keterangan pembayaran pada kuitansi.
   *
   * Bila Insentif Bor terisi, pekerjaannya adalah jasa operator pengeboran,
   * sehingga keterangannya disesuaikan agar sesuai dengan yang dibayarkan.
   */
  private get keteranganKuitansi(): string {
    return this.adaInsentifBor
      ? 'Upah jasa operator pengeboran'
      : 'Upah pekerjaan';
  }

  /**
   * Penanda pekerjaan pengeboran.
   *
   * Dipakai dua tempat — keterangan kuitansi dan akhiran nomor dokumen —
   * sehingga keduanya tidak mungkin berbeda.
   */
  private get adaInsentifBor(): boolean {
    return this.items.controls.some((c) => {
      const v = c.getRawValue();
      return v.name === 'Insentif Bor' && (Number(v.quantity) || 0) > 0;
    });
  }

  /** Keterangan periode pada kuitansi, berakhir di tanggal cut-off. */
  private get periodeText(): string {
    const v = this.formGroup.getRawValue();
    if (!v.cutOffDate) return '';
    const cut = new Date(v.cutOffDate);
    const bulan = [
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
    ][cut.getMonth()];
    return `s.d. ${cut.getDate()} ${bulan} ${cut.getFullYear()}`;
  }

  // --- cetak ---------------------------------------------------------------
  /**
   * Hanya membuat dokumen. Tidak menyimpan apa pun dan formulir dibiarkan
   * apa adanya, sehingga bisa dicetak ulang atau disesuaikan lagi.
   */

  /**
   * Nomor SPK lengkap dari angka urut yang diketik.
   *
   * Contoh: 1 + proyek MICZ  ->  001-SPK-MICZ-D
   */
  get purchaseOrderName(): string {
    const v = this.formGroup.getRawValue();
    const n = Number(v.purchaseOrderNumber) || 0;
    if (!n || !v.projectCode) return '';
    return `${String(n).padStart(3, '0')}-SPK-${String(
      v.projectCode,
    ).toUpperCase()}-D`;
  }

  /**
   * Cari SPK-nya di basis data, lalu lampirkan di belakang kuitansi.
   *
   * Pencarian gagal atau tidak ketemu tidak membatalkan pencetakan invoice —
   * dokumennya tetap keluar, hanya tanpa lampiran.
   */
  private fetchPurchaseOrder(): Observable<any | null> {
    const nama = this.purchaseOrderName;
    if (!nama) return of(null);
    return this.apiService
      .get('purchase-orders', { keyword: nama, page_size: 5 })
      .pipe(
        map((res: any) => {
          const list = res?.data ?? res?.items ?? [];
          return list.find((x: any) => x?.name === nama) ?? null;
        }),
        catchError(() => of(null)),
      );
  }

  print(output: 'open' | 'download' = 'open') {
    if (!this.readyToPrint()) return;
    this.generateDocument(output).subscribe();
  }

  /**
   * Membuat dokumen sekaligus mencatat pembelian, lalu mengosongkan
   * formulir untuk invoice berikutnya.
   */
  save() {
    if (!this.readyToPrint()) return;

    const v = this.formGroup.getRawValue();
    /*
     * Diperiksa lewat getter, bukan lewat nilai formulir.
     *
     * Kontrolnya bernama `purchaseOrderNumber` (angka urut); nomor
     * lengkapnya disusun getter `purchaseOrderName`. Membaca
     * `v.purchaseOrderName` selalu menghasilkan undefined, sehingga
     * peringatan "No. PO belum diisi" muncul meski nomornya sudah diketik.
     */
    if (!this.purchaseOrderName) {
      this.snackBar.open(
        this.translate.instant('notify.poNumberEmpty'),
        'Close',
        { duration: 3000 },
      );
      return;
    }

    /*
     * Pencatatan menunggu dokumennya selesai dirakit.
     *
     * `savePurchase()` mengosongkan formulir begitu server menjawab. Bila
     * dijalankan berbarengan, jawaban server bisa datang lebih dulu
     * daripada pengambilan data SPK — formulir sudah nol saat dokumennya
     * dirakit, dan seluruh baris tercetak 0.
     */
    this.generateDocument('open').subscribe(() => this.savePurchase());
  }

  private readyToPrint(): boolean {
    if (this.formGroup.invalid) {
      this.formGroup.markAllAsTouched();
      return false;
    }
    if (this.grandTotal <= 0) {
      this.snackBar.open(
        this.translate.instant('notify.invoiceValueZero'),
        'Close',
        { duration: 3000 },
      );
      return false;
    }
    return true;
  }

  /**
   * Cetak invoice; SPK dicari lebih dulu agar bisa dilampirkan.
   * Bila SPK tidak ketemu, invoice tetap dicetak tanpa lampiran.
   */

  /** Ubah data PO dari server menjadi bentuk yang dipahami helper PO-D. */
  private toPrintData(po: any) {
    const custom = po?.customData ?? {};
    return {
      purchaseOrderName: po?.name ?? '',
      date: po?.date,
      projectName: po?.projectName ?? '',
      // PO-D memakai istilah "worker", bukan "supplier".
      workerName: po?.supplierName ?? '',
      workerPrefix: po?.supplierPrefix ?? '',
      workerAddress: po?.supplierAddress ?? '',
      workerCity: po?.supplierCity ?? '',
      workerNpwp: po?.supplierNpwp ?? '',
      // PO-D mencatat komponen upah: label + nominal per satuan.
      items: (po?.items ?? []).map((it: any) => ({
        label: it.task || it.item_description || '',
        amount: Number(it.price) || 0,
        unit: it.unit ?? '',
      })),
      /*
       * Konteks klausul DIRAKIT, bukan diteruskan mentah.
       *
       * `customData.wageSchedules` menyimpan DATA jadwal — larik objek
       * `{task, wages[]}` — sedangkan pembangun klausul menyisipkan isi
       * `wageSchedules` langsung sebagai poin perjanjian, dan tiap poin
       * melewati `stripHtmlTags()` yang memanggil `.replace()` atas nilainya.
       * Objek yang sampai ke sana melempar "replace is not a function" dan
       * SELURUH pencetakan berhenti.
       *
       * `konteksKlausulTenagaKerja` merakit kalimatnya dari data itu, persis
       * seperti pada daftar purchase order. Ia pula yang menurunkan
       * `paymentTerm`, nama proyek, dan tanggal panjang dari dokumennya bila
       * tidak tersimpan di `customData` — itulah sebab pratinjau dan hasil
       * cetak sempat berbeda.
       */
      clauseContext: konteksKlausulTenagaKerja(custom, po ?? {}),
      templateVersion: po?.templateVersion ?? '1.0',
      additionalClauses: custom.additionalClauses ?? [],
    };
  }

  /**
   * Merakit dokumen, lalu memberi tahu bahwa perakitannya SELESAI.
   *
   * Mengembalikan Observable, bukan void, karena pemanggilnya perlu tahu
   * kapan dokumennya benar-benar jadi. `save()` mencatat pembelian dan
   * mengosongkan formulir sesudah berhasil — bila keduanya berjalan
   * berbarengan, formulir bisa terkosongkan lebih dulu dan dokumen dirakit
   * dari isian yang sudah nol.
   */
  private generateDocument(
    output: 'open' | 'print' | 'download',
  ): Observable<void> {
    this.isFetchingPo = true;
    return this.fetchPurchaseOrder().pipe(
      map((po) => {
        this.isFetchingPo = false;
        if (this.purchaseOrderName && !po) {
          this.snackBar.open(
            `SPK ${this.purchaseOrderName} tidak ditemukan — invoice dicetak tanpa lampiran.`,
            'Close',
            { duration: 4000 },
          );
        }
        this.renderDocument(output, po);
      }),
    );
  }

  isFetchingPo = false;

  private renderDocument(
    output: 'open' | 'print' | 'download',
    po: any | null = null,
  ) {
    const v = this.formGroup.getRawValue();
    try {
      printInvoiceDocument(
        {
          invoiceNumber: this.invoiceNumber,
          city: v.city,
          date: v.date,
          supplierName: v.supplierName,
          // baris tanpa nilai tidak perlu ikut tercetak
          /*
           * Lampiran: SPK, lalu surat pengalihan bila diminta.
           *
           * Keduanya menumpang berkas yang sama, bukan terbit sendiri-
           * sendiri. Dua berkas terpisah harus disimpan, dikirim, dan
           * diarsipkan masing-masing padahal selalu dipakai bersama — dan
           * berkas kedua kerap diblokir peramban karena bukan hasil
           * penekanan tombol secara langsung.
           */
          attachment: [
            ...(po ? buildPurchaseOrderDContent(this.toPrintData(po)) : []),
            ...(v.proxyPayment
              ? proxyPaymentContent({
                  invoiceName: this.invoiceNumber,
                  // Invoice tenaga kerja tidak menerbitkan faktur pajak.
                  taxInvoiceName: '',
                  supplierName: String(v.supplierName ?? ''),
                  bankName: String(v.bankName ?? ''),
                  bankAccountNumber: String(v.bankAccountNumber ?? ''),
                  bankAccountName: String(v.bankAccountName ?? ''),
                  // Yang dialihkan adalah jumlah yang benar-benar
                  // dibayarkan, sesudah PPh dipotong.
                  totalPayment: this.netTotal,
                  date: v.date ? new Date(v.date) : new Date(),
                })
              : []),
          ],
          items: this.items.controls
            .map((c) => c.getRawValue())
            .filter((x) => (Number(x.quantity) || 0) > 0)
            .map((x) => ({
              name: x.name,
              quantity: Number(x.quantity) || 0,
              unit: x.unit,
              price: Number(x.price) || 0,
            })),
          bankAccountNumber: v.bankAccountNumber,
          bankAccountName: v.bankAccountName,
          bankName: v.bankName,
          keterangan: this.keteranganKuitansi,
          periode: this.periodeText,
        },
        output,
      );
    } catch (e) {
      console.error('Gagal membuat dokumen invoice:', e);
      this.snackBar.open(
        this.translate.instant('notify.createFailed'),
        'Close',
        {
          duration: 3000,
        },
      );
    }
  }

  /** Kosongkan isian nilai; identitas proyek & supplier dipertahankan. */
  private resetForm() {
    this.items.controls.forEach((c) => c.patchValue({ quantity: 0, price: 0 }));
    this.formGroup.patchValue({
      purchaseOrderName: '',
      pphCode: '',
      pphTaxObject: '',
      pphPercentage: 0,
    });
    this.formGroup.markAsPristine();
    this.formGroup.markAsUntouched();
  }

  private savePurchase() {
    const v = this.formGroup.getRawValue();
    /*
     * Diperiksa lewat getter, bukan lewat nilai formulir.
     *
     * Kontrolnya bernama `purchaseOrderNumber` (angka urut); nomor
     * lengkapnya disusun getter `purchaseOrderName`. Membaca
     * `v.purchaseOrderName` selalu menghasilkan undefined, sehingga
     * peringatan "No. PO belum diisi" muncul meski nomornya sudah diketik.
     */
    if (!this.purchaseOrderName) {
      this.snackBar.open(
        this.translate.instant('notify.poNumberEmpty'),
        'Close',
        { duration: 3000 },
      );
      return;
    }

    const toISO = (d: any) => (d ? tanggalLokal(d) : null);

    this.isSubmitting = true;
    this.apiService
      .post('purchases', {
        procurementType: 'D',
        invoiceName: this.invoiceNumber,
        // kuitansi memakai nomor yang sama dengan invoice
        receiptName: this.invoiceNumber,
        taxInvoiceName: null,
        supplierID: v.supplierID,
        supplierName: v.supplierName,
        supplierAddress: '',
        date: toISO(v.date),
        dueDate: toISO(v.date),
        purchaseOrderName: this.purchaseOrderName,
        projectName: v.projectCode,
        purchaseType: 'D',
        isInternal: false,
        // upah tenaga kerja: tanpa PPN dan tanpa PBBKB
        dpp: this.grandTotal,
        ppn: 0,
        ppnValue: 0,
        pbbkb: 0,
        pphCode: v.pphCode,
        pphTaxObject: v.pphTaxObject,
        pphPercentage: Number(v.pphPercentage) || 0,
        pphValue: this.pphValue,
        otherValue: 0,
        otherValueNote: '',
        total: this.netTotal,
        isInvoiceAttached: true,
        isReceiptAttached: true,
        isTaxInvoiceAttached: false,
        isCopAttached: false,
        isCopyPurchaseOrderAttached: true,
        bankName: v.bankName,
        bankAccountName: v.bankAccountName,
        bankAccountNumber: v.bankAccountNumber,
        paymentMethod: 'Transfer',
        lastStatus: 'ready',
        lastStatusDescription: null,
      })
      .subscribe({
        next: () => {
          this.snackBar.open(
            this.translate.instant('notify.createSuccess'),
            'Close',
            {
              duration: 3000,
            },
          );
          // Hanya direset bila pencatatan berhasil, agar data tidak hilang
          // saat penyimpanan gagal dan perlu dicoba lagi.
          this.resetForm();
        },
        error: (error: any) => {
          this.snackBar.open(
            /*
             * Cadangannya BUKAN kalimat umum.
             *
             * Yang gagal di sini hanya pencatatan pembeliannya; dokumennya
             * sendiri sudah terbit. "Tindakan gagal dijalankan" membuat yang
             * membacanya mengira seluruhnya batal, lalu mengulang dari awal —
             * dan dokumen keduanya terbit dengan nomor baru.
             */
            this.serverMessage.terjemahkan(
              error,
              'notify.pembelianGagalDicatat',
            ),
            'Close',
            { duration: 5000 },
          );
        },
      })
      .add(() => {
        this.isSubmitting = false;
      });
  }
}
