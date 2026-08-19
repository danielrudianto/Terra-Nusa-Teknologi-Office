import { CommonModule } from '@angular/common';
import { CanDirective } from '../../../directives/can.directive';
import { konteksKlausulTenagaKerja } from '../../../helpers/klausul-tenaga-kerja.helper';
import { namaPemasokBaris } from '../../../helpers/purchase-order-shared.helper';
import { Component } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatMenuModule } from '@angular/material/menu';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ActivatedRoute, Router } from '@angular/router';
import { debounceTime } from 'rxjs';
import { DeleteConfirmationComponent } from '../../../components/delete-confirmation/delete-confirmation.component';
import { HeaderTitleComponent } from '../../../components/header-title/header-title.component';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { ApiService } from '../../../services/api.service';
import { purchaseTypeLabel } from '../../../constants/purchase-type-label.constant';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { printPurchaseOrderG } from '../../../helpers/purchase-order-g.helper';
import { printPurchaseOrderC } from '../../../helpers/purchase-order-c.helper';
import { printPurchaseOrderD } from '../../../helpers/purchase-order-d.helper';
import {
  printPurchaseOrderB,
  perluasItemMobilisasi,
} from '../../../helpers/purchase-order-b.helper';
import { printPurchaseOrderH } from '../../../helpers/purchase-order-h.helper';
import { PurchaseOrderViewComponent } from '../purchase-order-view/purchase-order-view.component';
import { PurchaseOrderTypeSelectorComponent } from '../purchase-order-type-selector/purchase-order-type-selector.component';
import {
  buildBuangLumpurClauses,
  buildClauseLines,
  buildGroutingClauses,
  buildMandorClauses,
  buildEquipmentRentalBillingTerms,
  buildTransportRentalBillingTerms,
  buildLegalServiceBillingTerms,
  buildInsuranceClauses,
  buildTrainingClauses,
  buildLegalServiceClauses,
  buildMaintenanceBillingTerms,
  buildPasal5,
  buildTransportBillingTerms,
  buildTransportClauses,
  transportUsesRentalLayout,
} from '../../../constants/clause-templates';
import { isTempoTerm } from '../../../helpers/purchase-order-shared.helper';
import { printPurchaseOrderA } from '../../../helpers/purchase-order-a.helper';
import { cetakRantaiPurchaseOrder } from '../../../helpers/purchase-order-rantai.helper';
import { PdfOutput } from '../../../helpers/purchase-order-shared.helper';
import { printPurchaseOrder641 } from '../../../helpers/purchase-order-641.helper';
import { FLEET_ID_MODE, FLEET_OPTIONS } from '../../../constants/fleet';
import { SettingsService } from '../../../services/setting.service';
import { ServerMessageService } from '../../../services/server-message.service';
import { RefreshButtonComponent } from '../../../components/refresh-button/refresh-button.component';
import { PurchaseOrderRekapComponent } from '../purchase-order-rekap/purchase-order-rekap.component';
import { PurchaseOrderFilterComponent } from './purchase-order-filter/purchase-order-filter.component';

@Component({
  selector: 'app-purchase-order-list',
  standalone: true,
  imports: [
    CanDirective,
    MatProgressSpinnerModule,
    CommonModule,
    ReactiveFormsModule,
    MatTableModule,
    MatFormFieldModule,
    MatInputModule,
    MatIconModule,
    MatMenuModule,
    MatPaginatorModule,
    MatButtonModule,
    MatProgressBarModule,
    MatSnackBarModule,
    MatTooltipModule,
    HeaderTitleComponent,
    TranslatePipe,
    RefreshButtonComponent,
  ],
  templateUrl: './purchase-order-list.component.html',
  styleUrl: './purchase-order-list.component.scss',
})
export class PurchaseOrderListComponent {
  /**
   * Status yang ditampilkan. PO terhapus ditandai lewat `isDelete`,
   * bukan kolom status, sehingga perlu diperiksa terpisah.
   */
  displayStatus(po: any): string {
    if (po?.isDelete) return 'deleted';
    if (po?.isApproved) return 'approved';
    return po?.status || 'draft';
  }

  /** i18n key untuk status PO. */
  statusKey(status: string): string {
    switch (status) {
      case 'approved':
        return 'status.approved';
      case 'cancelled':
        return 'status.cancelled';
      case 'pending':
        return 'status.pending';
      case 'published':
        return 'status.published';
      case 'deleted':
        return 'status.deleted';
      case 'draft':
      default:
        return 'status.draft';
    }
  }

  constructor(
    public settings: SettingsService,
    private router: Router,
    private route: ActivatedRoute,
    private apiService: ApiService,
    private dialog: MatDialog,
    private snackBar: MatSnackBar,
    private translate: TranslateService,
    private serverMessage: ServerMessageService,
  ) {}

  isLoading: boolean = false;
  isReprinting: number | null = null;
  searchControl: FormControl = new FormControl('');
  orders: any[] = [];
  /** Kolom & arah pengurutan; penamaannya mengikuti halaman Pembelian. */
  sortBy: string = 'date';
  sortByDirection: 'asc' | 'desc' = 'desc';
  page: number = 1;
  /** Nilai awal dari pengaturan pengguna; tetap bisa diubah per halaman. */
  pageSize: number = this.settings.pageSize;
  count: number = 0;
  displayedColumns: string[] = [
    'name',
    'date',
    'supplier',
    'project',
    'type',
    'total',
    'status',
    'action',
  ];

  /**
   * Ganti kolom pengurut; mengklik kolom yang sama membalik arahnya.
   * Pengurutan dilakukan di server supaya mencakup seluruh data.
   */
  changeSortBy(sortBy: string) {
    if (this.sortBy === sortBy) {
      this.sortByDirection = this.sortByDirection === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortBy = sortBy;
      this.sortByDirection = 'asc';
    }

    this.fetch(1);
  }

  ngOnInit(): void {
    // Cetak otomatis bila datang dari formulir adendum.
    this.cetakDariAlamat();
    this.fetch();
    this.searchControl.valueChanges.pipe(debounceTime(400)).subscribe(() => {
      this.fetch(1);
    });
  }

  /*
   * Keadaan penyaring.
   *
   * Disimpan di komponen, bukan di dalam dialog: dialog dibuang setiap kali
   * ditutup, dan penyaring yang ikut hilang berarti yang membukanya lagi
   * harus mengisi ulang seluruhnya.
   */
  filterStatus = '';
  filterTipe: string[] = [];
  filterProyek = '';
  filterDari: Date | null = null;
  filterSampai: Date | null = null;

  /** Kode proyek untuk pilihan; diambil dari daftar yang sedang tampil. */
  proyekOptions: string[] = [];

  /**
   * Berapa penyaring yang sedang aktif.
   *
   * Ditampilkan sebagai lencana pada tombolnya — tanpa itu, daftar yang
   * tersaring tampak seperti daftar yang kosong, dan yang melihatnya
   * menyimpulkan datanya hilang.
   */
  activeFilterCount(): number {
    let n = 0;
    if (this.filterStatus) n++;
    if (this.filterTipe.length) n++;
    if (this.filterProyek) n++;
    if (this.filterDari || this.filterSampai) n++;
    return n;
  }

  openFilter(): void {
    this.dialog
      .open(PurchaseOrderFilterComponent, {
        width: '460px',
        maxWidth: '92vw',
        autoFocus: false,
        data: {
          projects: this.proyekOptions,
          status: this.filterStatus,
          purchaseType: this.filterTipe,
          projectName: this.filterProyek,
          dateFrom: this.filterDari,
          dateTo: this.filterSampai,
        },
      })
      .afterClosed()
      .subscribe((hasil) => {
        if (!hasil) return;
        this.filterStatus = hasil.status;
        this.filterTipe = hasil.purchaseType;
        this.filterProyek = hasil.projectName;
        this.filterDari = hasil.dateFrom;
        this.filterSampai = hasil.dateTo;

        // Kembali ke halaman satu.
        //
        // Penyaring baru menghasilkan daftar yang berbeda, dan halaman lima
        // dari daftar itu kerap tidak ada — sehingga yang tampil justru
        // kosong.
        this.fetch(1);
      });
  }

  bersihkanFilter(): void {
    this.filterStatus = '';
    this.filterTipe = [];
    this.filterProyek = '';
    this.filterDari = null;
    this.filterSampai = null;
    this.fetch(1);
  }

  /** Tanggal untuk server: YYYY-MM-DD waktu setempat. */
  private tglParam(d: Date | null): string {
    if (!d) return '';
    const p = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  }

  fetch(targetPage: number = 1) {
    this.isLoading = true;
    this.page = targetPage;
    this.apiService
      .get('purchase-orders', {
        keyword: this.searchControl.value || '',
        page: this.page,
        page_size: this.pageSize,
        sortBy: this.sortBy,
        sortByDirection: this.sortByDirection,

        // Penyaring dikirim sebagai teks kosong bila tidak dipakai; server
        // mengabaikan yang kosong dan tidak menambah kondisi apa pun.
        status: this.filterStatus,
        purchase_type: this.filterTipe.join(','),
        project_name: this.filterProyek,
        date_from: this.tglParam(this.filterDari),
        date_to: this.tglParam(this.filterSampai),
      })
      .subscribe({
        next: (res: any) => {
          this.orders = res.data || [];
          this.count = res.count || 0;

          /*
           * Kode proyek dikumpulkan dari daftar yang tampil.
           *
           * Bukan dari seluruh proyek yang pernah ada: sebagian sudah selesai
           * bertahun lalu dan tidak akan pernah dicari lagi, sementara
           * daftar pilihan yang panjang justru menyulitkan menemukan yang
           * sedang berjalan.
           */
          const proyek = new Set(this.proyekOptions);
          for (const o of this.orders) {
            if (o?.projectName) proyek.add(o.projectName);
          }
          this.proyekOptions = [...proyek].sort();
        },
        error: (err) => {
          this.snackBar.open(
            this.serverMessage.terjemahkan(err, 'notify.loadFailed'),
            'Close',
            { duration: 3000 },
          );
        },
      })
      .add(() => {
        this.isLoading = false;
      });
  }

  changePage(event: PageEvent) {
    this.pageSize = event.pageSize;
    this.fetch(event.pageIndex + 1);
  }

  /**
   * Nama pemasok pada satu baris daftar.
   *
   * Nama bidangnya dibaca `namaPemasokBaris`, satu-satunya tempat yang
   * mengetahuinya. Sebelumnya fungsi ini menyusunnya sendiri dari
   * `supplier_prefix`/`supplier_name` sementara templat di sebelahnya membaca
   * `supplierName` — dua bentuk berbeda untuk satu hal, di dalam satu berkas
   * yang sama. Ketika kueri backend berganti bentuk, satu ikut dan satu
   * tertinggal, dan yang tertinggal berubah menjadi "—" tanpa galat.
   */
  supplierLabel(po: any): string {
    const hasil = namaPemasokBaris(po);
    return hasil === '-' ? '—' : hasil;
  }

  /**
   * Huruf pertama nama pemasok, untuk lencana bundar di sebelah kiri baris.
   *
   * Diambil dari nama yang SUDAH disusun, bukan dari bidangnya langsung —
   * kalau tidak, lencananya bisa menunjukkan "?" sementara namanya di
   * sebelahnya terbaca dengan benar, atau sebaliknya.
   */
  inisialPemasok(po: any): string {
    const nama = this.supplierLabel(po);
    return nama === '—' ? '?' : nama.charAt(0).toUpperCase();
  }

  /**
   * Nama jenis PO diambil dari berkas terjemahan; peta lama dipakai sebagai
   * cadangan bila kodenya belum punya terjemahan.
   *
   * Seluruh logikanya ada di `purchaseTypeLabel` — termasuk pemeriksaan
   * "kunci tidak ditemukan" yang sebelumnya ditulis ulang di sini.
   */
  typeLabel(code: string): string {
    return purchaseTypeLabel(this.translate, code);
  }

  total(po: any): number {
    const dpp = Number(po.dpp) || 0;
    const ppn = Number(po.ppn) || 0;
    return dpp + (dpp * ppn) / 100;
  }

  createNewPurchaseOrder() {
    this.openTypeSelector();
  }

  /** Tipe PO yang sudah punya template cetak. */
  // PO-H disimpan sebagai 'H1' (badan usaha) atau 'H2' (perorangan),
  // bukan 'H' — keduanya memakai dokumen dan helper yang sama.
  private readonly printableTypes = [
    'A',
    '5.1.2',
    '6.3.1',
    '6.3.2',
    '6.4.1',
    '6.4.2',
    '6.5.1',
    '6.5.2',
    'G',
    'C',
    'D',
    'F',
    'B',
    'H',
    'H1',
    'H2',
    '5.1.1',
    '5.1.12',
    '5.1.6',
  ];

  /**
   * Dokumen ini berasal dari formulir sewa alat (PO-B).
   *
   * PO-B dapat diterbitkan sebagai tipe A, sehingga kode jenisnya tidak bisa
   * dipakai untuk menentukan bentuk dokumennya. Yang menentukan adalah
   * penanda `formOrigin`; PO lama yang belum menyimpannya dikenali dari
   * kolom sewa yang hanya ada pada formulir B.
   */
  private dariFormB(po: any, custom: any): boolean {
    if (custom?.formOrigin) return custom.formOrigin === 'B';
    if (po?.purchaseType === 'B') return true;
    // PO-B lama: hanya formulir sewa yang menyimpan hal-hal ini.
    return (
      custom?.equipmentRiskBearer !== undefined ||
      custom?.operatorByVendor !== undefined ||
      custom?.quotaPeriodDays !== undefined
    );
  }

  /** Keterangan tanggal dan lembaga penerbit untuk satu baris pelatihan. */
  private periodeLembaga(it: any): string {
    const bagian: string[] = [];
    const mulai = this.tanggalPanjang(it.remarks_1);
    const selesai = this.tanggalPanjang(it.remarks_2);
    if (mulai && selesai) bagian.push(`${mulai} s/d ${selesai}`);
    else if (mulai) bagian.push(mulai);
    if (it.remarks_3) bagian.push(String(it.remarks_3));
    return bagian.join(' · ');
  }

  /** Keterangan periode dan lokasi untuk satu baris sewa alat. */
  private periodeLokasiSewa(it: any): string {
    const bagian: string[] = [];
    const mulai = this.tanggalPanjang(it.remarks_1);
    const selesai = this.tanggalPanjang(it.remarks_2);
    if (mulai && selesai) bagian.push(`${mulai} s/d ${selesai}`);
    else if (mulai) bagian.push(`Mulai ${mulai}`);
    if (it.remarks_3) bagian.push(String(it.remarks_3));
    return bagian.join(' · ');
  }

  /** Tanggal dalam penulisan panjang, mis. "1 September 2026". */
  private tanggalPanjang(nilai: any): string {
    if (!nilai) return '';
    const d = new Date(nilai);
    return isNaN(d.getTime())
      ? ''
      : d.toLocaleDateString('id-ID', {
          day: 'numeric',
          month: 'long',
          year: 'numeric',
        });
  }

  canReprint(po: any): boolean {
    if (!this.printableTypes.includes(po?.purchaseType)) return false;

    /*
     * SPK pekerjaan yang datanya berasal dari jenis PO lain tidak dapat
     * dicetak ulang.
     *
     * Sebagian PO tipe H dulu dibuat lewat formulir jenis lain lalu
     * direklasifikasi, sehingga `customData`-nya tidak memuat `workScope`
     * maupun rincian pasal yang dibutuhkan template ini. Dokumennya tetap
     * keluar, tetapi tanpa satu pun pasal — dan dokumen kosong yang
     * terlihat resmi lebih berbahaya daripada tidak ada tombolnya.
     *
     * Dokumen aslinya tetap tersimpan sebagai arsip; yang ditutup hanya
     * pembuatan ulangnya.
     */
    if (String(po.purchaseType || '').startsWith('H')) {
      let custom: any = {};
      try {
        custom =
          typeof po.customData === 'string'
            ? JSON.parse(po.customData)
            : po.customData || {};
      } catch {
        custom = {};
      }
      if (!custom.workScope) return false;
    }

    return true;
  }

  /**
   * Cetak ulang dokumen PO. Data diambil ulang dari server, dan poin
   * perjanjian dirakit dari template + templateVersion PO tersebut —
   * bukan dari teks tersimpan — sehingga hasilnya konsisten dengan datanya.
   */

  /** Buka detail PO: tampilan rapi atau data mentah. */
  /**
   * Dokumen ini sudah selesai — tidak boleh disetujui, ditolak, atau
   * dihapus lagi.
   *
   * Memeriksa DUA bidang, bukan satu. Sebagian dokumen tersimpan dengan
   * `status: "approved"` sementara `isApproved` masih `false`; memeriksa
   * salah satu saja membuat tombol Setujui tetap hidup pada dokumen yang
   * sudah disetujui.
   *
   * Menyetujui ulang menimpa `approvedBy` dan `approvedAt`, sehingga jejak
   * siapa yang benar-benar menyetujuinya hilang — padahal blok tanda tangan
   * pada lembar yang dipegang vendor memuat nama penyetuju pertama.
   */
  sudahSelesai(po: any): boolean {
    return (
      !!po?.isApproved ||
      po?.status === 'approved' ||
      po?.status === 'cancelled'
    );
  }

  viewOrder(po: any) {
    // Dialognya menangani sendiri bila penggunanya memilih membuat adendum:
    // ia dibuka dari tiga tempat, dan menaruh penanganannya di sini berarti
    // ketiganya harus menyalin hal yang sama.
    this.dialog.open(PurchaseOrderViewComponent, {
      data: { id: po.id },
      maxWidth: '94vw',
      autoFocus: false,
    });
  }

  /**
   * Cetak otomatis setelah adendum terbit.
   *
   * Formulir pembuatan mengarah ke sini dengan `?cetak={id}` alih-alih
   * mencetak sendiri: cetakan adendum wajib menyertakan induk dan adendum
   * sebelumnya, dan yang menyusun rantainya hanya ada di halaman ini.
   * Mengulanginya di enam belas formulir berarti enam belas salinan yang
   * harus diperbaiki bersamaan.
   *
   * Parameternya DIBERSIHKAN setelah dipakai; tanpa itu, memuat ulang
   * halaman mencetak dokumen yang sama berulang kali.
   */
  private cetakDariAlamat(): void {
    const v = this.route.snapshot.queryParamMap.get('cetak');
    const id = Number(v);
    if (!v || isNaN(id) || !id) return;

    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { cetak: null },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });

    this.apiService.get(`purchase-orders/${id}`, {}).subscribe({
      next: (po: any) => {
        if (po) this.reprint(po);
      },
      error: () => {},
    });
  }

  /**
   * Buka dialog rekap Excel.
   *
   * Proyeknya dipilih di dalam dialog, bukan diambil dari penyaring yang
   * sedang aktif: rekap ini dikirim ke luar, dan menerbitkannya dari keadaan
   * layar yang kebetulan tersaring menghasilkan berkas yang isinya tidak
   * sesuai judulnya.
   */
  bukaRekap(): void {
    this.dialog.open(PurchaseOrderRekapComponent, {
      autoFocus: false,
      maxWidth: '96vw',
    });
  }

  reprint(po: any) {
    if (!this.canReprint(po)) return;
    this.isReprinting = po.id;

    /*
     * Mencetak adendum menyertakan SELURUH yang mendahuluinya.
     *
     * Adendum berisi selisih; dibaca sendirian ia tidak menyatakan keadaan
     * pekerjaannya. Vendor yang menerima `ADD2` saja tidak dapat mengetahui
     * volume yang berlaku.
     *
     * Adendum SESUDAHNYA tidak ikut — lembar yang sudah ditandatangani tidak
     * boleh berubah isinya karena ada adendum baru.
     */
    this.apiService.get(`purchase-orders/${po.id}/rantai`, {}).subscribe({
      next: (rantai: any) => {
        try {
          const daftar: any[] = Array.isArray(rantai) ? rantai : [];
          if (!daftar.length) {
            this.isReprinting = null;
            return;
          }

          if (daftar.length === 1) {
            this.susunDokumen(daftar[0], 'open');
          } else {
            const definisi = daftar
              .map((d) => this.susunDokumen(d, 'docdef'))
              .filter(Boolean);
            cetakRantaiPurchaseOrder(definisi, po.name || 'purchase-order');
          }
          this.isReprinting = null;
        } catch {
          this.gagalCetak();
        }
      },
      error: () => this.gagalCetak(),
    });
  }

  private gagalCetak(): void {
    this.isReprinting = null;
    this.snackBar.open(this.translate.instant('notify.actionFailed'), 'Close', {
      duration: 4000,
    });
  }

  /**
   * Susun dokumen cetak untuk SATU purchase order.
   *
   * Dipisah dari `reprint` agar dapat dipanggil berulang: mencetak adendum
   * menyertakan induk dan adendum sebelumnya, dan ketiganya harus disusun
   * dengan aturan yang sama persis. Menyalin logikanya berarti dua salinan
   * yang harus diperbaiki bersamaan — dan yang terlupa tidak menimbulkan
   * galat, hanya dokumen yang diam-diam berbeda.
   *
   * `output` diteruskan ke helper cetaknya. Dengan `'docdef'`, yang
   * dikembalikan definisi dokumennya — bukan PDF — sehingga beberapa dokumen
   * dapat digabung menjadi satu berkas.
   */
  private susunDokumen(data: any, output: PdfOutput = 'open'): any {
    /*
     * Penanda adendum diteruskan ke helper cetaknya.
     *
     * Mengubah dua hal pada lembarnya: kalimat pembukanya, dan judul kolom
     * volume — pada adendum yang dicantumkan SELISIH, bukan volume yang
     * berlaku. Tanpa penanda ini, vendor membaca angkanya sebagai volume
     * total lalu menagih dua kali.
     */
    const isAdendum = !!data?.parentPurchaseOrderID;

    /*
     * Keadaan persetujuan diteruskan agar cap DRAFT muncul pada dokumen yang
     * belum disahkan.
     *
     * Tanpa cap itu, lembar draf tidak dapat dibedakan dari yang sah begitu
     * keluar dari pencetak — bentuknya sama persis, lengkap dengan blok
     * tanda tangan.
     */
    const isApproved = !!data?.isApproved;
    const status = data?.status;

      const custom = data.customData || {};
      try {
        const printData = {
      // Keadaan persetujuan dan penanda adendum diteruskan lewat
      // muatan bersama ini; enam titik cetak memakainya alih-alih
      // objek literal, sehingga tanpa ini capnya tidak pernah muncul.
      isApproved,
      status,
      isAdendum,
          poType: data.purchaseType,
          purchaseOrderName: data.name,
          // Nama penyetuju; kosong selama dokumennya belum disetujui,
          // sehingga blok tanda tangan tidak menyebut siapa pun.
          approvedByName: data.approvedByName ?? null,
          approvedByPosition: data.approvedByPosition ?? null,
          // Keterangan penelusuran di bawah blok tanda tangan.
          //
          // Bukan pengganti tanda tangan basah; nilainya agar dokumen yang
          // beredar dapat ditelusuri tanpa membuka sistem.
          approvedAt: data.approvedAt ?? null,
          checkedByName: data.checkedByName ?? null,
          date: data.date,
          projectName: data.projectName,
          supplierName: data.supplierName ?? '',
          supplierPrefix: data.supplierPrefix ?? '',
          supplierAddress: data.supplierAddress ?? '',
          supplierCity: data.supplierCity ?? '',
          supplierNpwp: data.supplierNpwp ?? '',
          items: (data.items || []).map((it: any) => ({
            // Nama barang berasal dari join master_item
            // (item_description); `task` dipakai PO jasa/tenaga kerja.
            // item_description = barang katalog, equipment_name = alat
            // sewa (PO B), task = PO jasa/tenaga kerja.
            name:
              it.item_description ||
              it.equipment_name ||
              it.task ||
              it.sku ||
              '',
            // Catatan per baris disimpan pada kolom remarks_1.
            remarks: it.remarks_1 || '',
            quantity: Number(it.quantity) || 0,
            unit: it.unit,
            price: Number(it.price) || 0,
          })),
          includePpn: Number(data.ppn) > 0,
          templateVersion: data.templateVersion,
          clauseContext: {
            paymentTerm: custom.paymentTerm ?? data.payment_term,
            creditTerm: custom.creditTerm,
            prepaidTerm: custom.prepaidTerm,
            deliveryMethod: custom.deliveryMethod,
            deliveryAddress: custom.deliveryAddress,
            supplierPICName: custom.supplierPICName,
            supplierPICPhoneNumber: custom.supplierPICPhoneNumber,
            officePICName: custom.officePICName,
            officePICPhoneNumber: custom.officePICPhoneNumber,
            fuelReportRequired: custom.fuelReportRequired,
            materialType: custom.materialType,
            deliveryDate: custom.deliveryDate,
            /*
             * Informasi umum PO-D: lokasi kerja dan jangka waktu.
             * Tanggal disimpan dalam bentuk ISO, sehingga perlu
             * diformat ulang agar terbaca wajar di dokumen.
             */
            workLocation: custom.workLocation,
            projectName: data.projectName,
            contractStartText: this.tanggalPanjang(custom.contractStart),
            contractEndText: this.tanggalPanjang(custom.contractEnd),
            contractUntilProjectDone: !!custom.contractUntilProjectDone,
          },
          additionalClauses: custom.additionalClauses || [],
        };

        if (String(data.purchaseType || '').startsWith('H')) {
          // SPK pekerjaan: bentuk dokumen mengikuti jenis pekerjaannya.
          const scope = custom.workScope || 'borongan';
          const ringkas = scope !== 'borongan';
          return printPurchaseOrderH({
            purchaseOrderName: data.name,
            date: data.date,
            projectName: data.projectName,
            supplierName: data.supplierName ?? '',
            supplierPrefix: data.supplierPrefix ?? '',
            supplierAddress: data.supplierAddress ?? '',
            supplierCity: data.supplierCity ?? '',
            supplierNpwp: data.supplierNpwp ?? '',
            supplierPIC: custom.supplierPIC ?? '',
            pasal1: buildClauseLines('H', custom, data.templateVersion),
            scopes: (data.items || []).map((it: any) => ({
              task: it.task || it.item_description || '',
              quantity: Number(it.quantity) || 0,
              unit: it.unit,
              price: Number(it.price) || 0,
            })),
            isLumpSum: custom.rateType === 'lumpsum',
            lumpSumPrice: Number(custom.lumpSumPrice) || 0,
            includePpn: Number(data.ppn) > 0,
            kewajiban: custom.kewajiban || [],
            keterangan: custom.keterangan || [],
            pasal5: buildPasal5(custom, custom.billingDocuments),
            mode: ringkas ? 'ringkas' : 'lengkap',
            /*
             * Poin tambahan menjadi seksi tersendiri, bukan menempel di
             * ekor pasal terakhir — sama seperti saat dokumen dibuat.
             *
             * Sebelumnya poin tambahan tidak ikut tercetak sama sekali
             * pada cetak ulang: helper PO-H hanya membaca `sections`,
             * sedangkan `additionalClauses` yang dikirim tidak pernah
             * dipakainya.
             */
            sections: (() => {
              const extra: string[] = custom.additionalClauses || [];
              const base =
                scope === 'grouting'
                  ? buildGroutingClauses(custom)
                  : scope.startsWith('mandor-')
                    ? buildMandorClauses(custom, scope)
                    : undefined;
              if (!base) return undefined;
              return extra.length
                ? [...base, { title: 'Catatan Tambahan', items: extra }]
                : base;
            })(),
            catatan:
              scope === 'buang-lumpur'
                ? [
                    ...buildBuangLumpurClauses(custom),
                    ...(custom.additionalClauses || []),
                  ]
                : undefined,
            closingText:
              scope === 'buang-lumpur'
                ? undefined
                : ringkas
                  ? 'Demikian PERJANJIAN KERJA SAMA ini dibuat sesuai dengan kesepakatan bersama dan akan digunakan sebagai dasar pekerjaan dan penagihan.'
                  : undefined,
            isApproved,
            status,
            isAdendum,
            },
              output);
        } else if (data.purchaseType === 'A' && !this.dariFormB(data, custom)) {
          // Dokumen tipe A yang benar-benar jasa transportasi.
          //
          // PO-B yang diterbitkan sebagai tipe A tidak masuk ke sini:
          // isian, tabel, dan ketentuannya milik sewa alat, sehingga
          // ditangani cabang sewa di bawah.
          //
          // SPK jasa transportasi. Moda tidak disimpan sebagai kolom
          // sendiri: darat memakai fleet_id sungguhan, sedangkan udara
          // dan laut memakai id penanda (1000/1001).
          const tgl = (d: any) =>
            d
              ? new Date(d).toLocaleDateString('id-ID', {
                  weekday: 'long',
                  day: 'numeric',
                  month: 'long',
                  year: 'numeric',
                })
              : '';

          const jadwal: any[] = custom.shipmentSchedules || [];

          const shipments = (data.items || []).map((it: any, i: number) => {
            const fleetId = Number(it.fleet_id);
            const mode = FLEET_ID_MODE[fleetId] || 'darat';
            const darat = mode === 'darat';
            return {
              mode,
              from: it.remarks_1 || '',
              to: it.remarks_2 || '',
              fleetName: darat
                ? FLEET_OPTIONS.find((f) => f.id === fleetId)?.name
                : undefined,
              nopol: darat ? it.remarks_3 : undefined,
              driver: darat ? it.remarks_4 : undefined,
              provider: darat ? undefined : it.remarks_3,
              refNumber: darat ? undefined : it.remarks_4,
              picName: it.remarks_5 || '',
              picPhone: it.remarks_6 || '',
              quantity: Number(it.quantity) || 0,
              unit: it.unit,
              price: Number(it.price) || 0,
              // `task` menyimpan tanggal kirim baris ini.
              deliveryDateText: tgl(jadwal[i]?.deliveryDate || it.task),
            };
          });

          const ctx: any = {
            ...custom,
            paymentTerm: custom.paymentTerm ?? data.payment_term,
            // Moda diambil dari baris yang benar-benar tersimpan, bukan
            // dari satu moda di tingkat kontrak.
            transportModes: shipments.map((s: any) => s.mode),
            shipmentSchedules: shipments.map((s: any, i: number) => ({
              mode: s.mode,
              from: s.from,
              to: s.to,
              deliveryDateText: s.deliveryDateText,
              unloadingDateText: tgl(jadwal[i]?.unloadingDate),
              closingDateText: tgl(jadwal[i]?.closingDate),
              etdText: tgl(jadwal[i]?.etd),
              etaText: tgl(jadwal[i]?.eta),
            })),
          };

          const additional: string[] = custom.additionalClauses || [];

          if (transportUsesRentalLayout(custom.workKind)) {
            // PO lama berjenis sewa alat: dokumennya memakai tata letak
            // PO-B, sesuai templatenya waktu itu.
            return printPurchaseOrderB({
              ...printData,
              // Sama dengan jalur formulir: mobilisasi disisipkan
              // sebagai baris pekerjaan tersendiri. Ditulis lewat fungsi
              // yang sama supaya cetak ulang tidak dapat berbeda dari
              // cetakan pertamanya.
              items: perluasItemMobilisasi(
                (data.items || []).map((it: any) => ({
                  name:
                    it.equipment_name ||
                    it.item_description ||
                    it.task ||
                    '',
                  quantity: Number(it.quantity) || 0,
                  unit: it.unit,
                  price: Number(it.price) || 0,
                  remarks_4: it.remarks_4,
                  remarks_5: it.remarks_5,
                })),
              ),
              includePpn: Number(data.ppn) > 0,
              clauseContext: ctx,
              additionalClauses: additional,
            },
              output);
          } else {
            return printPurchaseOrderA({
              isApproved,
              status,
              isAdendum,
              purchaseOrderName: data.name,
              date: data.date,
              projectName: data.projectName,
              supplierName: data.supplierName ?? '',
              supplierPrefix: data.supplierPrefix ?? '',
              supplierAddress: data.supplierAddress ?? '',
              supplierCity: data.supplierCity ?? '',
              supplierNpwp: data.supplierNpwp ?? '',
              shipments,
              includePpn: Number(data.ppn) > 0,
              // PO lama tidak menyimpan tarifnya; kolom `ppn` masih
              // memuat angka tarif selama PPN-nya tidak dimatikan.
              ppnRate: Number(custom.ppnRate ?? data.ppn) || 11,
              sections: buildTransportClauses(ctx, additional),
              billingTerms: buildTransportBillingTerms(),
            },
              output);
          }
        } else if (
          data.purchaseType === '6.3.1' ||
          data.purchaseType === '6.3.2'
        ) {
          // Merchandise adalah pembelian barang (tata letak G); jasa
          // periklanan adalah pemesanan karya (tata letak SPK).
          const barang = data.purchaseType === '6.3.2';
          const data63 = {
            ...printData,
            poType: data.purchaseType,
            items: (data.items || []).map((it: any) => ({
              name: barang
                ? it.item_description || it.sku || ''
                : it.task || '',
              remarks: it.remarks_1 || '',
              quantity: Number(it.quantity) || 0,
              unit: it.unit,
              price: Number(it.price) || 0,
            })),
            includePpn: Number(data.ppn) > 0,
            clauseContext: {
              ...printData.clauseContext,
              paymentTerm: custom.paymentTerm ?? data.payment_term,
              creditTerm: custom.creditTerm,
              prepaidTerm: custom.prepaidTerm,
              revisionCount: custom.revisionCount,
              latePenaltyPermil: custom.latePenaltyPermil,
              latePenaltyCapPercent: custom.latePenaltyCapPercent,
              // PO lama tidak menyimpan field ini; true adalah perilaku
              // sebelumnya (poin ditampilkan utuh).
              sampleApprovalRequired:
                custom.sampleApprovalRequired !== false,
              // Klausul pengiriman hanya berlaku pada merchandise.
              deliveryMethod: barang ? custom.deliveryMethod : undefined,
              deliveryAddress: barang ? custom.deliveryAddress : undefined,
              supplierPICName: barang ? custom.supplierPICName : undefined,
              supplierPICPhoneNumber: barang
                ? custom.supplierPICPhoneNumber
                : undefined,
              officePICName: barang ? custom.officePICName : undefined,
              officePICPhoneNumber: barang
                ? custom.officePICPhoneNumber
                : undefined,
              pphCode: custom.pphCode,
              pphTaxObject: custom.pphTaxObject,
              pphPercentage: custom.pphPercentage,
            },
            // PO lama menyimpan catatan sebagai satu blok teks pada
            // `notes`; dipakai sebagai poin tunggal agar isinya tidak
            // hilang dari dokumen.
            additionalClauses: custom.additionalClauses?.length
              ? custom.additionalClauses
              : custom.notes
                ? [
                    String(custom.notes)
                      .replace(/<[^>]*>/g, '')
                      .trim(),
                  ]
                : [],
          };

          if (barang) {
            return printPurchaseOrderG(data63,
              output);
          } else {
            return printPurchaseOrderB(data63,
              output);
          }
        } else if (data.purchaseType === '5.1.12') {
          // Perangkat lunak & langganan: pemesanan layanan, sehingga
          // memakai tata letak Surat Perintah Kerja.
          return printPurchaseOrderB({
            ...printData,
            poType: '5.1.12',
            items: (data.items || []).map((it: any) => ({
              name: it.task || '',
              remarks: it.remarks_1 || '',
              quantity: Number(it.quantity) || 0,
              unit: it.unit,
              price: Number(it.price) || 0,
            })),
            includePpn: Number(data.ppn) > 0,
            clauseContext: {
              ...printData.clauseContext,
              paymentTerm: custom.paymentTerm ?? data.payment_term,
              creditTerm: custom.creditTerm,
              prepaidTerm: custom.prepaidTerm,
              softwareIsSubscription: custom.isSubscription !== false,
              subscriptionStartDate: this.tanggalPanjang(
                custom.subscriptionStartDate,
              ),
              subscriptionDuration: custom.subscriptionDuration,
              subscriptionDurationUnit: custom.subscriptionDurationUnit,
              autoRenew: !!custom.autoRenew,
              licenseDelivery: custom.licenseDelivery,
              renewalNoticeDays: custom.renewalNoticeDays,
              dataRetrievalDays: custom.dataRetrievalDays,
              userSeatCount: custom.userSeatCount,
              supplierPICName: custom.supplierPICName,
              supplierPICPhoneNumber: custom.supplierPICPhoneNumber,
              officePICName: custom.officePICName,
              officePICPhoneNumber: custom.officePICPhoneNumber,
              pphCode: custom.pphCode,
              pphTaxObject: custom.pphTaxObject,
              pphPercentage: custom.pphPercentage,
            },
          },
              output);
        } else if (data.purchaseType === '6.4.2') {
          // Penutupan pertanggungan: pemesanan jasa, tata letak SPK.
          return printPurchaseOrderB({
            ...printData,
            poType: '6.4.2',
            items: (data.items || []).map((it: any) => ({
              name: it.task || '',
              remarks: it.remarks_1 || '',
              quantity: Number(it.quantity) || 0,
              unit: it.unit,
              price: Number(it.price) || 0,
            })),
            includePpn: Number(data.ppn) > 0,
            sections: buildInsuranceClauses(
              {
                ...printData.clauseContext,
                paymentTerm: custom.paymentTerm ?? data.payment_term,
                creditTerm: custom.creditTerm,
                prepaidTerm: custom.prepaidTerm,
                insuranceChannel: custom.insuranceChannel || 'broker',
                hasPremium: (custom.premiums || []).length > 0,
                policyDeliveryDays: custom.policyDeliveryDays,
                isSuretyBond: !!custom.isSuretyBond,
                pphCode: custom.pphCode,
                pphTaxObject: custom.pphTaxObject,
                pphPercentage: custom.pphPercentage,
              } as any,
              custom.additionalClauses || [],
            ),
          },
              output);
        } else if (data.purchaseType === '6.5.2') {
          // Pelatihan: pemesanan jasa, tata letak SPK.
          return printPurchaseOrderB({
            ...printData,
            poType: '6.5.2',
            items: (data.items || []).map((it: any) => ({
              name: it.task || '',
              // Tanggal pelaksanaan dan lembaga penerbit dirangkai ulang
              // agar cetak ulang sama dengan dokumen aslinya.
              remarks: this.periodeLembaga(it),
              quantity: Number(it.quantity) || 0,
              unit: it.unit,
              price: Number(it.price) || 0,
            })),
            includePpn: Number(data.ppn) > 0,
            sections: buildTrainingClauses(
              {
                ...printData.clauseContext,
                paymentTerm: custom.paymentTerm ?? data.payment_term,
                creditTerm: custom.creditTerm,
                prepaidTerm: custom.prepaidTerm,
                trainingVenue: custom.trainingVenue,
                participantCancelDays: custom.participantCancelDays,
                certificateDueDays: custom.certificateDueDays,
                retakeCostBearer: custom.retakeCostBearer,
                pphCode: custom.pphCode,
                pphTaxObject: custom.pphTaxObject,
                pphPercentage: custom.pphPercentage,
              } as any,
              custom.additionalClauses || [],
            ),
          },
              output);
        } else if (data.purchaseType === '6.5.1') {
          // Kuota adalah pembelian slot (tata letak surat pesanan);
          // pemeriksaan peserta adalah pemesanan jasa (tata letak SPK).
          const kuota = custom.recruitmentMode !== 'peserta';
          const data651 = {
      // Keadaan persetujuan dan penanda adendum diteruskan lewat
      // muatan bersama ini; enam titik cetak memakainya alih-alih
      // objek literal, sehingga tanpa ini capnya tidak pernah muncul.
            ...printData,
            poType: '6.5.1',
            items: (data.items || []).map((it: any) => ({
              name: it.task || '',
              remarks: it.remarks_1 || '',
              quantity: Number(it.quantity) || 0,
              unit: it.unit,
              price: Number(it.price) || 0,
            })),
            includePpn: Number(data.ppn) > 0,
            clauseContext: {
              ...printData.clauseContext,
              paymentTerm: custom.paymentTerm ?? data.payment_term,
              creditTerm: custom.creditTerm,
              prepaidTerm: custom.prepaidTerm,
              pphCode: custom.pphCode,
              pphTaxObject: custom.pphTaxObject,
              pphPercentage: custom.pphPercentage,
              recruitmentMode: custom.recruitmentMode || 'kuota',
              quotaValidUntil: this.tanggalPanjang(custom.quotaValidUntil),
              resultDueDays: custom.resultDueDays,
              participantCancelDays: custom.participantCancelDays,
            },
          };

          if (kuota) {
            return printPurchaseOrderG(data651,
              output);
          } else {
            return printPurchaseOrderB(data651,
              output);
          }
        } else if (data.purchaseType === '6.4.1') {
          // Biaya resmi tidak disimpan sebagai baris item — nilainya bukan
          // bagian dari dpp — melainkan di customData.
          const fees = custom.officialFees || [];
          const ctx641: any = {
            paymentTerm: custom.paymentTerm ?? data.payment_term,
            creditTerm: custom.creditTerm,
            prepaidTerm: custom.prepaidTerm,
            pphCode: custom.pphCode ?? data.pphCode,
            pphTaxObject: custom.pphTaxObject ?? data.pphTaxObject,
            pphPercentage: custom.pphPercentage ?? data.pphPercentage,
            hasOfficialFee: fees.length > 0,
            rejectionCostBearer: custom.rejectionCostBearer,
            documentReturnDays: custom.documentReturnDays,
            reportingIntervalDays: custom.reportingIntervalDays,
          };

          return printPurchaseOrder641({
              isApproved,
              status,
              isAdendum,
            purchaseOrderName: data.name,
            date: data.date,
            projectName: data.projectName,
            supplierName: data.supplierName ?? '',
            supplierPrefix: data.supplierPrefix ?? '',
            supplierAddress: data.supplierAddress ?? '',
            supplierCity: data.supplierCity ?? '',
            supplierNpwp: data.supplierNpwp ?? '',
            items: (data.items || []).map((it: any) => ({
              task: it.task || '',
              description: it.remarks_1 || '',
              targetDays: it.remarks_2 || '',
              quantity: Number(it.quantity) || 0,
              unit: it.unit,
              price: Number(it.price) || 0,
            })),
            officialFees: fees.map((x: any) => ({
              task: x.task,
              description: x.description,
              amount: Number(x.amount) || 0,
            })),
            includePpn: Number(data.ppn) > 0,
            sections: buildLegalServiceClauses(
              ctx641,
              // PO lama menyimpan catatan sebagai satu blok teks pada
              // `notes`; dipakai sebagai poin tunggal supaya isinya
              // tidak hilang dari dokumen.
              custom.additionalClauses?.length
                ? custom.additionalClauses
                : custom.notes
                  ? [
                      String(custom.notes)
                        .replace(/<[^>]*>/g, '')
                        .trim(),
                    ]
                  : [],
            ),
            billingTerms: buildLegalServiceBillingTerms(fees.length > 0),
          },
              output);
        } else if (data.purchaseType === '5.1.2') {
          // Perawatan aset punya dua bentuk dokumen: sparepart adalah
          // pembelian barang (tata letak G), perbaikan adalah pemesanan
          // jasa (tata letak SPK). Keduanya memakai template klausul
          // '5.1.2' yang sama.
          const jasa = custom.maintenanceMode === 'jasa';
          const data512 = {
            ...printData,
            poType: '5.1.2',
            items: (data.items || []).map((it: any) => ({
              name: jasa
                ? it.task || ''
                : it.item_description || it.sku || '',
              // remarks_2 = aset yang dirawat, remarks_1 = catatan baris.
              remarks: [it.remarks_2, it.remarks_1]
                .filter(Boolean)
                .join(' — '),
              quantity: Number(it.quantity) || 0,
              unit: it.unit,
              price: Number(it.price) || 0,
            })),
            includePpn: Number(data.ppn) > 0,
            clauseContext: {
              ...printData.clauseContext,
              maintenanceMode: custom.maintenanceMode || 'barang',
              pphCode: custom.pphCode,
              pphTaxObject: custom.pphTaxObject,
              pphPercentage: custom.pphPercentage,
            },
          };

          if (jasa) {
            return printPurchaseOrderB({
              ...data512,
              billingTerms: buildMaintenanceBillingTerms(),
              billingTitle:
                'TATA CARA PENAGIHAN DAN PEMBAYARAN\nJASA PERBAIKAN & PERAWATAN',
            },
              output);
          } else {
            return printPurchaseOrderG(data512,
              output);
          }
        } else if (this.dariFormB(data, custom)) {
          // SPK sewa alat: nama alat dari katalog equipment.
          // Termasuk yang diterbitkan sebagai tipe A — bentuk dokumennya
          // mengikuti formulir asalnya, bukan kode jenisnya.
          return printPurchaseOrderB({
              isApproved,
              status,
              isAdendum,
            purchaseOrderName: data.name,
            date: data.date,
            projectName: data.projectName,
            supplierName: data.supplierName ?? '',
            supplierPrefix: data.supplierPrefix ?? '',
            supplierAddress: data.supplierAddress ?? '',
            supplierCity: data.supplierCity ?? '',
            supplierNpwp: data.supplierNpwp ?? '',
            /*
             * Mobilisasi DIPEKARKAN, sama seperti saat dokumennya pertama
             * kali dicetak.
             *
             * Tanpa ini, cetak ulang kehilangan baris mobilisasi dan
             * demobilisasi — dan subtotalnya lebih kecil daripada dokumen
             * yang sudah ditandatangani vendor. Selisihnya tampak seperti
             * kesalahan hitung pada lembar yang seharusnya identik.
             *
             * `remarks_4` dan `remarks_5` HARUS ikut diteruskan; tanpa
             * keduanya `perluasItemMobilisasi` tidak menemukan nilainya dan
             * diam-diam tidak memekarkan apa pun.
             */
            items: perluasItemMobilisasi(
              (data.items || []).map((it: any) => ({
                name:
                  it.equipment_name || it.item_description || it.task || '',
                // Periode sewa (remarks_1/2) dan lokasi (remarks_3)
                // dirangkai ulang agar cetak ulang sama dengan dokumen
                // yang keluar saat PO dibuat.
                remarks: this.periodeLokasiSewa(it),
                quantity: Number(it.quantity) || 0,
                unit: it.unit,
                price: Number(it.price) || 0,
                remarks_4: it.remarks_4,
                remarks_5: it.remarks_5,
              })),
            ),
            includePpn: Number(data.ppn) > 0,
            templateVersion: data.templateVersion,
            // Lembar penagihan mengikuti bentuk pekerjaannya: pada
            // pengangkutan tidak ada periode pekan maupun CoP.
            billingTerms:
              data.purchaseType === 'A'
                ? buildTransportRentalBillingTerms()
                : buildEquipmentRentalBillingTerms(
                    isTempoTerm(custom.paymentTerm),
                  ),
            billingTitle:
              'TATA CARA PENAGIHAN DAN PEMBAYARAN\nPENYEWAAN ALAT KERJA',
            clauseContext: {
              // PO lama tidak menyimpan penanda ini; cakupan pengangkutan
              // disimpulkan dari jenis dokumennya agar cetak ulangnya
              // tetap sama dengan dokumen aslinya.
              includeTransportCoverage:
                custom.includeTransportCoverage ??
                String(data.purchaseType || '').startsWith('A'),
              // PO lama tidak menyimpan jenis sewanya; alat berat dipakai
              // sebagai anggapan agar dokumennya tercetak sama seperti
              // saat diterbitkan.
              rentalCategory: custom.rentalCategory || 'alat-berat',
              // PO-B lama menyimpan termin sebagai teks bebas; keduanya
              // dikirim agar yang lama tetap tercetak apa adanya.
              paymentTerm: custom.paymentTerm,
              paymentTermText: custom.paymentTerm,
              creditTerm: custom.creditTerm,
              prepaidTerm: custom.prepaidTerm,
              // PO lama tidak menyimpan field ini; nilai bawaannya false
              // sesuai perilaku sebelumnya (sewa tanpa operator).
              operatorByVendor: !!custom.operatorByVendor,
              // PO lama tidak menyimpan field ini; 'kedua' adalah
              // perilaku yang berlaku sebelumnya.
              equipmentRiskBearer: custom.equipmentRiskBearer || 'kedua',
              // PO lama tidak menyimpan field ini; disimpulkan ulang dari
              // satuan baris sewa yang tercatat.
              rentalByHour:
                custom.rentalByHour ??
                (data.items || []).some(
                  (it: any) =>
                    String(it.unit || '').toLowerCase() === 'jam',
                ),
              quotaPeriodDays: custom.quotaPeriodDays,
              excessHourRate: custom.excessHourRate,
            },
            additionalClauses: printData.additionalClauses,
          },
              output);
        } else if (data.purchaseType === 'D') {
          /*
           * Konteks klausulnya disusun ulang, TIDAK memakai `printData`.
           *
           * `printData.clauseContext` hanya memuat lokasi kerja dan jangka
           * waktu. Seluruh hak dan kewajiban pekerja — lembur, jam shift,
           * kebijakan hari Minggu, tempat tinggal, jadwal upah — tidak ada di
           * dalamnya, sehingga PDF yang dicetak ulang dari daftar ini jauh
           * lebih sedikit isinya daripada yang dicetak sesaat setelah dibuat.
           * Dan yang dicetak ulang itulah yang biasanya sampai ke pekerja.
           */
          // SPK tenaga kerja: satu baris item = satu komponen upah
          return printPurchaseOrderD({
              isApproved,
              status,
              isAdendum,
            purchaseOrderName: data.name,
            date: data.date,
            projectName: data.projectName,
            workerName: data.supplierName ?? '',
            workerPrefix: data.supplierPrefix ?? '',
            workerAddress: data.supplierAddress ?? '',
            workerCity: data.supplierCity ?? '',
            workerNpwp: data.supplierNpwp ?? '',
            task: (data.items || [])[0]?.task,
            items: (data.items || []).map((it: any) => ({
              label: it.remarks_3 || it.task || '',
              amount: Number(it.price) || 0,
              unit: it.unit,
            })),
            templateVersion: data.templateVersion,
            clauseContext: konteksKlausulTenagaKerja(custom, data),
            additionalClauses: printData.additionalClauses,
          },
              output);
        } else if (
          data.purchaseType === 'F' &&
          (custom.materialType === 'ujitekan' ||
            custom.materialType === 'ujibesi')
        ) {
          /*
           * Jasa pengujian dicetak sebagai Surat Perintah Kerja.
           *
           * KEDUA jenis pengujian harus disebut. Sebelumnya hanya
           * `ujitekan` yang diperiksa, sehingga uji tarik dan tekuk besi
           * tercetak ulang sebagai PURCHASE ORDER — berbeda dari dokumen
           * yang ditandatangani vendor saat pertama kali terbit.
           *
           * Pengadaan beton, besi, dan material lain tetap PURCHASE
           * ORDER; yang menjadi SPK hanya jasa pengujian.
           */
          return printPurchaseOrderB({
            ...printData,
            includePpn: Number(data.ppn) > 0,
          },
              output);
        } else if (data.purchaseType === 'C') {
          return printPurchaseOrderC({
            ...printData,
            // komponen pajak khas PO-C (pembelian BBM)
            pbbkbPercent: Number(custom.pbbkbPercent) || 0,
            pph22: Number(custom.pph22) || 0,
          },
              output);
        } else {
          return printPurchaseOrderG(printData,
              output);
        }
      } catch (e) {
        console.error('Gagal membuat PDF purchase order:', e);
        this.snackBar.open(
          this.translate.instant('purchaseOrder.reprintFailed'),
          'Close',
          { duration: 3000 },
        );
      }
  }


  /**
   * Ubah status purchase order.
   *
   * Memakai `PATCH /purchase-orders/{id}/status`, satu-satunya rute yang
   * disediakan server. Sebelumnya layar menembak `POST .../approve` — jalur
   * yang tidak pernah ada, sehingga jawabannya selalu 404 dan tombolnya
   * tidak pernah bekerja.
   *
   * `status` dikirim sebagai parameter kueri, bukan badan permintaan: pada
   * rute itu ia dideklarasikan sebagai enum biasa, dan FastAPI membacanya
   * dari kueri.
   */
  private ubahStatus(po: any, status: 'approved' | 'cancelled', kunciSukses: string) {
    this.apiService
      .patch(`purchase-orders/${po.id}/status?status=${status}`, {})
      .subscribe({
        next: () => {
          this.snackBar.open(this.translate.instant(kunciSukses), 'Close', {
            duration: 2000,
          });
          this.fetch(this.page);
        },
        error: (err) => {
          /*
           * Pesan diterjemahkan lewat layanan bersama, bukan dibaca mentah
           * dari `detail`.
           *
           * Galat berkode dari controller memang dapat diterjemahkan, tetapi
           * galat yang datang dari kerangka kerja — 404 karena rutenya tidak
           * ada, misalnya — tidak berkode sama sekali. Menampilkan `detail`
           * apa adanya membuat pengguna membaca "Not Found".
           */
          this.snackBar.open(this.serverMessage.terjemahkan(err), 'Close', {
            duration: 4000,
          });
        },
      });
  }

  /** Dokumen ini sudah diperiksa. */
  sudahDiperiksa(po: any): boolean {
    return !!po?.isChecked;
  }

  /**
   * Tandai dokumen sudah diperiksa.
   *
   * Tahap SEBELUM persetujuan; dokumen yang belum diperiksa ditolak server
   * ketika hendak disetujui.
   */
  periksa(po: any): void {
    this.ubahPemeriksaan(po, true, 'purchaseOrder.diperiksa');
  }

  /**
   * Cabut pemeriksaan.
   *
   * Dikonfirmasi lebih dulu karena persetujuan yang terlanjur ikut GUGUR —
   * dokumen kembali ke draf, dan yang tadinya siap terbit harus melewati
   * kedua tahap lagi.
   */
  batalkanPemeriksaan(po: any): void {
    this.dialog
      .open(DeleteConfirmationComponent, {
        data: {
          title: this.translate.instant('purchaseOrder.cabutPeriksaTitle'),
          prompt: this.translate.instant('purchaseOrder.cabutPeriksaPrompt', {
            name: po.name,
          }),
        },
      })
      .afterClosed()
      .subscribe((setuju) => {
        if (setuju) {
          this.ubahPemeriksaan(po, false, 'purchaseOrder.periksaDicabut');
        }
      });
  }

  private ubahPemeriksaan(po: any, checked: boolean, kunciSukses: string) {
    this.apiService
      .patch(`purchase-orders/${po.id}/checked?checked=${checked}`, {})
      .subscribe({
        next: () => {
          this.snackBar.open(
            this.translate.instant(kunciSukses),
            'Close',
            { duration: 2000 },
          );
          this.fetch(this.page);
        },
        error: (err) =>
          this.snackBar.open(
            this.serverMessage.terjemahkan(err),
            'Close',
            { duration: 5000 },
          ),
      });
  }

  approve(po: any) {
    this.ubahStatus(po, 'approved', 'notify.approveSuccess');
  }

  reject(po: any) {
    this.dialog
      .open(DeleteConfirmationComponent, {
        data: {
          title: this.translate.instant('purchaseOrder.rejectTitle'),
          prompt: this.translate.instant('confirm.rejectNamed', {
            name: po.name,
          }),
        },
      })
      .afterClosed()
      .subscribe((setuju) => {
        // Penolakan dikonfirmasi lebih dulu: statusnya tidak dapat
        // dikembalikan lewat layar ini, dan PO yang terlanjur dibatalkan
        // harus dibuat ulang.
        if (setuju) this.ubahStatus(po, 'cancelled', 'notify.rejectSuccess');
      });
  }

  deleteOrder(po: any) {
    this.dialog
      .open(DeleteConfirmationComponent, {
        data: {
          title: this.translate.instant('confirm.deleteTitle'),
          prompt: this.translate.instant('confirm.deleteNamed', {
            name: po.name,
          }),
        },
      })
      .afterClosed()
      .subscribe((confirmed) => {
        if (!confirmed) return;
        this.apiService.delete(`purchase-orders/${po.id}`).subscribe({
          next: () => {
            this.snackBar.open(
      this.translate.instant('notify.deleteSuccess'), 'Close', {
              duration: 2000,
            });
            this.fetch(this.page);
          },
          error: (err) => {
            this.snackBar.open(
              this.serverMessage.terjemahkan(err, 'notify.deleteFailed'),
              'Close',
              { duration: 3000 },
            );
          },
        });
      });
  }

  /** Kode jenis PO -> segmen rute pembuatannya. */
  private readonly createRoutes: Record<string, string> = {
    A: 'A',
    B: 'B',
    C: 'C',
    D: 'D',
    F: 'F',
    G: 'G',
    H: 'H',
    '5.1.1': '511',
    '5.1.2': '512',
    '5.1.6': '516',
    '5.1.12': '5112',
    '6.3.1': '631',
    '6.3.2': '632',
    '6.4.1': '641',
    '6.4.2': '642',
    '6.5.1': '651',
    '6.5.2': '652',
    // 6.4.2 (asuransi) dan 6.5.2 belum memiliki formulir; sengaja tidak
    // dicantumkan agar pemilihnya memberi pesan "belum tersedia" daripada
    // mengarahkan ke alamat yang tidak ada.
  };

  /**
   * Pemilih jenis PO dibuka sebagai dialog, bukan halaman tersendiri, agar
   * daftar PO tetap terlihat dan menutupnya tidak perlu navigasi balik.
   */
  openTypeSelector() {
    this.dialog
      .open(PurchaseOrderTypeSelectorComponent, {
        maxWidth: '94vw',
        autoFocus: false,
      })
      .afterClosed()
      .subscribe((type: string) => {
        if (!type) return;
        const segment = this.createRoutes[type];
        if (!segment) {
          this.snackBar.open(`Jenis PO ${type} belum tersedia`, 'Close', {
            duration: 3000,
          });
          return;
        }
        this.router.navigate(['Create', segment], { relativeTo: this.route });
      });
  }
}
