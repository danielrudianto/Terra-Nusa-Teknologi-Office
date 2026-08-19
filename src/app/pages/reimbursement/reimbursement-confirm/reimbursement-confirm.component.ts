import { CommonModule, DatePipe } from '@angular/common';
import { TranslateService } from '@ngx-translate/core';
import { Component, Inject, inject } from '@angular/core';
import {
  FormArray,
  FormBuilder,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
} from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { TranslatePipe } from '@ngx-translate/core';
import { MatInputModule } from '@angular/material/input';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService } from 'src/app/services/api.service';
import { DialogGeserDirective } from '../../../directives/dialog-geser.directive';
import {
  KartuPilihan,
  PILIHAN_CARA_BAYAR,
} from 'src/app/constants/pilihan-pembelian';
import { PILIHAN_JENIS_BEBAN } from 'src/app/constants/pilihan-reimbursement';
import { ServerMessageService } from 'src/app/services/server-message.service';

@Component({
  selector: 'app-reimbursement-confirm',
  imports: [
    MatDialogModule,
    MatSnackBarModule,
    MatInputModule,
    ReactiveFormsModule,
    MatIconModule,
    MatButtonModule,
    CommonModule,
    TranslatePipe,
    DialogGeserDirective,
  ],
  // `provideNgxMask` dilepas bersama isian bertopengnya: jumlahnya kini
  // ditampilkan sebagai teks, bukan sebagai isian yang tidak dapat diisi.
  providers: [DatePipe],
  templateUrl: './reimbursement-confirm.component.html',
  styleUrl: './reimbursement-confirm.component.scss',
})
export class ReimbursementConfirmComponent {
  private readonly translate = inject(TranslateService);
  constructor(
    @Inject(MAT_DIALOG_DATA) public data: { id: number },
    private apiService: ApiService,
    private snackBar: MatSnackBar,
    private datePipe: DatePipe,
    private formBuilder: FormBuilder,
    private dialog: MatDialogRef<ReimbursementConfirmComponent>,
    private serverMessage: ServerMessageService,
  ) {}

  formGroup: FormGroup = new FormGroup({
    date: new FormControl(''),
    dueDate: new FormControl(''),
    projectName: new FormControl(''),
    name: new FormControl(''),
    purchaseType: new FormControl(''),
    items: new FormArray([]),
    bankName: new FormControl(''),
    bankAccountName: new FormControl(''),
    bankAccountNumber: new FormControl(''),
    paymentMethod: new FormControl(''),
    total: new FormControl(0),
  });

  isLoading: boolean = false;
  isSubmitting: boolean = false;

  ngOnInit(): void {
    this.fetchData();
  }

  fetchData() {
    this.isLoading = true;
    this.apiService
      .get('reimbursements/' + this.data.id, {})
      .subscribe({
        next: (data: any) => {
          if (data.reimbursement.isApprove) {
            this.snackBar.open(
      this.translate.instant('notify.alreadyApproved'),
              'Close',
              {
                duration: 3000,
              },
            );
            this.dialog.close();
            return;
          }

          if (data.reimbursement.isDelete) {
            this.snackBar.open(
      this.translate.instant('notify.alreadyRejected'),
              'Close',
              {
                duration: 3000,
              },
            );
            this.dialog.close();
            return;
          }

          /*
           * Kode disimpan APA ADANYA, teksnya dirakit saat ditampilkan.
           *
           * Sebelumnya keduanya diterjemahkan di sini menjadi kalimat Inggris
           * yang ditulis langsung di kode — "Bank Transfer", "Transportation"
           * — sehingga layar ini tetap berbahasa Inggris bagi pengguna yang
           * memilih bahasa lain, dan menambah satu tempat lagi yang harus
           * diubah setiap kali daftar pilihannya berubah.
           */
          this.formGroup.patchValue({
            date: this.datePipe.transform(
              data.reimbursement.date,
              'dd MMMM yyyy',
            ),
            /*
             * `dueDate`, bukan `date`.
             *
             * Keduanya sempat mengambil kolom yang sama, sehingga jatuh tempo
             * pada layar ini SELALU sama dengan tanggal pengajuannya. Ini
             * layar tempat pembayaran disetujui, dan jatuh tempo justru yang
             * menentukan kapan uangnya harus keluar.
             */
            dueDate: this.datePipe.transform(
              data.reimbursement.dueDate,
              'dd MMMM yyyy',
            ),
            name: data.reimbursement.name,
            projectName: data.reimbursement.projectName,
            purchaseType: data.reimbursement.purchaseType,
            bankName: data.reimbursement.bankName,
            bankAccountName: data.reimbursement.bankAccountName,
            bankAccountNumber: data.reimbursement.bankAccountNumber,
            paymentMethod: data.reimbursement.paymentMethod,
            total: data.reimbursement_items.reduce(
              (a: any, b: any) => a + b.amount,
              0,
            ),
          });

          data.reimbursement_items.forEach((item: any) => {
            this.t.push(
              this.formBuilder.group({
                amount: new FormControl(item.amount),
                description: new FormControl(item.description),
                date: new FormControl(
                  this.datePipe.transform(item.date, 'dd MMMM yyyy'),
                ),
              }),
            );
          });
        },
        error: (error) => {
          this.snackBar.open(
      this.translate.instant('notify.loadFailed'), 'Close', {
            duration: 3000,
          });
          console.error('Error fetching reimbursement data:', error);
          this.dialog.close();
        },
      })
      .add(() => {
        this.isLoading = false;
      });
  }

  /*
   * `isSubmitting` DINYALAKAN, bukan hanya dipadamkan.
   *
   * Tombolnya sudah lama memakai `[disabled]="isSubmitting"`, tetapi nilainya
   * tidak pernah menjadi `true` — hanya dikembalikan ke `false` di `.add()`.
   * Selama permintaannya berjalan tombolnya tetap hidup, dan klik kedua
   * mengirim persetujuan kedua atas dokumen yang sama.
   *
   * Kegagalannya juga dikatakan. Tanpa penangan galat, persetujuan yang
   * DITOLAK server tidak menghasilkan apa pun di layar: dialognya tetap
   * terbuka, tidak ada pesan, dan yang menekan menyangka sudah tersetujui.
   */
  approve() {
    if (this.isSubmitting) return;
    this.isSubmitting = true;
    this.apiService
      .put('reimbursements/approve/' + this.data.id, {})
      .subscribe({
        next: (_) => {
          this.snackBar.open(
            this.translate.instant('notify.approveSuccess'),
            'Close',
            { duration: 3000 },
          );
          this.dialog.close('approve');
        },
        error: (galat) => {
          this.snackBar.open(
            this.serverMessage.terjemahkan(galat),
            'Close',
            { duration: 3000 },
          );
        },
      })
      .add(() => {
        this.isSubmitting = false;
      });
  }

  /** Sama seperti `approve()`: dijaga dari klik ganda, galatnya dikatakan. */
  reject() {
    if (this.isSubmitting) return;
    this.isSubmitting = true;
    this.apiService
      .put('reimbursements/reject/' + this.data.id, {})
      .subscribe({
        next: (_) => {
          this.snackBar.open(
            this.translate.instant('notify.updateSuccess'),
            'Close',
            { duration: 3000 },
          );
          this.dialog.close('reject');
        },
        error: (galat) => {
          this.snackBar.open(
            this.serverMessage.terjemahkan(galat),
            'Close',
            { duration: 3000 },
          );
        },
      })
      .add(() => {
        this.isSubmitting = false;
      });
  }

  get f() {
    return this.formGroup.controls;
  }

  get t() {
    return this.formGroup.get('items') as FormArray;
  }

  /** Kunci terjemahan sebuah kode, dari daftar pilihan yang sama dengan formulirnya. */
  private kunciLabel(daftar: KartuPilihan[], nilai: unknown): string {
    return daftar.find((o) => o.value === nilai)?.label ?? '';
  }

  get kunciJenisBeban(): string {
    return this.kunciLabel(
      PILIHAN_JENIS_BEBAN,
      this.formGroup.get('purchaseType')?.value,
    );
  }

  get kunciCaraBayar(): string {
    return this.kunciLabel(
      PILIHAN_CARA_BAYAR,
      this.formGroup.get('paymentMethod')?.value,
    );
  }

  get nilai(): number {
    const n = Number(this.formGroup.get('total')?.value);
    return isNaN(n) ? 0 : n;
  }
}
