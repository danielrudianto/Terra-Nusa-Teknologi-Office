import { Component, ElementRef, ViewChild, inject } from '@angular/core';
import { debounceTime, distinctUntilChanged } from 'rxjs';
import { ServerMessageService } from 'src/app/services/server-message.service';
import { TranslateService } from '@ngx-translate/core';
import {
  AbstractControl,
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
  ValidationErrors,
  ValidatorFn,
  Validators,
} from '@angular/forms';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { TranslatePipe } from '@ngx-translate/core';
import { PphSelectorComponent } from 'src/app/components/pph-selector/pph-selector.component';
import { SupplierSelectorComponent } from 'src/app/components/supplier-selector/supplier-selector.component';
import { ApiService } from 'src/app/services/api.service';
import { banks, IBank } from 'src/app/utils/bank';
import { IPPh } from 'src/app/utils/pph';
import { ProxyPaymentHelper } from 'src/app/helpers/proxy-payment.helper';
import { PaymentSlipHelper } from '../../../helpers/payment-slip.helper';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { HeaderTitleComponent } from '../../../components/header-title/header-title.component';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatSelectModule } from '@angular/material/select';
import { MatDividerModule } from '@angular/material/divider';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { CommonModule } from '@angular/common';
import { NgxMaskDirective, provideNgxMask } from 'ngx-mask';
import { MatInputModule } from '@angular/material/input';
import { Clipboard } from '@angular/cdk/clipboard';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ProjectSelectorComponent } from '../../../components/project-selector/project-selector.component';
import { BankAccountSelectorComponent } from '../../../components/bank-account-selector/bank-account-selector.component';
import { PurchaseOrderPickerComponent } from '../../../components/purchase-order-picker/purchase-order-picker.component';
import { PurchaseOrderRingkasComponent } from '../../../components/purchase-order-ringkas/purchase-order-ringkas.component';
import { JENIS_NILAI_LAIN } from 'src/app/constants/jenis-nilai-lain';
import {
  PILIHAN_CARA_BAYAR,
  PILIHAN_JENIS_DOKUMEN,
  PILIHAN_KELENGKAPAN,
  PILIHAN_LINGKUP,
  PILIHAN_PPN,
  PILIHAN_PROXY,
} from 'src/app/constants/pilihan-pembelian';

function lastStatusDescriptionRequired(): ValidatorFn {
  return (group: AbstractControl): ValidationErrors | null => {
    const lastStatus = group.get('lastStatus')?.value;
    const descControl = group.get('lastStatusDescription');
    if (
      lastStatus === 'draft' &&
      (!descControl?.value || descControl.value.trim().length < 10)
    ) {
      descControl?.setErrors({ required: true });
      return { lastStatusDescriptionRequired: true };
    } else if (
      lastStatus === 'draft' &&
      (!descControl?.value || descControl.value.trim().length > 99)
    ) {
      descControl?.setErrors({ required: true });
      return { lastStatusDescriptionRequired: true };
    } else {
      // Only clear if this was the error set by this validator
      if (descControl?.hasError('required')) {
        descControl.setErrors(null);
      }
      return null;
    }
  };
}

// create a validator function if createPayment is true, then bankAccountID is required
function bankAccountIDRequired(): ValidatorFn {
  return (group: AbstractControl): ValidationErrors | null => {
    const createPayment = group.get('createPayment')?.value;
    const bankAccountID = group.get('bankAccountID');
    if (
      createPayment == true &&
      (bankAccountID == null || bankAccountID.value.toString() == '')
    ) {
      bankAccountID?.setErrors({ required: true });
      return { bankAccountIDRequired: true };
    } else {
      // Only clear if this was the error set by this validator
      if (bankAccountID?.hasError('required')) {
        bankAccountID.setErrors(null);
      }
      return null;
    }
  };
}

@Component({
  selector: 'app-purchase-create',
  providers: [provideNgxMask()],
  imports: [
    BankAccountSelectorComponent,
    ProjectSelectorComponent,
    MatTooltipModule,
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    HeaderTitleComponent,
    MatDatepickerModule,
    MatSelectModule,
    MatDividerModule,
    MatAutocompleteModule,
    MatSlideToggleModule,
    NgxMaskDirective,
    TranslatePipe,
  ],
  templateUrl: './purchase-create.component.html',
  styleUrls: ['./purchase-create.component.scss'],
  standalone: true,
})
export class PurchaseCreateComponent {
  /*
   * Pilihan berbentuk kartu.
   *
   * Sebagian di antaranya MENGUBAH perilaku dokumen, bukan sekadar
   * melabelinya — "Menunggu dokumen" menyimpannya sebagai draf yang belum
   * dapat dibayar, dan "Pembelian internal" mengeluarkannya dari biaya
   * proyek. Dari daftar tarik-turun, akibat itu tidak terlihat.
   */
  readonly pilihanJenisDokumen = PILIHAN_JENIS_DOKUMEN;
  readonly pilihanKelengkapan = PILIHAN_KELENGKAPAN;
  readonly pilihanLingkup = PILIHAN_LINGKUP;
  readonly pilihanPpn = PILIHAN_PPN;
  readonly pilihanCaraBayar = PILIHAN_CARA_BAYAR;
  readonly pilihanProxy = PILIHAN_PROXY;

  /** Jenis nilai lain; satu sumber untuk seluruh layar pembelian. */
  readonly jenisNilaiLain = JENIS_NILAI_LAIN;

  private readonly serverMessage = inject(ServerMessageService);
  private readonly translate = inject(TranslateService);
  constructor(
    private apiService: ApiService,
    private dialog: MatDialog,
    private snackBar: MatSnackBar,
    private clipboard: Clipboard,
  ) {}

  @ViewChild('input') input!: ElementRef<HTMLInputElement>;

  filteredOptions: IBank[] = [];
  options: IBank[] = banks;
  isFinal: boolean = false;
  isSubmitting: boolean = false;
  bankAccounts: any[] = [];

  get isNumberValid() {
    return (
      this.valueFormGroup.controls['dpp'].valid &&
      this.valueFormGroup.controls['ppn'].valid &&
      this.valueFormGroup.controls['pbbkb'].valid
    );
  }

  metaFormGroup: FormGroup = new FormGroup(
    {
      invoiceName: new FormControl('', [Validators.required, Validators.maxLength(100)]),
      receiptName: new FormControl('', Validators.maxLength(100)),
      taxInvoiceName: new FormControl('', Validators.maxLength(17)),
      supplierID: new FormControl('', Validators.required),
      supplierName: new FormControl(''),
      supplierAddress: new FormControl(''),
      date: new FormControl('', Validators.required),
      dueDate: new FormControl('', Validators.required),
      purchaseOrderName: new FormControl('', [
        Validators.required,
        Validators.pattern(
          /^\d{3,4}-(PO|SPK|PKS)-[A-Z0-9]{4,5}-(A|B|C|D|E|F|G|H1|H2|5\.1\.1|5\.1\.2|5\.1\.6|5\.1\.7|6\.3\.1|6\.3\.2|5\.1\.12|6\.4\.1|6\.4\.2|6\.5\.1)$/,
        ),
        Validators.maxLength(100),
      ]),
      projectName: new FormControl('', [
        Validators.required,
        Validators.minLength(4),
        Validators.maxLength(5),
      ]),
      purchaseType: new FormControl('', [
        Validators.required,
        Validators.pattern(
          /^\A|B|C|D|E|F|G|H1|H2|5\.1\.1|5\.1\.2|5\.1\.6|5\.1\.7|6\.3\.1|6\.3\.2|5\.1\.12|6\.4\.1|6\.4\.2|6\.5\.1$/,
        ),
      ]),
      documentType: new FormControl('', Validators.required),
      lastStatus: new FormControl('ready', Validators.required),
      lastStatusDescription: new FormControl(''),
      isInternal: new FormControl(false, Validators.required),
    },
    { validators: lastStatusDescriptionRequired() },
  );

  valueFormGroup: FormGroup = new FormGroup({
    dpp: new FormControl('', [Validators.required, Validators.min(1)]),
    ppn: new FormControl('', [
      Validators.required,
      Validators.min(0),
      Validators.max(11),
    ]),
    ppnValue: new FormControl(0),
    pbbkb: new FormControl(0, [Validators.required, Validators.min(0)]),
    pphCode: new FormControl(''),
    pphTaxObject: new FormControl(''),
    pphPercentage: new FormControl(0, [Validators.required, Validators.min(0)]),
    pphValue: new FormControl(0),
    otherValue: new FormControl(0, [Validators.required, Validators.min(0)]),
    otherValueNote: new FormControl('', Validators.maxLength(255)),
    total: new FormControl(0, [Validators.required, Validators.min(0)]),
  });

  attachmentFormGroup: FormGroup = new FormGroup({
    isInvoiceAttached: new FormControl(false, Validators.requiredTrue),
    isReceiptAttached: new FormControl(false),
    isTaxInvoiceAttached: new FormControl(false),
    isCopAttached: new FormControl(false),
    isCopyPurchaseOrderAttached: new FormControl(
      false,
      Validators.requiredTrue,
    ),
  });

  paymentFormGroup: FormGroup = new FormGroup(
    {
      bankName: new FormControl('', Validators.required),
      bankAccountName: new FormControl('', Validators.required),
      bankAccountNumber: new FormControl('', [
        Validators.required,
        Validators.pattern(/^[0-9]+$/),
      ]),
      paymentMethod: new FormControl('', Validators.required),
      paymentTotal: new FormControl(0, [
        Validators.required,
        Validators.min(0),
      ]),
      proxyPayment: new FormControl(false),
      /*
       * Menyala sejak awal.
       *
       * Slip pembayaran hampir selalu dibuat; yang lupa mencentangnya baru
       * sadar ketika pembayarannya tidak muncul di mana pun, dan menambahkan
       * belakangan berarti mengetik ulang seluruh nilainya. Kebalikannya —
       * slip yang terlanjur dibuat padahal tidak perlu — masih dapat dibatalkan.
       *
       * Akibatnya `bankAccountID` ikut wajib sejak awal, lewat
       * `bankAccountIDRequired()`. Itu memang yang dikehendaki: slip tanpa
       * rekening asal tidak dapat dibuat.
       */
      createPayment: new FormControl(true),
      bankAccountID: new FormControl(''),
    },
    {
      validators: bankAccountIDRequired(),
    },
  );

  ngOnInit() {
    this.filteredOptions = this.options.slice();
    this.fetchBankAccounts();

    this.metaFormGroup.controls['documentType'].valueChanges.subscribe(() => {
      const documentType = this.metaFormGroup.value['documentType'];
      if (documentType == 'goods') {
        this.valueFormGroup.patchValue({
          pphCode: '',
          pphTaxObject: '',
          pphPercentage: 0,
          /*
           * `pphValue` ikut dikosongkan.
           *
           * Tarifnya sudah dinolkan sejak dulu, tetapi rupiahnya tidak —
           * `calculateTotal()` menghitungnya sebagai variabel lokal dan tidak
           * pernah menuliskannya kembali ke kolom ini. Nilai lama bertahan,
           * dan sejak isiannya disembunyikan pada pembelian barang, ia
           * bertahan tanpa terlihat siapa pun.
           */
          pphValue: 0,
        });
      }

      /*
       * Perhitungannya ditandai USANG.
       *
       * Berganti jenis mengubah ada-tidaknya potongan PPh, dan karenanya
       * mengubah nilai pembayaran. Tanpa baris ini `isFinal` tetap `true`:
       * tombol hitung tampak mati seolah angkanya sudah benar, padahal nilai
       * pembayaran yang tersimpan masih memuat potongan dari jenis yang
       * sebelumnya. Kolom PPh sendiri tidak mengubah `isFinal` — hanya dpp,
       * ppn, pbbkb, dan nilai lain yang melakukannya.
       */
      this.isFinal = false;
    });

    /*
     * Alasan menunggu dikosongkan begitu statusnya kembali "Siap".
     *
     * Isiannya disembunyikan pada status itu, dan nilai yang tertinggal di
     * baliknya tetap ikut terkirim — dokumen yang sudah lengkap akhirnya
     * tersimpan dengan keterangan menunggu berkas yang sebenarnya sudah ada.
     */
    this.metaFormGroup.controls['lastStatus'].valueChanges.subscribe(
      (status) => {
        if (status !== 'draft') {
          this.metaFormGroup.controls['lastStatusDescription'].setValue('');
        }
      },
    );

    /*
     * Rekening asal dikosongkan begitu slip pembayaran dimatikan.
     *
     * Isiannya disembunyikan pada keadaan itu, dan rekening yang tertinggal
     * di baliknya membuat `bankAccountIDRequired()` melihat isian yang sudah
     * terisi — sehingga menyalakan kembali sakelarnya tidak lagi menuntut
     * rekening dipilih ulang, padahal yang terakhir dipilih tidak pernah
     * terlihat lagi oleh yang mengisi.
     *
     * Dikosongkan ke '' dan BUKAN null: validatornya memanggil
     * `.toString()` atas nilainya.
     */
    this.paymentFormGroup.controls['createPayment'].valueChanges.subscribe(
      (aktif) => {
        if (aktif !== true) {
          this.paymentFormGroup.controls['bankAccountID'].setValue('');
        }
      },
    );

    /*
     * Nomor purchase order menentukan dua hal lain.
     *
     * Jenis pembeliannya mengikuti jenis dokumennya — PO menyertai barang,
     * SPK dan PKS menyertai pekerjaan — dan id yang tersimpan hanya berlaku
     * selama nomornya masih nomor yang dipilih. Nomor yang diketik tangan
     * mengosongkan id, sehingga tombol lihat tidak membuka dokumen lain.
     */
    const nomorPo = this.metaFormGroup.controls['purchaseOrderName'].valueChanges;

    /*
     * SEKETIKA: apa pun yang menempel pada nomor sebelumnya dilepas.
     *
     * Riwayat tagihan yang tertinggal adalah yang paling berbahaya di antara
     * ketiganya. Ia berbunyi "1 tagihan sudah masuk atas PO ini" sambil
     * menunjuk dokumen yang sudah tidak dirujuk lagi — dan yang membacanya
     * justru sedang memutuskan boleh-tidaknya menagih lagi. Salah baca di
     * situ berarti tagihan kedua atas purchase order yang belum pernah
     * ditagih, atau sebaliknya.
     *
     * Dikosongkan lebih dulu, bukan menunggu jawaban permintaan berikutnya:
     * di antara keduanya ada jeda yang cukup untuk dibaca.
     */
    nomorPo.subscribe((nomor) => {
      if (String(nomor || '') !== this.poTerpilihNomor) {
        this.poTerpilihId = null;
        this.poTerpilihNomor = '';
        this.tagihanPo = [];
        this.nilaiPo = 0;
        this.memuatTagihanPo = false;
      }
      this.terapkanJenisDariNomor(nomor);
    });

    /*
     * SESUDAH BERHENTI MENGETIK: dokumennya dicari, lalu bandingannya dimuat.
     *
     * Nomor yang diketik tangan sebelumnya tidak memuat apa pun — riwayat
     * tagihan hanya terisi lewat pencarian — sehingga yang mengetik nomornya
     * sendiri tidak pernah diperingatkan bahwa purchase order itu sudah
     * pernah ditagih.
     *
     * Ditunda 500 ms dan hanya untuk nomor yang sudah SAH menurut polanya:
     * tanpa keduanya, satu nomor yang diketik menghasilkan belasan
     * permintaan yang seluruhnya pasti tidak menemukan apa-apa.
     */
    nomorPo
      .pipe(debounceTime(500), distinctUntilChanged())
      .subscribe((nomor) => {
        const teks = String(nomor || '').trim();
        if (!teks || teks === this.poTerpilihNomor) return;
        if (this.metaFormGroup.controls['purchaseOrderName'].invalid) return;
        this.selaraskanDenganPoTertulis(teks);
      });
  }

  /**
   * Temukan purchase order dari nomor yang diketik, lalu muat bandingannya.
   *
   * Yang diambil dari dokumennya HANYA id dan nilainya — id agar tombol lihat
   * dapat membukanya, nilai agar sisa purchase order dapat dihitung. Isian
   * lain sengaja tidak ikut diisi: yang mengetik nomornya sendiri boleh jadi
   * sudah mengisi pemasok dan angkanya dengan sengaja, dan menimpanya di
   * tengah pengetikan menghapus pekerjaan yang tidak ia minta dihapus.
   *
   * Yang tidak ditemukan meninggalkan bandingan kosong, bukan bandingan lama.
   */
  private selaraskanDenganPoTertulis(nomor: string): void {
    this.apiService
      .get('purchase-orders', { keyword: nomor, page: 1, page_size: 10 })
      .subscribe({
        next: (res: any) => {
          const daftar: any[] = res?.data ?? [];
          // Cocok PERSIS, bukan sekadar mengandung: pencariannya memakai
          // `LIKE %nomor%`, sehingga "0412-PO-ALPHA-B" ikut mengembalikan
          // dokumen lain yang nomornya memuat potongan yang sama.
          const cocok = daftar.find(
            (d) =>
              String(d?.name || '').toUpperCase() === nomor.toUpperCase(),
          );
          if (!cocok) {
            this.tagihanPo = [];
            this.nilaiPo = 0;
            return;
          }

          this.poTerpilihId = cocok.id ?? null;
          this.poTerpilihNomor = String(cocok.name || '');
          this.nilaiPo = this.nilaiTagihan(cocok);
          this.muatTagihanPo(cocok.name);
        },
        // Gagal mencari TIDAK menghalangi pengisian; hanya bandingannya yang
        // tidak muncul.
        error: () => {
          this.tagihanPo = [];
          this.nilaiPo = 0;
        },
      });
  }

  ngAfterViewInit() {
    this.valueFormGroup.controls['ppn'].valueChanges.subscribe((value) => {
      if (value) {
        this.valueFormGroup.controls['ppnValue'].setValue(
          ((this.valueFormGroup.controls['dpp'].value * value) / 100).toFixed(
            2,
          ),
        );
      } else {
        this.valueFormGroup.controls['ppnValue'].setValue(0);
      }

      this.isFinal = false;
    });

    this.valueFormGroup.controls['dpp'].valueChanges.subscribe((value) => {
      if (value) {
        this.valueFormGroup.controls['ppnValue'].setValue(
          ((this.valueFormGroup.controls['ppn'].value * value) / 100).toFixed(
            2,
          ),
        );

        const pphPercentage =
          this.valueFormGroup.controls['pphPercentage'].value;
        const pphValue = (value * pphPercentage) / 100;
        this.valueFormGroup.controls['pphValue'].setValue(pphValue.toFixed(2));
      } else {
        this.valueFormGroup.controls['ppnValue'].setValue(0);
      }

      this.isFinal = false;
    });

    this.valueFormGroup.controls['pbbkb'].valueChanges.subscribe((value) => {
      this.isFinal = false;
    });

    this.valueFormGroup.controls['otherValue'].valueChanges.subscribe((_) => {
      this.isFinal = false;
    });

    this.metaFormGroup.controls['purchaseOrderName'].valueChanges.subscribe(
      (_) => {
        const purchaseOrderName =
          this.metaFormGroup.controls['purchaseOrderName'].value;
        const regex =
          /^\d{3,4}-(PO|SPK|PKS)-[A-Z0-9]{1,5}-(A|B|C|D|E|F|G|H1|H2|5\.1\.1|5\.1\.2|5\.1\.6|5\.1\.7|6\.3\.1|6\.3\.2|5\.1\.12|6\.4\.1|6\.4\.2|6\.5\.1)$/;
        const isValid = regex.test(purchaseOrderName);
        if (isValid) {
          // set the project name based on the purchase order name
          const projectName = purchaseOrderName.split('-')[2];
          const expenseType = purchaseOrderName.split('-')[3];
          this.metaFormGroup.controls['projectName'].setValue(projectName);
          this.metaFormGroup.controls['purchaseType'].setValue(expenseType);
        } else {
          // set the project name to empty string if the purchase order name is not valid
          this.metaFormGroup.controls['projectName'].setValue('');
        }
      },
    );
  }

  /**
   * Pilih purchase order, lalu salin datanya ke formulir ini.
   *
   * Yang disalin hanya bidang yang artinya SAMA di kedua dokumen. Tanggal
   * tidak ikut: `date` pada purchase order adalah tanggal terbit dokumennya,
   * sedangkan di sini tanggal faktur pemasok — dan menyalinnya membuat
   * jatuh tempo dihitung dari hari yang keliru.
   *
   * Nilai yang sudah diisi DITIMPA. Yang menekan tombol ini sedang menyatakan
   * bahwa dokumen inilah acuannya; membiarkan isian lama bertahan justru
   * meninggalkan campuran dua sumber yang tidak dapat ditelusuri.
   */
  /**
   * Tagihan yang SUDAH masuk atas purchase order yang sedang dirujuk.
   *
   * Pemasok menagih beberapa kali atas satu PO — bertahap, per pengiriman —
   * dan tidak ada yang mencegah tagihan kesekian melewati nilai PO-nya.
   * Yang menemukannya biasanya baru saat rekonsiliasi, berbulan kemudian.
   *
   * Ditampilkan SEBELUM nilainya diisi: yang hendak dicegah adalah mengetik
   * angka yang ternyata membuat totalnya melampaui.
   */
  tagihanPo: any[] = [];
  nilaiPo = 0;
  memuatTagihanPo = false;

  private muatTagihanPo(nomor: string): void {
    if (!nomor) {
      this.tagihanPo = [];
      return;
    }
    this.memuatTagihanPo = true;
    this.apiService
      .get(`purchases/purchase-order/${nomor}`, {})
      .subscribe({
        next: (res: any) => (this.tagihanPo = res?.data ?? []),
        // Gagal memuat TIDAK menghalangi pengisian; hanya bandingannya yang
        // tidak muncul.
        error: () => (this.tagihanPo = []),
      })
      .add(() => (this.memuatTagihanPo = false));
  }

  /** Nilai satu tagihan, memakai rumus yang sama dengan dokumennya. */
  private nilaiTagihan(x: any): number {
    const dpp = Number(x?.dpp || 0);
    return (
      dpp +
      (Number(x?.ppn || 0) * dpp) / 100 +
      Number(x?.pbbkb || 0) +
      Number(x?.otherValue || 0) -
      (Number(x?.pphPercentage || 0) * dpp) / 100
    );
  }

  get totalTagihanPo(): number {
    return this.tagihanPo.reduce((a, x) => a + this.nilaiTagihan(x), 0);
  }

  /** Sisa nilai PO yang belum tertagih; negatif berarti sudah melampaui. */
  get sisaPo(): number {
    return this.nilaiPo - this.totalTagihanPo;
  }

  /**
   * Tagihan yang sedang diisi membuat totalnya MELAMPAUI nilai PO.
   *
   * Diperingatkan, bukan dicegah: adendum dan pekerjaan tambahan memang
   * dapat melebihi, dan menolaknya justru menghalangi hal yang sah. Yang
   * dijaga hanya agar tidak terjadi tanpa disadari.
   */
  get melampauiPo(): boolean {
    if (!this.nilaiPo) return false;
    return this.totalTagihanPo + this.nilaiTagihanKini > this.nilaiPo + 5;
  }

  /**
   * Nilai tagihan yang SEDANG diisi, dengan rumus yang sama seperti tagihan
   * lain.
   *
   * Sebelumnya dipakai kolom `total`, dan itu membandingkan dua besaran yang
   * berbeda: `nilaiTagihan()` mengurangkan PPh, `total` tidak. Pada pembelian
   * jasa selisihnya sebesar potongan PPh — cukup untuk memunculkan peringatan
   * melampaui pada tagihan yang sebenarnya masih di bawah nilai purchase
   * order, atau sebaliknya menahannya pada tagihan yang sudah melampaui.
   */
  private get nilaiTagihanKini(): number {
    const v = this.valueFormGroup?.getRawValue?.() ?? {};
    return this.nilaiTagihan({
      dpp: v.dpp,
      ppn: v.ppn,
      pbbkb: v.pbbkb,
      otherValue: v.otherValue,
      pphPercentage: v.pphPercentage,
    });
  }

  /**
   * Tarif PPN dari purchase order, dipetakan ke nilai kartu pilihannya.
   *
   * Kartunya membandingkan dengan `===` terhadap nilai bertipe teks ('11',
   * '1.1', '0'), sedangkan kolom `ppn` di basis data DECIMAL — jawabannya
   * sampai sebagai angka. `11 === '11'` bernilai salah, sehingga sesudah
   * memilih purchase order tidak ada satu pun kartu yang tersorot dan
   * tarifnya tampak belum terisi, padahal sudah.
   */
  private tarifPpnSebagaiPilihan(tarif: unknown): string {
    const angka = Number(tarif);
    if (isNaN(angka)) return '';
    const cocok = this.pilihanPpn.find(
      (o) => Number(o.value) === angka,
    );
    // Tarif di luar ketiga pilihan tetap dipasang apa adanya: menolaknya akan
    // mengosongkan nilai yang sah pada dokumen lama.
    return cocok ? String(cocok.value) : String(angka);
  }

  /**
   * Id purchase order yang sedang dirujuk.
   *
   * Disimpan terpisah dari nomornya karena rute yang memuat satu dokumen
   * menerima id. Dikosongkan seketika ketika nomornya berubah — yang
   * tersimpan di sini belum tentu dokumen yang sedang ditulis nomornya, dan
   * membuka yang keliru lebih menyesatkan daripada tidak membuka apa pun —
   * lalu diisi kembali oleh `selaraskanDenganPoTertulis` bila nomor yang
   * diketik ternyata memang ada.
   */
  poTerpilihId: number | null = null;

  /**
   * Nomor dokumen yang id-nya tersimpan di atas.
   *
   * Dipakai membedakan perubahan nomor yang datang DARI pemilihan — yang
   * memang menyertakan id — dengan yang diketik tangan. Tanpa pembanding ini,
   * `patchValue` dari pemilihannya sendiri ikut memicu pengosongan, dan
   * tombol lihat mati tepat setelah dokumennya dipilih.
   */
  private poTerpilihNomor = '';

  /**
   * Jenis pembelian, disimpulkan dari nomor dokumennya.
   *
   * Aturannya sudah pasti dan tidak perlu ditanyakan: PO menyertai barang,
   * SPK dan PKS menyertai pekerjaan. Menanyakannya kembali kepada yang
   * mengisi hanya menambah satu kesempatan untuk salah — dan salahnya tidak
   * terlihat sampai PPh-nya tidak dipotong.
   *
   * Mengembalikan '' bila nomornya belum mengandung salah satu penanda,
   * sehingga pilihan yang sudah ada tidak dihapus oleh nomor setengah jadi.
   */
  private jenisDokumenDariNomor(nomor: unknown): string {
    const teks = String(nomor || '').toUpperCase();
    if (teks.includes('-PO-')) return 'goods';
    if (teks.includes('-SPK-') || teks.includes('-PKS-')) return 'other';
    return '';
  }

  private terapkanJenisDariNomor(nomor: unknown): void {
    const jenis = this.jenisDokumenDariNomor(nomor);
    if (!jenis) return;
    if (this.metaFormGroup.controls['documentType'].value === jenis) return;
    this.metaFormGroup.controls['documentType'].setValue(jenis);
  }

  /**
   * Buka isi purchase order yang dirujuk, untuk dibandingkan dengan faktur.
   *
   * Tersedia begitu dokumennya dikenali — baik lewat pencarian maupun lewat
   * nomor yang diketik dan ternyata ada.
   */
  lihatPurchaseOrder(): void {
    if (!this.poTerpilihId) return;
    this.dialog.open(PurchaseOrderRingkasComponent, {
      data: { id: this.poTerpilihId },
      maxWidth: '96vw',
      autoFocus: false,
    });
  }

  bukaPemilihPO(): void {
    this.dialog
      .open(PurchaseOrderPickerComponent, {
        maxWidth: '96vw',
        autoFocus: false,
      })
      .afterClosed()
      .subscribe((po: any) => {
        if (!po) return;

        // Riwayat tagihan atas PO ini dimuat bersamaan; tanpa itu
        // bandingannya baru muncul setelah nilainya terlanjur diisi.
        this.muatTagihanPo(po.purchaseOrderName);
        this.nilaiPo = this.nilaiTagihan(po);
        this.poTerpilihId = po.id ?? null;
        this.poTerpilihNomor = String(po.purchaseOrderName || '');

        this.metaFormGroup.patchValue({
          purchaseOrderName: po.purchaseOrderName,
          supplierID: po.supplierID,
          supplierName: po.supplierName,
          supplierAddress: po.supplierAddress,
          projectName: po.projectName,
          purchaseType: po.purchaseType,
        });

        // Pemasok yang terbawa dari purchase order tetap perlu rekening yang
        // biasa dipakai; jalur pencarian pemasok biasa sudah memuatnya.
        if (po.supplierID) {
          this.fetchFrequentPaymentBySupplierID(po.supplierID);
        }

        this.valueFormGroup.patchValue({
          dpp: po.dpp,
          ppn: this.tarifPpnSebagaiPilihan(po.ppn),
          pphCode: po.pphCode,
          pphTaxObject: po.pphTaxObject,
          pphPercentage: po.pphPercentage,
        });

        /*
         * Jenis pembelian ditetapkan SESUDAH nilainya dipasang, bukan
         * sebelum.
         *
         * Jenis "barang" memicu pengosongan PPh lewat langganan
         * `documentType`. Bila dijalankan lebih dulu, PPh dari purchase
         * order-nya dipasang kembali sesudah dikosongkan — dan karena
         * isiannya memang disembunyikan pada pembelian barang, potongan itu
         * tetap ikut mengurangi nilai pembayaran tanpa terlihat siapa pun.
         *
         * Urutan ini juga yang membuat `isFinal` berakhir `false`, sehingga
         * tombol hitung tetap dapat ditekan.
         */
        this.terapkanJenisDariNomor(po.purchaseOrderName);

        // Nilai turunan dihitung ulang dari yang baru dipasang; tanpa ini
        // total dan nilai pembayaran masih memakai angka sebelumnya.
        this.calculateTotal();
      });
  }

  openSupplierSelector() {
    this.dialog
      .open(SupplierSelectorComponent, {
        minWidth: '400px',
      })
      .afterClosed()
      .subscribe((data) => {
        if (data) {
          this.metaFormGroup.patchValue({
            supplierID: data.id,
            supplierName: data.name,
            supplierAddress: data.address,
          });

          this.fetchFrequentPaymentBySupplierID(data.id);
        }
      });
  }

  openPPHSelector() {
    const documentType = this.metaFormGroup.value['documentType'];
    if (documentType == 'other') {
      this.dialog
        .open(PphSelectorComponent, {})
        .afterClosed()
        .subscribe((data) => {
          /*
           * "Tanpa PPh" MENGHAPUS pilihan, berbeda dari membatalkan.
           *
           * Keduanya sempat sama-sama menutup tanpa nilai, sehingga cabang di
           * bawah tidak berjalan dan PPh yang sudah terlanjur dipilih tidak
           * pernah hilang.
           */
          if (data?.hapus) {
            this.valueFormGroup.patchValue({
              pphCode: '',
              pphTaxObject: '',
              pphPercentage: 0,
            });
            return;
          }
          if (data) {
            const pph = data as IPPh;
            this.valueFormGroup.patchValue({
              pphCode: pph.code,
              pphTaxObject: pph.taxObjectName,
              pphPercentage: pph.tariff,
            });

            const pphPercentage =
              this.valueFormGroup.controls['pphPercentage'].value;
            const dpp = this.valueFormGroup.controls['dpp'].value;
            const pphValue = (dpp * pphPercentage) / 100;
            this.valueFormGroup.controls['pphValue'].setValue(
              pphValue.toFixed(2),
            );
          } else {
            this.valueFormGroup.patchValue({
              pphCode: '',
              pphTaxObject: '',
              pphPercentage: 0,
            });
          }
        });

      this.isFinal = false;
    }
  }

  calculateTotal() {
    const dpp = Number(this.valueFormGroup.controls['dpp'].value);
    const ppn = Number(this.valueFormGroup.controls['ppn'].value);
    const pbbkb = Number(this.valueFormGroup.controls['pbbkb'].value);
    const total = dpp + (dpp * ppn) / 100 + pbbkb;
    const pph = Number(this.valueFormGroup.controls['pphPercentage'].value);
    const pphValue = (dpp * pph) / 100;
    const otherValue = Number(this.valueFormGroup.controls['otherValue'].value);

    this.valueFormGroup.patchValue({
      total: (total + otherValue).toFixed(2),
    });

    this.paymentFormGroup.patchValue({
      paymentTotal: (total + otherValue - pphValue).toFixed(2),
    });

    this.isFinal = true;
  }

  filter(): void {
    const filterValue = this.input.nativeElement.value.toLowerCase();

    // Kalau input kosong atau persis sama dengan bank yang sudah dipilih,
    // tampilkan semua bank supaya user bisa mengganti pilihan.
    const isExactSelected = this.options.some(
      (o) => o.name.toLowerCase() === filterValue,
    );
    if (!filterValue || isExactSelected) {
      this.filteredOptions = this.options.slice();
      return;
    }

    this.filteredOptions = this.options.filter(
      (option) =>
        option.name.toLowerCase().includes(filterValue) ||
        option.alias.toLowerCase().includes(filterValue),
    );
  }

  onSubmit() {
    this.isSubmitting = true;

    this.apiService
      .post(`purchases/check`, {
        invoiceName: this.metaFormGroup.controls['invoiceName'].value,
        purchaseOrderName:
          this.metaFormGroup.controls['purchaseOrderName'].value,
      })
      .subscribe({
        next: (data) => {},
        error: (error) => {
          this.snackBar.open(
          this.serverMessage.terjemahkan(error), 'Close', {
            duration: 3000,
          });
        },
      });

    const date = new Date(this.metaFormGroup.controls['date'].value);
    const dueDate = new Date(this.metaFormGroup.controls['dueDate'].value);

    const dateFormatted = `${date.getFullYear()}-${String(
      date.getMonth() + 1,
    ).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

    const dueDateFormatted = `${dueDate.getFullYear()}-${String(
      dueDate.getMonth() + 1,
    ).padStart(2, '0')}-${String(dueDate.getDate()).padStart(2, '0')}`;
    const proxyPayment = this.paymentFormGroup.controls['proxyPayment'].value;
    const paymentAmount = this.paymentFormGroup.controls['paymentTotal'].value;

    const purchaseData = {
      procurementType: this.metaFormGroup.controls['documentType'].value,
      invoiceName: this.metaFormGroup.controls['invoiceName'].value,
      receiptName: this.metaFormGroup.controls['receiptName'].value,
      taxInvoiceName:
        this.metaFormGroup.controls['taxInvoiceName'].value == ''
          ? null
          : this.metaFormGroup.controls['taxInvoiceName'].value,
      supplierID: this.metaFormGroup.controls['supplierID'].value,
      supplierName: this.metaFormGroup.controls['supplierName'].value,
      supplierAddress: this.metaFormGroup.controls['supplierAddress'].value,
      // change from date object to YYYY-MM-DD
      date: dateFormatted,
      dueDate: dueDateFormatted,
      purchaseOrderName: this.metaFormGroup.controls['purchaseOrderName'].value,
      projectName: this.metaFormGroup.controls['projectName'].value,
      purchaseType: this.metaFormGroup.controls['purchaseType'].value,
      isInternal: this.metaFormGroup.controls['isInternal'].value,
      dpp: this.valueFormGroup.controls['dpp'].value,
      ppn: this.valueFormGroup.controls['ppn'].value,
      pbbkb: this.valueFormGroup.controls['pbbkb'].value,
      pphCode:
        this.valueFormGroup.controls['pphCode'].value == ''
          ? null
          : this.valueFormGroup.controls['pphCode'].value,
      pphTaxObject:
        this.valueFormGroup.controls['pphCode'].value == ''
          ? null
          : this.valueFormGroup.controls['pphTaxObject'].value,
      pphPercentage:
        this.valueFormGroup.controls['pphCode'].value == ''
          ? 0
          : this.valueFormGroup.controls['pphPercentage'].value,
      otherValue: this.valueFormGroup.controls['otherValue'].value,
      otherValueNote:
        this.valueFormGroup.controls['otherValue'].value == 0
          ? null
          : this.valueFormGroup.controls['otherValueNote'].value,
      isInvoiceAttached:
        this.attachmentFormGroup.controls['isInvoiceAttached'].value,
      isReceiptAttached:
        this.attachmentFormGroup.controls['isReceiptAttached'].value,
      isTaxInvoiceAttached:
        this.attachmentFormGroup.controls['isTaxInvoiceAttached'].value,
      isCopAttached: this.attachmentFormGroup.controls['isCopAttached'].value,
      isCopyPurchaseOrderAttached:
        this.attachmentFormGroup.controls['isCopyPurchaseOrderAttached'].value,
      bankName: this.paymentFormGroup.controls['bankName'].value,
      bankAccountName: this.paymentFormGroup.controls['bankAccountName'].value,
      bankAccountNumber:
        this.paymentFormGroup.controls['bankAccountNumber'].value,
      paymentMethod: this.paymentFormGroup.controls['paymentMethod'].value,
      lastStatus: this.metaFormGroup.controls['lastStatus'].value,
      lastStatusDescription:
        this.metaFormGroup.controls['lastStatus'].value == 'ready'
          ? null
          : this.metaFormGroup.controls['lastStatusDescription'].value,
    };

    if (this.paymentFormGroup.controls['createPayment'].value === true) {
      this.apiService
        .post('purchases', purchaseData)
        .subscribe({
          next: (result: any) => {
            const purchaseID = result.purchase_id;

            const paymentData = {
              purchaseID: purchaseID,
              expenseID: null,
              reimbursementID: null,
              salarySlipID: null,
              date: dueDateFormatted,
              amount: this.paymentFormGroup.controls['paymentTotal'].value,
              bankAccountID:
                this.paymentFormGroup.controls['bankAccountID'].value,
              status: this.metaFormGroup.controls['lastStatus'].value,
            };

            this.apiService
              .post('outgoing-payments', paymentData)
              .subscribe({
                next: (_) => {
                  if (proxyPayment) {
                    this.generateProxyPaymentPDF({
                      ...purchaseData,
                      totalPayment: paymentAmount,
                    });
                  }

                  // PaymentSlipHelper.generatePurchasePaymentSlipPDF({
                  //   ...purchaseData,
                  //   createdAt: new Date(),
                  //   amount: paymentData.amount,
                  //   paymentDate: dueDateFormatted,
                  //   payments: [],
                  //   total: paymentData.amount,
                  //   bankNameOrigin: '',
                  //   bankAccountNameOrigin: '',
                  //   bankAccountNumberOrigin: '',
                  // });

                  this.snackBar.open(
      this.translate.instant('notify.createSuccess'), 'Close', {
                    duration: 3000,
                  });

                  this.metaFormGroup.reset({
                    invoiceName: '',
                    receiptName: '',
                    taxInvoiceName: '',
                    supplierID: '',
                    supplierName: '',
                    supplierAddress: '',
                    date: '',
                    dueDate: '',
                    purchaseOrderName: '',
                    projectName: '',
                    purchaseType: '',
                    lastStatus: 'ready',
                    lastStatusDescription: '',
                    isInternal: false,
                    // Ikut disebut: `reset()` memberi `null` kepada kendali
                    // yang tidak disebut, dan `documentType` wajib diisi.
                    documentType: '',
                  });

                  this.valueFormGroup.reset({
                    dpp: '',
                    ppn: '',
                    ppnValue: 0,
                    pbbkb: 0,
                    pphCode: '',
                    pphTaxObject: '',
                    pphPercentage: 0,
                    pphValue: 0,
                    otherValue: 0,
                    otherValueNote: '',
                    total: 0,
                  });

                  this.attachmentFormGroup.reset({
                    isInvoiceAttached: false,
                    isReceiptAttached: false,
                    isTaxInvoiceAttached: false,
                    isCopAttached: false,
                    isCopyPurchaseOrderAttached: false,
                  });

                  this.paymentFormGroup.reset({
                    bankName: '',
                    bankAccountName: '',
                    bankAccountNumber: '',
                    paymentMethod: '',
                    paymentTotal: 0,
                    proxyPayment: false,
                    /*
                     * `createPayment` dan `bankAccountID` WAJIB ikut disebut.
                     *
                     * `reset()` memberi `null` kepada setiap kolom yang tidak
                     * disebut — bukan mengembalikannya ke nilai bawaan.
                     * Akibatnya dua hal, keduanya tanpa satu pun galat yang
                     * terlihat:
                     *
                     * 1. `createPayment` menjadi `null`, sedangkan
                     *    pemeriksaannya memakai `=== true`. Pembelian
                     *    BERIKUTNYA tersimpan tanpa slip pembayaran —
                     *    padahal sakelarnya sengaja dibuat menyala sejak awal
                     *    justru agar tidak terlewat.
                     * 2. `bankAccountID` menjadi `null`, sedangkan
                     *    `bankAccountIDRequired()` memanggil `.toString()`
                     *    atas nilainya. Menyalakan kembali sakelarnya melempar
                     *    TypeError dan formulirnya berhenti di situ.
                     */
                    createPayment: true,
                    bankAccountID: '',
                  });

    /*
     * Digulir ke ATAS, bukan dikembalikan ke langkah pertama.
     *
     * Formulirnya kini satu halaman; yang perlu terjadi setelah tersimpan
     * adalah pandangan kembali ke awal, bukan berpindah langkah.
     */
    window.scrollTo({ top: 0, behavior: 'smooth' });
                },
                error: (error) => {
                  this.snackBar.open(
          this.serverMessage.terjemahkan(error), 'Close', {
                    duration: 3000,
                  });
                },
              })
              .add(() => {
                this.isSubmitting = false;
              });
          },
          error: (error) => {
            this.snackBar.open(
          this.serverMessage.terjemahkan(error), 'Close', {
              duration: 3000,
            });
          },
        })
        .add(() => {
          this.isSubmitting = false;
        });
    } else {
      this.apiService
        .post('purchases', purchaseData)
        .subscribe({
          next: (_) => {
            if (proxyPayment) {
              this.generateProxyPaymentPDF({
                ...purchaseData,
                totalPayment: paymentAmount,
              });
            }

            this.snackBar.open(
      this.translate.instant('notify.createSuccess'), 'Close', {
              duration: 3000,
            });

            this.metaFormGroup.reset({
              invoiceName: '',
              receiptName: '',
              taxInvoiceName: '',
              supplierID: '',
              supplierName: '',
              supplierAddress: '',
              date: '',
              dueDate: '',
              purchaseOrderName: '',
              projectName: '',
              purchaseType: '',
              lastStatus: 'ready',
              lastStatusDescription: '',
              isInternal: false,
              // Ikut disebut: `reset()` memberi `null` kepada kendali yang
              // tidak disebut, dan `documentType` wajib diisi — kartu jenis
              // pembelian berakhir tanpa satu pun yang tersorot.
              documentType: '',
            });

            this.valueFormGroup.reset({
              dpp: '',
              ppn: '',
              ppnValue: 0,
              pbbkb: 0,
              pphCode: '',
              pphTaxObject: '',
              pphPercentage: 0,
              pphValue: 0,
              otherValue: 0,
              otherValueNote: '',
              total: 0,
            });

            this.attachmentFormGroup.reset({
              isInvoiceAttached: false,
              isReceiptAttached: false,
              isTaxInvoiceAttached: false,
              isCopAttached: false,
              isCopyPurchaseOrderAttached: false,
            });

            this.paymentFormGroup.reset({
              bankName: '',
              bankAccountName: '',
              bankAccountNumber: '',
              paymentMethod: '',
              paymentTotal: 0,
              proxyPayment: false,
              // Lihat keterangan pada jalur di atas: yang tidak disebut di
              // sini menjadi `null`, bukan kembali ke bawaannya.
              createPayment: true,
              bankAccountID: '',
            });

    /*
     * Digulir ke ATAS, bukan dikembalikan ke langkah pertama.
     *
     * Formulirnya kini satu halaman; yang perlu terjadi setelah tersimpan
     * adalah pandangan kembali ke awal, bukan berpindah langkah.
     */
    window.scrollTo({ top: 0, behavior: 'smooth' });
          },
          error: (error) => {
            this.snackBar.open(
          this.serverMessage.terjemahkan(error), 'Close', {
              duration: 3000,
            });
          },
        })
        .add(() => {
          this.isSubmitting = false;
        });
    }
  }

  fetchBankAccounts() {
    this.apiService.get('banks/all', {}).subscribe({
      next: (data: any) => {
        this.bankAccounts = data;
      },
      error: (error) => {
        this.snackBar.open(
      this.translate.instant('notify.loadFailed'), 'Close', {
          duration: 3000,
        });
      },
    });
  }

  fetchFrequentPaymentBySupplierID(id: number) {
    this.apiService.get('purchases/frequent-payment/' + id, {}).subscribe({
      next: (data: any) => {
        if (data != null) {
          this.paymentFormGroup.patchValue({
            bankName: data.bankName,
            bankAccountName: data.bankAccountName,
            bankAccountNumber: data.bankAccountNumber,
          });
        }
      },
    });
  }

  generateProxyPaymentPDF(data: any) {
    ProxyPaymentHelper.createProxyPaymentPDF({
      invoiceName: data.invoiceName,
      taxInvoiceName: data.taxInvoiceName,
      supplierName: data.supplierName,
      bankName: data.bankName,
      bankAccountNumber: data.bankAccountNumber,
      bankAccountName: data.bankAccountName,
      totalPayment: data.totalPayment,
      date: new Date(data.date),
    });
  }

  copyBankAccountNumber() {
    this.clipboard.copy(this.paymentFormGroup.get('bankAccountNumber')!.value);
    this.snackBar.open(
      this.translate.instant('notify.copied'), 'Close', {
      duration: 3000,
    });
  }

  get isValid() {
    return (
      this.metaFormGroup.valid &&
      this.valueFormGroup.valid &&
      this.attachmentFormGroup.valid &&
      this.paymentFormGroup.valid
    );
  }
}
