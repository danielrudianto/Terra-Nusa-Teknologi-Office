import { Clipboard } from '@angular/cdk/clipboard';
import { TranslateService } from '@ngx-translate/core';
import { CommonModule, DatePipe } from '@angular/common';
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
import { MatInputModule } from '@angular/material/input';
import { MatListModule } from '@angular/material/list';
import { TranslatePipe } from '@ngx-translate/core';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService } from 'src/app/services/api.service';
import { AuditTrailComponent } from '../../../components/audit-trail/audit-trail.component';
import { DialogGeserDirective } from '../../../directives/dialog-geser.directive';

@Component({
  selector: 'app-reimbursement-view',
  imports: [
    AuditTrailComponent,
    MatDialogModule,
    MatSnackBarModule,
    MatInputModule,
    ReactiveFormsModule,
    MatIconModule,
    MatButtonModule,
    CommonModule,
    MatListModule,
    TranslatePipe,
    DialogGeserDirective,
  ],
  providers: [DatePipe],
  templateUrl: './reimbursement-view.component.html',
  styleUrl: './reimbursement-view.component.scss',
})
export class ReimbursementViewComponent {
  private readonly translate = inject(TranslateService);
  constructor(
    @Inject(MAT_DIALOG_DATA) public data: { id: number },
    private apiService: ApiService,
    private snackBar: MatSnackBar,
    private datePipe: DatePipe,
    private formBuilder: FormBuilder,
    private dialog: MatDialogRef<ReimbursementViewComponent>,
    private clipboard: Clipboard,
  ) {}

  formGroup: FormGroup = new FormGroup({
    date: new FormControl(''),
    createdAt: new FormControl(''),
    dueDate: new FormControl(''),
    projectName: new FormControl(''),
    name: new FormControl(''),
    purchaseType: new FormControl(''),
    items: new FormArray([]),
    payments: new FormArray([]),
    bankName: new FormControl(''),
    bankAccountName: new FormControl(''),
    bankAccountNumber: new FormControl(''),
    paymentMethod: new FormControl(''),
    total: new FormControl(0),
  });

  isLoading: boolean = false;

  ngOnInit(): void {
    this.fetchData();
  }

  fetchData() {
    this.isLoading = true;
    this.apiService
      .get('reimbursements/' + this.data.id, {})
      .subscribe({
        next: (data: any) => {
          const paymentMethod = data.reimbursement.paymentMethod;
          const paymentMethodText =
            paymentMethod == 'bank'
              ? 'Bank Transfer'
              : paymentMethod == 'cash'
                ? 'Cash'
                : 'Virtual Account';

          const purchaseType = data.reimbursement.purchaseType;
          const purchaseTypeText =
            purchaseType == 'A'
              ? 'Transportation'
              : purchaseType == 'E'
                ? 'Coordination; Consumption; and Accomodation'
                : 'Document handling & Stationery';
          this.formGroup.patchValue({
            date: this.datePipe.transform(
              data.reimbursement.date,
              'dd MMMM yyyy',
            ),
            /*
             * `dueDate`, bukan `date`.
             *
             * Keduanya kolom tersendiri, dan yang tercetak di sini selama ini
             * tanggal pengajuannya — sehingga setiap pengajuan tampak jatuh
             * tempo pada hari ia diajukan. Layar konfirmasi sudah dibetulkan;
             * yang ini terlewat, dan keduanya membaca dokumen yang sama.
             */
            dueDate: this.datePipe.transform(
              data.reimbursement.dueDate,
              'dd MMMM yyyy',
            ),
            createdAt: this.datePipe.transform(
              data.reimbursement.createdAt,
              'dd MMMM yyyy',
            ),
            name: data.reimbursement.name,
            projectName: data.reimbursement.projectName,
            purchaseType: purchaseType,
            bankName: data.reimbursement.bankName,
            bankAccountName: data.reimbursement.bankAccountName,
            bankAccountNumber: data.reimbursement.bankAccountNumber,
            paymentMethod: paymentMethodText,
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

          data.payments.forEach((x: any) => {
            this.p.push(
              this.formBuilder.group({
                id: [x.id],
                bankAccountName: [x.bankAccountName],
                bankAccountNumber: [x.bankAccountNumber],
                bankName: [x.bankName],
                amount: [x.amount],
                date: [x.date],
                isApprove: [x.isApprove],
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

  copyBankAccountNumber() {
    this.clipboard.copy(this.formGroup.get('bankAccountNumber')!.value);
    this.snackBar.open(
      this.translate.instant('notify.copied'), 'Close', {
      duration: 3000,
    });
  }

  formatDate(date: string): string {
    if (!date) return '-';
    const d = new Date(date);
    if (isNaN(d.getTime())) return date;
    return d.toLocaleDateString('id-ID', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  }

  private rp(n: number): string {
    return 'Rp ' + Math.round(n || 0).toLocaleString('id-ID');
  }

  /** Build a WhatsApp-friendly summary and copy it to the clipboard. */
  copyDocument(): void {
    const f = this.formGroup.value;
    const lines = [
      '*DATA REIMBURSEMENT*',
      f.name || '-',
      '',
      `*Tanggal:* ${f.date || '-'}`,
      `*Project:* ${f.projectName || '-'}`,
      `*Tipe:* ${f.purchaseType || '-'}`,
      '',
      '*RINCIAN ITEM*',
      ...this.t.controls.map((it) => {
        const d = it.get('date')?.value || '-';
        const desc = it.get('description')?.value || '-';
        const amt = this.rp(it.get('amount')?.value);
        return `• ${d} — ${desc}: ${amt}`;
      }),
      '',
      `*Total:* ${this.rp(f.total)}`,
      '',
      '*REKENING TUJUAN*',
      `${f.bankName || '-'} — ${f.bankAccountName || '-'}`,
      `${f.bankAccountNumber || '-'}`,
    ];
    this.clipboard.copy(lines.join('\n'));
    this.snackBar.open(
      this.translate.instant('notify.copied'),
      'Close',
      { duration: 3000 },
    );
  }

  close() {
    this.dialog.close();
  }

  get f() {
    return this.formGroup.controls;
  }

  get t() {
    return this.formGroup.get('items') as FormArray;
  }

  get p() {
    return this.formGroup.get('payments') as FormArray;
  }
}
