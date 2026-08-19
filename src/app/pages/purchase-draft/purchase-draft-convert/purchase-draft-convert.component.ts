import { Component, ElementRef, ViewChild, inject } from '@angular/core';
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
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatDialog } from '@angular/material/dialog';
import { MatDividerModule } from '@angular/material/divider';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatStepper, MatStepperModule } from '@angular/material/stepper';
import { ActivatedRoute } from '@angular/router';
import { PphSelectorComponent } from 'src/app/components/pph-selector/pph-selector.component';
import { PaymentSlipHelper } from 'src/app/helpers/payment-slip.helper';
import { ProxyPaymentHelper } from 'src/app/helpers/proxy-payment.helper';
import { ApiService } from 'src/app/services/api.service';
import { banks, IBank } from 'src/app/utils/bank';
import { IPPh } from 'src/app/utils/pph';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatTooltipModule } from '@angular/material/tooltip';
import { RouterModule } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';
import { ProjectSelectorComponent } from '../../../components/project-selector/project-selector.component';
import { BankAccountSelectorComponent } from '../../../components/bank-account-selector/bank-account-selector.component';
import { NgxMaskDirective, provideNgxMask } from 'ngx-mask';
import { JENIS_NILAI_LAIN } from 'src/app/constants/jenis-nilai-lain';

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
  selector: 'app-purchase-draft-convert',
  standalone: true,
  templateUrl: './purchase-draft-convert.component.html',
  styleUrl: './purchase-draft-convert.component.scss',
  imports: [
    BankAccountSelectorComponent,
    ProjectSelectorComponent,
    TranslatePipe,
    RouterModule,
    MatTooltipModule,
    MatSlideToggleModule,
    MatButtonModule,
    CommonModule,
    MatStepperModule,
    MatDatepickerModule,
    MatFormFieldModule,
    MatInputModule,
    FormsModule,
    ReactiveFormsModule,
    MatSelectModule,
    MatDividerModule,
    MatIconModule,
    MatAutocompleteModule,
    NgxMaskDirective,
  ],
  // `provideNgxMask()` WAJIB ada di komponen yang memakai mask;
  // tanpa itu atribut `mask` hanya teks yang diabaikan Angular.
  providers: [provideNgxMask()],
})
export class PurchaseDraftConvertComponent {
  /** Jenis nilai lain; satu sumber untuk seluruh layar pembelian. */
  readonly jenisNilaiLain = JENIS_NILAI_LAIN;

  private readonly serverMessage = inject(ServerMessageService);
  private readonly translate = inject(TranslateService);
  constructor(
    private apiService: ApiService,
    private dialog: MatDialog,
    private snackBar: MatSnackBar,
    private router: ActivatedRoute,
  ) {}

  @ViewChild('stepper') stepper: MatStepper | undefined;
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
      invoiceName: new FormControl('', Validators.required),
      receiptName: new FormControl(''),
      taxInvoiceName: new FormControl('', Validators.maxLength(17)),
      supplierID: new FormControl('', Validators.required),
      supplierName: new FormControl(''),
      supplierAddress: new FormControl(''),
      date: new FormControl('', Validators.required),
      dueDate: new FormControl('', Validators.required),
      purchaseOrderName: new FormControl('', [
        Validators.required,
        Validators.pattern(
          /^\d{3,4}-(PO|SPK|PKS)-[A-Z0-9]{4,5}-(A|B|C|D|E|F|G|H1|H2|5\.1\.1|5\.1\.2|5\.1\.6|5\.1\.7|6\.3\.1|6\.3\.2|5\.1\.12|6\.4\.1)$/,
        ),
      ]),
      projectName: new FormControl('', [
        Validators.required,
        Validators.minLength(4),
        Validators.maxLength(5),
      ]),
      purchaseType: new FormControl('', [
        Validators.required,
        Validators.pattern(
          /^\A|B|C|D|E|F|G|H1|H2|5\.1\.1|5\.1\.2|5\.1\.6|5\.1\.7|6\.3\.1|6\.3\.2|5\.1\.12|6\.4\.1$/,
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
    otherValueNote: new FormControl(''),
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
      createPayment: new FormControl(false),
      bankAccountID: new FormControl(''),
    },
    {
      validators: bankAccountIDRequired(),
    },
  );

  ngOnInit() {
    this.fetchBankAccounts();
    this.fetchPurchaseDraft();

    this.metaFormGroup.controls['documentType'].valueChanges.subscribe(() => {
      const documentType = this.metaFormGroup.value['documentType'];
      if (documentType == 'goods') {
        this.valueFormGroup.patchValue({
          pphCode: '',
          pphTaxObject: '',
          pphPercentage: 0,
        });
      }
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
          /^\d{3,4}-(PO|SPK|PKS)-[A-Z]{1,5}-(A|B|C|D|E|F|G|H1|H2|5\.1\.1|5\.1\.2|5\.1\.6|5\.1\.7|6\.3\.1|6\.3\.2|5\.1\.12|6\.4\.1)$/;
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
    this.filteredOptions = this.options.filter(
      (option) =>
        option.name.toLowerCase().includes(filterValue) ||
        option.alias.toLowerCase().includes(filterValue),
    );
  }

  onSubmit() {
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
    const id = this.router.snapshot.params['id'];
    this.isSubmitting = true;

    const purchaseData = {
      id: id,
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
        .put('purchase-draft', purchaseData)
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
                      id: this.router.snapshot.params['id'],
                    });
                  }

                  PaymentSlipHelper.generatePurchasePaymentSlipPDF({
                    ...purchaseData,
                    createdAt: new Date(),
                    amount: paymentData.amount,
                    paymentDate: dueDateFormatted,
                    payments: [],
                    total: paymentData.amount,
                    bankNameOrigin: '',
                    bankAccountNameOrigin: '',
                    bankAccountNumberOrigin: '',
                  });

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
                    // Lihat keterangan pada jalur di bawah: `bankAccountID`
                    // yang menjadi `null` melempar TypeError pada
                    // validatornya.
                    createPayment: false,
                    bankAccountID: '',
                  });

                  this.stepper!.selectedIndex = 0;
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
      /*
       * Konversi memakai endpoint yang SAMA dengan cabang berpembayaran.
       *
       * Sebelumnya cabang ini menembak `POST purchases` langsung, sehingga
       * pembeliannya jadi tetapi draftnya tidak pernah ditutup — draft yang
       * sama tetap duduk di daftar tertunda dan bisa dikonversi lagi menjadi
       * pembelian kedua. `PUT purchase-draft` membuat pembelian dan menutup
       * draftnya dalam satu langkah.
       */
      this.apiService
        .put('purchase-draft', purchaseData)
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
              // tidak disebut, dan `documentType` wajib diisi.
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
               * `bankAccountID` WAJIB disebut.
               *
               * Tanpa ini nilainya menjadi `null`, sedangkan
               * `bankAccountIDRequired()` memanggil `.toString()` atasnya —
               * menyalakan sakelar slip pembayaran sesudah satu berkas
               * tersimpan melempar TypeError dan formulirnya berhenti.
               */
              createPayment: false,
              bankAccountID: '',
            });

            this.stepper!.selectedIndex = 0;
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

  fetchPurchaseDraft() {
    this.apiService
      .get(`purchase-draft/${this.router.snapshot.params['id']}`, {})
      .subscribe({
        next: (data: any) => {
          this.metaFormGroup.patchValue({
            date: new Date(data.date),
            supplierID: data.supplier_id,
            supplierName: data.supplier_name,
            supplierAddress: data.supplier_address,
            total: data.dpp + (data.ppn * data.dpp) / 100 + data.pbbkb,
            purchaseOrderName: data.purchaseOrderName,
            purchaseType: data.purchaseType,
            projectName: data.projectName,
            description: data.description,
          });

          this.valueFormGroup.patchValue({
            dpp: data.dpp,
            ppn: data.ppn,
            pbbkb: data.pbbkb,
          });
        },
        error: (error) => {
          this.snackBar.open(
          this.serverMessage.terjemahkan(error), 'Close', {
            duration: 3000,
          });
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

  get isValid() {
    return (
      this.metaFormGroup.valid &&
      this.valueFormGroup.valid &&
      this.attachmentFormGroup.valid &&
      this.paymentFormGroup.valid
    );
  }
}
