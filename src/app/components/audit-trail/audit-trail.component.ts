import { CommonModule } from '@angular/common';
import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { TranslatePipe } from '@ngx-translate/core';
import { ApiService } from '../../services/api.service';
import { AvatarComponent } from '../avatar/avatar.component';

/**
 * Satu baris perubahan yang ditampilkan.
 *
 * `sisa` hanya terisi pada baris rangkuman di ujung daftar, ketika
 * perubahannya lebih banyak daripada yang ditampilkan.
 */
export interface BarisPerubahan {
  field: string;
  from: string;
  to: string;
  sisa?: number;
}

interface AuditEntry {
  id: number;
  entity: string;
  entityID: number;
  action: string;
  userID: number | null;
  userName: string | null;
  changes: Record<string, { from: unknown; to: unknown }> | null;
  note: string | null;
  createdAt: string;
}

/**
 * Riwayat perubahan satu dokumen.
 *
 * Dipasang di dalam tampilan detail mana pun; cukup menyebut entitas dan
 * id-nya, sehingga tidak perlu komponen terpisah per modul.
 */
@Component({
  selector: 'app-audit-trail',
  standalone: true,
  imports: [
    CommonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    TranslatePipe,
    AvatarComponent,
  ],
  templateUrl: './audit-trail.component.html',
  styleUrl: './audit-trail.component.scss',
})
export class AuditTrailComponent implements OnChanges {
  /** Nama tabel, mis. 'purchase_orders'. */
  @Input() entity!: string;
  @Input() entityId!: number;
  @Input() limit = 20;

  entries: AuditEntry[] = [];
  isLoading = false;
  hasError = false;

  constructor(private apiService: ApiService) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['entity'] || changes['entityId']) this.fetch();
  }

  private fetch(): void {
    if (!this.entity || !this.entityId) return;
    this.isLoading = true;
    this.hasError = false;

    this.apiService
      .get(`audit-logs/${this.entity}/${this.entityId}`, {
        limit: this.limit,
      })
      .subscribe({
        next: (res: any) => {
          this.entries = res?.data ?? [];
          this.isLoading = false;
        },
        error: () => {
          // Riwayat adalah pelengkap; kegagalan memuatnya tidak boleh
          // membuat tampilan detail ikut gagal.
          this.hasError = true;
          this.isLoading = false;
        },
      });
  }

  /** Ikon dan warna dipilih dari jenis aksinya. */
  icon(action: string): string {
    switch (action) {
      case 'create':
        return 'add_circle_outline';
      case 'approve':
        return 'check_circle_outline';
      case 'reject':
        return 'cancel';
      case 'delete':
      case 'contract_delete':
        return 'delete_outline';
      case 'contract_create':
        return 'note_add';
      case 'contract_update':
        return 'edit_note';
      case 'move_date':
        return 'event_repeat';
      case 'update_status':
      case 'update_payment_status':
        return 'sync_alt';
      default:
        return 'edit';
    }
  }

  actionKey(action: string): string {
    return `audit.${action}`;
  }

  /** Daftar kolom yang berubah, siap ditampilkan. */
  /**
   * Daftar perubahan yang siap ditampilkan.
   *
   * Kolom JSON — `customData` pada purchase order yang paling besar — dulu
   * dirangkai `JSON.stringify` menjadi SATU baris sepanjang ribuan aksara.
   * Hasilnya bukan sekadar jelek: baris itu tidak dapat dipatahkan peramban,
   * sehingga seluruh dialog ikut melebar dan muncul penggulung mendatar; dan
   * yang membacanya tetap tidak tahu apa yang berubah, karena satu tanggal
   * yang berganti tenggelam di antara empat puluh kunci yang tidak berubah.
   *
   * Karena itu nilai bersarang DIBANDINGKAN sampai daunnya, dan yang
   * ditampilkan hanya kunci yang benar-benar berbeda —
   * `customData.workEnd  17:00 → 18:00`, bukan seluruh isinya.
   */
  changeList(entry: AuditEntry): BarisPerubahan[] {
    if (!entry.changes) return [];

    const hasil: BarisPerubahan[] = [];
    for (const [field, v] of Object.entries(entry.changes)) {
      // Penanda bukan perubahan nilai; ditampilkan tersendiri, bukan sebagai
      // baris "dari — ke —" yang tidak berarti apa pun.
      if (field === 'selfApproved') continue;

      const dari = v?.from;
      const ke = v?.to;

      if (this.bersarang(dari) || this.bersarang(ke)) {
        const rinci = this.bedaBersarang(field, dari, ke);
        if (rinci.length) {
          hasil.push(...rinci);
          continue;
        }
        // Keduanya bersarang tetapi tidak ada daun yang berbeda: tidak ada
        // yang perlu ditampilkan. Menampilkan seluruh isinya di sini justru
        // mengembalikan persoalan yang hendak dihindari.
        continue;
      }

      /*
       * Nilai datar pun dibandingkan UTUH lebih dulu.
       *
       * Backend memang hanya mencatat kolom yang berubah, sehingga baris ini
       * hampir selalu terpakai. Yang dijaga keadaan sisanya: dua nilai
       * panjang yang berbeda hanya pada bagian akhirnya akan tercetak sebagai
       * "X… → X…" — dua sisi yang tampak persis sama, dan itu terbaca seperti
       * kekeliruan sistem.
       */
      const kiri = this.utuh(dari);
      const kanan = this.utuh(ke);
      if (kiri === kanan) continue;

      hasil.push({
        field,
        from: this.potong(kiri),
        to: this.potong(kanan),
      });
    }

    /*
     * Dibatasi jumlahnya.
     *
     * Penyimpanan yang menimpa seluruh isi dokumen dapat menghasilkan puluhan
     * baris sekaligus, dan daftar sepanjang itu menenggelamkan entri riwayat
     * lain di bawahnya. Yang dipotong DISEBUTKAN — daftar yang diam-diam
     * berhenti terbaca sebagai daftar yang lengkap.
     */
    if (hasil.length > this.BATAS_BARIS) {
      const sisa = hasil.length - this.BATAS_BARIS;
      const dipotong = hasil.slice(0, this.BATAS_BARIS);
      dipotong.push({ field: '', from: '', to: '', sisa });
      return dipotong;
    }
    return hasil;
  }

  /** Nilai yang punya isi di dalamnya, sehingga dapat dibandingkan per bagian. */
  private bersarang(nilai: unknown): boolean {
    return typeof nilai === 'object' && nilai !== null;
  }

  /**
   * Ratakan objek/array menjadi peta jalur -> nilai daun.
   *
   * Array ikut diratakan dengan indeksnya, bukan diperlakukan sebagai satu
   * nilai utuh: `additionalClauses` berisi kalimat panjang, dan sebagai satu
   * nilai, satu kalimat yang berubah membuat seluruh daftar terbaca berubah.
   */
  private ratakan(
    nilai: unknown,
    awalan: string,
    keluar: Map<string, unknown>,
  ): void {
    if (!this.bersarang(nilai)) {
      keluar.set(awalan, nilai);
      return;
    }
    if (Array.isArray(nilai)) {
      if (!nilai.length) keluar.set(awalan, '[]');
      nilai.forEach((x, i) => this.ratakan(x, `${awalan}[${i}]`, keluar));
      return;
    }
    const isi = Object.entries(nilai as Record<string, unknown>);
    if (!isi.length) keluar.set(awalan, '{}');
    for (const [k, x] of isi) this.ratakan(x, `${awalan}.${k}`, keluar);
  }

  private bedaBersarang(
    field: string,
    dari: unknown,
    ke: unknown,
  ): BarisPerubahan[] {
    const a = new Map<string, unknown>();
    const b = new Map<string, unknown>();
    this.ratakan(dari, field, a);
    this.ratakan(ke, field, b);

    const jalur = Array.from(new Set([...a.keys(), ...b.keys()])).sort();
    const hasil: BarisPerubahan[] = [];
    for (const j of jalur) {
      /*
       * Dibandingkan UTUH, dipotong hanya untuk ditampilkan.
       *
       * Sebelumnya keduanya dipotong lebih dulu, sehingga dua nilai yang
       * seratus enam puluh aksara pertamanya sama dianggap tidak berubah.
       * Pada catatan dan klausul tambahan PO-D — keduanya paragraf bebas —
       * membetulkan kalimat TERAKHIR tidak menghasilkan satu baris pun; dan
       * bila itu satu-satunya yang berubah, seluruh daftar ikut disembunyikan
       * oleh `@if (changeList(e).length)`. Catatannya lalu berbunyi "Ubah",
       * oleh siapa, dan pada jam berapa — tanpa menyebut apa yang diubah.
       */
      const kiri = this.utuh(a.get(j));
      const kanan = this.utuh(b.get(j));
      if (kiri === kanan) continue;
      hasil.push({ field: j, from: this.potong(kiri), to: this.potong(kanan) });
    }
    return hasil;
  }

  /**
   * Dokumen ini disetujui oleh orang yang membuatnya.
   *
   * Hanya mungkin dilakukan pemilik usaha dan memang diizinkan, tetapi harus
   * terbaca sebagai keadaan yang berbeda saat riwayat ditelusuri — bukan
   * tenggelam di antara persetujuan biasa.
   */
  disetujuiSendiri(entry: AuditEntry): boolean {
    return (entry.changes as any)?.selfApproved === true;
  }

  /** Jumlah baris perubahan yang ditampilkan sebelum sisanya dirangkum. */
  private readonly BATAS_BARIS = 12;

  /** Panjang satu nilai sebelum dipotong; yang dipotong ditandai dengan elipsis. */
  private readonly BATAS_AKSARA = 160;

  /** Nilai sebagai teks UTUH; inilah yang dibandingkan. */
  private utuh(value: unknown): string {
    if (value === null || value === undefined || value === '') return '—';
    if (typeof value === 'boolean') return value ? 'Ya' : 'Tidak';
    return typeof value === 'object' ? JSON.stringify(value) : String(value);
  }

  /**
   * Potong untuk DITAMPILKAN saja.
   *
   * Perbandingan sampai daun sudah membuat nilai panjang jarang, tetapi satu
   * klausa kontrak sepanjang paragraf masih mungkin — dan dua paragraf
   * berdampingan di dalam satu entri membuat entri di bawahnya tidak terlihat
   * sama sekali.
   */
  private potong(teks: string): string {
    return teks.length > this.BATAS_AKSARA
      ? `${teks.slice(0, this.BATAS_AKSARA)}…`
      : teks;
  }

}
