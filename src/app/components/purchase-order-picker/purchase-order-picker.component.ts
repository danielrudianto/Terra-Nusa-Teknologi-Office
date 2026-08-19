import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { TranslatePipe } from '@ngx-translate/core';
import { debounceTime } from 'rxjs';

import { DialogGeserDirective } from '../../directives/dialog-geser.directive';
import { ApiService } from '../../services/api.service';
import { namaPemasokBaris } from '../../helpers/purchase-order-shared.helper';

/**
 * Pilih purchase order yang akan ditagih, lalu salin datanya ke pembelian.
 *
 * Dokumen pembelian mengulang hampir seluruh isi purchase order-nya: pemasok,
 * proyek, jenis biaya, DPP, dan tarif pajaknya. Mengetiknya ulang bukan hanya
 * lambat — angka yang diketik ulang dapat berbeda dari dokumen yang
 * ditandatangani, dan selisihnya baru ketahuan saat rekonsiliasi.
 *
 * Dokumen DRAF tetap ditawarkan. Tagihan kerap datang sebelum persetujuan
 * internal selesai, dan menyembunyikannya memaksa yang mencatat kembali
 * mengetik manual — persis keadaan yang hendak dihindari. Statusnya ditandai
 * pada tiap baris.
 */
@Component({
  selector: 'app-purchase-order-picker',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    DialogGeserDirective,
    TranslatePipe,
  ],
  templateUrl: './purchase-order-picker.component.html',
  styleUrls: ['./purchase-order-picker.component.scss'],
})
export class PurchaseOrderPickerComponent implements OnInit {
  private readonly apiService = inject(ApiService);
  private readonly dialogRef = inject(
    MatDialogRef<PurchaseOrderPickerComponent>,
  );

  readonly searchBar = new FormControl('');

  daftar: any[] = [];
  jumlah = 0;
  page = 0;
  isLoading = false;

  /** Sepuluh baris per halaman; dikirim sebagai `page_size`. */
  readonly ukuranHalaman = 10;

  /** Nomor baris pertama pada halaman ini, dihitung dari satu. */
  get awalBaris(): number {
    return this.jumlah === 0 ? 0 : this.page * this.ukuranHalaman + 1;
  }

  /**
   * Nomor baris terakhir.
   *
   * Dibatasi `jumlah`: pada halaman terakhir isinya biasanya kurang dari
   * sepuluh, dan menulis "51–60 dari 54" membuat angkanya tidak dipercaya.
   */
  get akhirBaris(): number {
    return Math.min((this.page + 1) * this.ukuranHalaman, this.jumlah);
  }

  ngOnInit(): void {
    this.cari(0);
    this.searchBar.valueChanges
      .pipe(debounceTime(400))
      .subscribe(() => this.cari(0));
  }

  cari(halaman: number): void {
    // Dijaga agar tidak negatif: tombol sebelumnya dimatikan pada halaman
    // pertama, tetapi `cari()` juga dipanggil dari tempat lain.
    this.page = Math.max(0, halaman);
    this.isLoading = true;
    this.apiService
      .get('purchase-orders/', {
        keyword: (this.searchBar.value || '').trim(),
        page: this.page + 1,
        // `page_size`, bukan `pageSize`. FastAPI mencocokkan nama persis dan
        // membuang yang tidak dikenal tanpa galat — nilainya diam-diam jatuh
        // ke bawaan 10, sehingga mengubah angka di sini tidak berpengaruh apa
        // pun.
        page_size: this.ukuranHalaman,
      })
      .subscribe({
        next: (res: any) => {
          this.daftar = res?.data ?? [];
          this.jumlah = res?.count ?? 0;
        },
        error: () => {
          this.daftar = [];
          this.jumlah = 0;
        },
      })
      .add(() => {
        this.isLoading = false;
      });
  }

  /**
   * Nama pemasok beserta awalannya, seperti tercetak pada dokumen.
   *
   * Nama bidangnya TIDAK disebut di sini. `namaPemasokBaris` yang
   * mengetahuinya, dan ia satu-satunya yang mengetahuinya — sebab penamaan
   * itu pernah berbeda antara kueri daftar dan kueri satu dokumen, dan
   * perbedaannya hanya terlihat sebagai kolom kosong.
   */
  pemasok(po: any): string {
    const hasil = namaPemasokBaris(po);
    return hasil === '-' ? '—' : hasil;
  }

  sudahDisetujui(po: any): boolean {
    return (
      !!po?.isApproved || String(po?.status || '').toLowerCase() === 'approved'
    );
  }

  angka(v: unknown): number {
    const n = Number(v);
    return isNaN(n) ? 0 : n;
  }

  tutup(): void {
    this.dialogRef.close();
  }

  pilih(po: any): void {
    /*
     * Yang dikembalikan hanya bidang yang BENAR-BENAR dipakai pembelian.
     *
     * Mengembalikan seluruh dokumen membuat pemanggil tergoda menyalin
     * bidang lain yang artinya berbeda di sana — `date` purchase order
     * adalah tanggal terbit dokumennya, bukan tanggal faktur pemasok.
     */
    this.dialogRef.close({
      // Id ikut dibawa agar dokumennya dapat dibuka kembali dari formulir
      // pembelian untuk diperiksa. Nomornya tidak cukup: rute yang memuat
      // satu purchase order menerima id, bukan nomor.
      id: po?.id ?? null,
      purchaseOrderName: po?.name ?? '',
      supplierID: po?.supplierID ?? null,
      supplierName: po?.supplierName ?? po?.supplier_name ?? '',
      // Alamat ikut dibawa: dokumen pembelian mencetaknya, dan pemilihan
      // lewat pencarian pemasok biasa sudah mengisinya. Tanpa ini, pembelian
      // yang dibuat dari purchase order tercetak tanpa alamat.
      supplierAddress: po?.supplierAddress ?? '',
      projectName: po?.projectName ?? '',
      purchaseType: po?.purchaseType ?? '',
      dpp: this.angka(po?.dpp),
      ppn: this.angka(po?.ppn),
      pphCode: po?.pphCode ?? '',
      pphTaxObject: po?.pphTaxObject ?? '',
      pphPercentage: this.angka(po?.pphPercentage),
    });
  }
}
