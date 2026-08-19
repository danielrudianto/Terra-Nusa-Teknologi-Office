import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from './api.service';

export interface Birthday {
  /**
   * Id KARYAWANNYA.
   *
   * Pada ulang tahun pasangan pun yang disebut tetap id karyawan: pasangan
   * tidak punya baris sendiri, dan yang dituju saat barisnya ditekan memang
   * karyawannya.
   */
  id: number;
  /** Nama orang yang berulang tahun — karyawan atau pasangannya. */
  name: string;
  day: number;
  month: number;
  daysUntil: number;
  /**
   * Siapa yang berulang tahun.
   *
   * Tanpa penanda ini layar tidak dapat membedakan "Budi ulang tahun" dari
   * "istri Budi ulang tahun", dan keduanya menuntut kalimat yang berbeda.
   *
   * Opsional: jawaban dari backend yang belum diperbarui tidak memuatnya,
   * dan pada keadaan itu seluruh entri diperlakukan sebagai karyawan —
   * persis perilaku sebelumnya.
   */
  kind?: 'employee' | 'spouse';
  /** Nama karyawannya; hanya terisi bila `kind` bernilai `spouse`. */
  employeeName?: string | null;
}

export interface ReminderTarget {
  id: number;
  name: string;
}

export interface Reminder {
  id: number;
  title: string;
  note: string | null;
  date: string;
  category: string;
  isShared: boolean;
  createdBy: number;
  createdByName: string | null;
  targets: ReminderTarget[];
  daysUntil: number;
}

export interface AgendaResponse {
  birthdays: Birthday[];
  reminders: Reminder[];
}

export interface ReminderPayload {
  title: string;
  note?: string | null;
  date: string;
  category: string;
  isShared: boolean;
  targets: number[];
}

/**
 * Agenda: ulang tahun rekan dan pengingat.
 *
 * Keduanya diambil dalam satu permintaan karena selalu ditampilkan bersama;
 * memisahkannya berarti satu blok menunggu dua jawaban.
 */
@Injectable({ providedIn: 'root' })
export class AgendaService {
  private readonly api = inject(ApiService);

  /** Isi agenda untuk beberapa hari ke depan. */
  load(days = 7): Observable<AgendaResponse> {
    return this.api.get('agenda', { days }) as Observable<AgendaResponse>;
  }

  /**
   * Kategori yang dikenali server.
   *
   * Diambil dari server, tidak disalin ke layar: dua salinan berarti suatu
   * saat salah satunya diperbarui sendirian, dan pilihan yang tampil tidak
   * lagi sama dengan yang diterima.
   */
  categories(): Observable<{ categories: string[] }> {
    return this.api.get('agenda/categories', {}) as Observable<{
      categories: string[];
    }>;
  }

  /**
   * Orang yang dapat ditandai.
   *
   * Endpoint tersendiri, bukan daftar pengguna biasa: daftar itu dijaga
   * `user:read` yang berada di akses 5, sehingga staf tidak akan melihat
   * satu nama pun. Server juga sudah mengecualikan peminta, sehingga layar
   * tidak perlu menyaring diri sendiri — dan tidak bergantung pada data
   * pengguna yang tersimpan di peramban.
   */
  taggableUsers(): Observable<{ users: { id: number; name: string }[] }> {
    return this.api.get('agenda/taggable-users', {}) as Observable<{
      users: { id: number; name: string }[];
    }>;
  }

  create(body: ReminderPayload) {
    return this.api.post('agenda/reminders', body);
  }

  update(id: number, body: Partial<ReminderPayload>) {
    return this.api.put(`agenda/reminders/${id}`, body);
  }

  remove(id: number) {
    return this.api.delete(`agenda/reminders/${id}`);
  }
}
