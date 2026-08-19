import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { MatDialog } from '@angular/material/dialog';
import { ContractViewComponent } from '../contract-view/contract-view.component';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import moment from 'moment';

import { ApiService } from '../../../services/api.service';
import { HeaderTitleComponent } from '../../../components/header-title/header-title.component';
import { CanDirective } from '../../../directives/can.directive';
import { DeleteConfirmationComponent } from '../../../components/delete-confirmation/delete-confirmation.component';
import { Project, ProjectContract, keadaanProyek } from '../project.model';
import { PphSelectorComponent } from '../../../components/pph-selector/pph-selector.component';
import { IPPh } from '../../../utils/pph';
import { AuditTrailComponent } from '../../../components/audit-trail/audit-trail.component';
import { NgxMaskDirective, provideNgxMask } from 'ngx-mask';

@Component({
  selector: 'app-project-view',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatDatepickerModule,
    MatSnackBarModule,
    TranslatePipe,
    HeaderTitleComponent,
    CanDirective,
    AuditTrailComponent,
    NgxMaskDirective,
  ],
  providers: [provideNgxMask(), provideNativeDateAdapter()],
  templateUrl: './project-view.component.html',
  styleUrl: './project-view.component.scss',
})
export class ProjectViewComponent implements OnInit {
  constructor(
    private apiService: ApiService,
    private route: ActivatedRoute,
    private router: Router,
    private dialog: MatDialog,
    private snackBar: MatSnackBar,
    private translate: TranslateService,
  ) {}

  isLoading = true;
  isSubmitting = false;
  project: Project | null = null;
  contracts: ProjectContract[] = [];
  sedangTambah = false;

  formGroup = new FormGroup({
    documentNumber: new FormControl('', [
      Validators.required,
      Validators.maxLength(100),
    ]),
    documentType: new FormControl<'spk' | 'adendum'>('spk', Validators.required),
    // Nilai kontrak tidak boleh negatif: kontrak bernilai minus tidak
    // berarti apa pun, dan margin proyeknya ikut salah tanpa galat.
    dpp: new FormControl<number | null>(null, [
      Validators.required,
      Validators.min(0),
    ]),
    ppn: new FormControl<number>(11, [
      Validators.required,
      Validators.min(0),
      Validators.max(100),
    ]),
    pphCode: new FormControl<string | null>(null),
    pphTaxObject: new FormControl<string | null>(null),
    pphPercentage: new FormControl<number | null>(null),
    date: new FormControl<Date | null>(null, Validators.required),
    description: new FormControl('', Validators.maxLength(500)),
  });

  /*
   * Nilai dokumen dan potongan dihitung ulang di layar agar terlihat
   * seketika. Server menghitungnya sendiri saat menyimpan — kalau angkanya
   * boleh dikirim dari sini, nominal dokumen bisa tidak cocok dengan
   * komponennya dan tidak ada yang tahu mana yang benar.
   */
  get nilaiDpp(): number {
    return Number(this.formGroup.value.dpp ?? 0);
  }

  get nilaiPpn(): number {
    return (this.nilaiDpp * Number(this.formGroup.value.ppn ?? 0)) / 100;
  }

  get nilaiDokumen(): number {
    return this.nilaiDpp + this.nilaiPpn;
  }

  get nilaiPph(): number {
    return (this.nilaiDpp * Number(this.formGroup.value.pphPercentage ?? 0)) / 100;
  }

  /** Yang benar-benar diterima setelah PPh dipotong. */
  get nilaiDiterima(): number {
    return this.nilaiDokumen - this.nilaiPph;
  }

  pilihPph(): void {
    this.dialog
      .open(PphSelectorComponent, {})
      .afterClosed()
      .subscribe((data: any) => {
        /*
         * "Tanpa PPh" MENGHAPUS pilihan, berbeda dari membatalkan.
         *
         * Keduanya sempat sama-sama menutup tanpa nilai, sehingga baris di
         * bawah memperlakukan keduanya sebagai batal — dan PPh yang sudah
         * terlanjur dipilih tidak pernah hilang.
         */
        if (data?.hapus) {
          this.hapusPph();
          return;
        }
        if (!data) return;
        this.formGroup.patchValue({
          pphCode: data.code,
          pphTaxObject: data.taxObjectName,
          pphPercentage: data.tariff,
        });
      });
  }

  hapusPph(): void {
    this.formGroup.patchValue({
      pphCode: null,
      pphTaxObject: null,
      pphPercentage: null,
    });
  }

  ngOnInit(): void {
    this.route.params.subscribe((p) => this.fetch(Number(p['id'])));
  }

  fetch(id: number): void {
    this.isLoading = true;
    this.apiService
      .get(`projects/${id}`, {})
      .subscribe({
        next: (res: any) => {
          this.project = res?.project ?? null;
          this.contracts = res?.contracts ?? [];
        },
        error: () => {
          this.snackBar.open(
            this.translate.instant('notify.loadFailed'),
            'Close',
            { duration: 3000 },
          );
          this.router.navigate(['/Project']);
        },
      })
      .add(() => {
        this.isLoading = false;
      });
  }

  get keadaan(): string {
    return this.project ? keadaanProyek(this.project) : 'berjalan';
  }

  /**
   * Nilai kontrak berjalan dihitung ulang di layar dari baris yang tampil.
   *
   * Angka dari server tetap benar, tetapi setelah menambah atau menghapus
   * adendum, layar harus segera menunjukkan hasilnya tanpa menunggu
   * pengambilan ulang — dan keduanya harus selalu sama.
   */
  /**
   * Nilai satu dokumen: DPP ditambah PPN-nya.
   *
   * Kolom `value` sudah tidak ada — nilainya dihitung dari komponennya agar
   * angka yang tersimpan tidak mungkin berbeda dari penjumlahannya. Membaca
   * `value` yang tidak ada menghasilkan 0 tanpa satu pun galat, dan nilai
   * kontrak tampil nol meski dokumennya ada.
   */
  nilaiKontrak(k: any): number {
    const dpp = Number(k?.dpp ?? 0);
    const ppn = Number(k?.ppn ?? 0);
    return dpp + (dpp * ppn) / 100;
  }

  /**
   * Buka rincian satu kontrak.
   *
   * Rinciannya dipisah ke dialog karena satu proyek dapat memuat banyak
   * dokumen; menampilkan seluruhnya di daftar membuatnya tidak lagi dapat
   * dibaca sekilas.
   */
  lihatKontrak(k: any): void {
    this.dialog
      .open(ContractViewComponent, {
        data: { contract: k, projectName: this.project?.name },
        width: '560px',
        maxWidth: '94vw',
        autoFocus: false,
      })
      .afterClosed()
      .subscribe((hasil) => {
        if (hasil?.hapus) this.hapusKontrak(hasil.contract);
      });
  }

  get totalKontrak(): number {
    return this.contracts.reduce((a, b) => a + this.nilaiKontrak(b), 0);
  }

  get adaAdendum(): boolean {
    return this.contracts.some((c) => c.documentType === 'adendum');
  }

  bukaTambah(): void {
    this.sedangTambah = true;
    /*
     * Seluruh kendali disebut, termasuk yang memang dikosongkan.
     *
     * `reset()` memberi `null` kepada yang TIDAK disebut — bukan
     * mengembalikannya ke nilai bawaannya. Di sini akibatnya ringan, sebab
     * bawaan keenam kendali itu memang kosong; yang berubah hanya isian teks
     * yang berakhir `null` alih-alih `''`. Ditulis lengkap supaya yang
     * membaca tidak perlu menebak mana yang disengaja.
     */
    this.formGroup.reset({
      documentNumber: '',
      documentType: this.contracts.length === 0 ? 'spk' : 'adendum',
      dpp: null,
      ppn: 11,
      pphCode: null,
      pphTaxObject: null,
      pphPercentage: null,
      date: new Date(),
      description: '',
    });
  }

  batalTambah(): void {
    this.sedangTambah = false;
  }

  simpanKontrak(): void {
    if (!this.project || this.formGroup.invalid || this.isSubmitting) return;

    const v = this.formGroup.value;
    if (!v.dpp || Number(v.dpp) === 0) {
      this.snackBar.open(
        this.translate.instant('project.contractZero'),
        'Close',
        { duration: 4000 },
      );
      return;
    }

    this.isSubmitting = true;
    this.apiService
      .post(`projects/${this.project.id}/contracts`, {
        documentNumber: v.documentNumber,
        documentType: v.documentType,
        dpp: Number(v.dpp),
        ppn: Number(v.ppn ?? 0),
        pphCode: v.pphCode || null,
        pphTaxObject: v.pphTaxObject || null,
        pphPercentage: v.pphPercentage ?? null,
        date: moment(v.date).format('YYYY-MM-DD'),
        description: v.description || null,
      })
      .subscribe({
        next: () => {
          this.snackBar.open(
            this.translate.instant('project.contractAdded'),
            'Close',
            { duration: 3000 },
          );
          this.sedangTambah = false;
          this.fetch(this.project!.id);
        },
        error: () => {
          this.snackBar.open(
            this.translate.instant('notify.saveFailed'),
            'Close',
            { duration: 4000 },
          );
        },
      })
      .add(() => {
        this.isSubmitting = false;
      });
  }

  hapusKontrak(k: ProjectContract): void {
    this.dialog
      .open(DeleteConfirmationComponent, {
        data: {
          title: this.translate.instant('confirm.deleteTitle'),
          prompt: this.translate.instant('confirm.deletePrompt'),
        },
      })
      .afterClosed()
      .subscribe((setuju) => {
        if (!setuju) return;
        this.apiService.delete(`projects/contracts/${k.id}`).subscribe({
          next: () => {
            this.snackBar.open(
              this.translate.instant('project.contractDeleted'),
              'Close',
              { duration: 3000 },
            );
            this.fetch(this.project!.id);
          },
          error: () => {
            this.snackBar.open(
              this.translate.instant('notify.deleteFailed'),
              'Close',
              { duration: 4000 },
            );
          },
        });
      });
  }

  kembali(): void {
    this.router.navigate(['/Project']);
  }
}
