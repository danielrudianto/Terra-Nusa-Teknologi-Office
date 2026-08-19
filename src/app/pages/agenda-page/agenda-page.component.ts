import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';

import { ApiService } from '../../services/api.service';
import { HeaderTitleComponent } from '../../components/header-title/header-title.component';
import { ReminderCreateComponent } from '../dashboard/reminder-create/reminder-create.component';
import { tanggalLokal } from '../../utils/tanggal';

interface Acara {
  jenis: 'birthday' | 'reminder';
  judul: string;
  keterangan: string;
  kategori?: string;
  reminder?: any;
}

interface Sel {
  tanggal: Date;
  kunci: string;
  hari: number;
  bulanIni: boolean;
  hariIni: boolean;
  acara: Acara[];
}

/**
 * Kalender agenda bulanan.
 *
 * Dashboard hanya menampilkan tujuh hari ke depan sebagai daftar. Halaman ini
 * menjawab pertanyaan yang tidak bisa dijawab daftar itu: tanggal berapa ada
 * apa, dan bulan depan seperti apa.
 */
@Component({
  selector: 'app-agenda-page',
  standalone: true,
  imports: [
    CommonModule,
    MatIconModule,
    MatButtonModule,
    MatSnackBarModule,
    TranslatePipe,
    HeaderTitleComponent,
  ],
  templateUrl: './agenda-page.component.html',
  styleUrl: './agenda-page.component.scss',
})
export class AgendaPageComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly translate = inject(TranslateService);

  readonly memuat = signal(false);
  readonly kursor = signal(new Date());
  readonly dipilih = signal<string | null>(null);

  private readonly _acara = signal<Map<string, Acara[]>>(new Map());

  readonly namaHari = ['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min'];

  ngOnInit(): void {
    this.muat();
  }

  /**
   * Petak enam pekan, mulai Senin.
   *
   * Selalu enam pekan meski bulannya cukup lima: tinggi kalender yang
   * berubah-ubah tiap bulan membuat isinya melompat saat berpindah bulan.
   */
  readonly petak = computed<Sel[]>(() => {
    const k = this.kursor();
    const awalBulan = new Date(k.getFullYear(), k.getMonth(), 1);
    const geser = (awalBulan.getDay() + 6) % 7;
    const mulai = new Date(awalBulan);
    mulai.setDate(mulai.getDate() - geser);

    const hariIni = tanggalLokal(new Date());
    const peta = this._acara();
    const sel: Sel[] = [];

    for (let i = 0; i < 42; i++) {
      const t = new Date(mulai);
      t.setDate(mulai.getDate() + i);
      const kunci = tanggalLokal(t)!;
      sel.push({
        tanggal: t,
        kunci,
        hari: t.getDate(),
        bulanIni: t.getMonth() === k.getMonth(),
        hariIni: kunci === hariIni,
        acara: peta.get(kunci) ?? [],
      });
    }
    return sel;
  });

  readonly judulBulan = computed(() => {
    const k = this.kursor();
    return k.toLocaleDateString('id-ID', { month: 'long', year: 'numeric' });
  });

  readonly acaraTerpilih = computed<Acara[]>(() => {
    const k = this.dipilih();
    return k ? (this._acara().get(k) ?? []) : [];
  });

  muat(): void {
    const k = this.kursor();
    const awalBulan = new Date(k.getFullYear(), k.getMonth(), 1);
    const geser = (awalBulan.getDay() + 6) % 7;
    const mulai = new Date(awalBulan);
    mulai.setDate(mulai.getDate() - geser);
    const akhir = new Date(mulai);
    akhir.setDate(mulai.getDate() + 41);

    this.memuat.set(true);
    this.api
      .get('agenda/range', {
        start: tanggalLokal(mulai),
        end: tanggalLokal(akhir),
      })
      .subscribe({
        next: (r: any) => {
          const peta = new Map<string, Acara[]>();
          const tambah = (kunci: string | null, a: Acara) => {
            if (!kunci) return;
            if (!peta.has(kunci)) peta.set(kunci, []);
            peta.get(kunci)!.push(a);
          };

          for (const b of r?.birthdays ?? []) {
            /*
             * Ulang tahun pasangan memakai kalimat yang BERBEDA.
             *
             * Usianya tidak dikirim untuk pasangan — untuk mengucapkan
             * selamat, tanggal dan bulan sudah cukup, dan orangnya bukan
             * karyawan perusahaan ini. Memakai kalimat yang sama menghasilkan
             * "Ulang tahun ke-undefined", yang terbaca seperti data rusak.
             *
             * Hubungannya disebut, bukan sekadar namanya: satu nama asing di
             * kalender kantor membuat yang membacanya menebak-nebak siapa.
             */
            const pasangan = b.kind === 'spouse' && b.employeeName;
            tambah(tanggalLokal(b.date), {
              jenis: 'birthday',
              judul: b.name,
              keterangan: pasangan
                ? this.translate.instant('agenda.pasanganDari', {
                    nama: b.employeeName,
                  })
                : this.translate.instant('agendaPage.birthdayOf', {
                    age: b.age,
                  }),
            });
          }
          for (const p of r?.reminders ?? []) {
            tambah(tanggalLokal(p.date), {
              jenis: 'reminder',
              judul: p.title,
              keterangan: p.note ?? '',
              kategori: p.category,
              reminder: p,
            });
          }
          this._acara.set(peta);
        },
        error: () => {
          this._acara.set(new Map());
          this.snackBar.open(
            this.translate.instant('notify.loadFailed'),
            'Close',
            { duration: 3000 },
          );
        },
      })
      .add(() => this.memuat.set(false));
  }

  geserBulan(arah: -1 | 1): void {
    const k = new Date(this.kursor());
    // Tanggal disetel 1 lebih dulu: menggeser bulan dari tanggal 31
    // melompati bulan yang lebih pendek — 31 Maret mundur satu bulan
    // menghasilkan 3 Maret, bukan Februari.
    k.setDate(1);
    k.setMonth(k.getMonth() + arah);
    this.kursor.set(k);
    this.dipilih.set(null);
    this.muat();
  }

  keHariIni(): void {
    this.kursor.set(new Date());
    this.dipilih.set(tanggalLokal(new Date()));
    this.muat();
  }

  pilih(s: Sel): void {
    this.dipilih.set(this.dipilih() === s.kunci ? null : s.kunci);
  }

  /** Buat pengingat pada tanggal tertentu. */
  buat(kunci?: string | null): void {
    this.dialog
      .open(ReminderCreateComponent, {
        data: { tanggalAwal: kunci ?? this.dipilih() ?? undefined },
        autoFocus: false,
      })
      .afterClosed()
      .subscribe((berubah) => {
        if (berubah) this.muat();
      });
  }

  ubah(a: Acara): void {
    if (!a.reminder) return;
    this.dialog
      .open(ReminderCreateComponent, { data: { reminder: a.reminder }, autoFocus: false })
      .afterClosed()
      .subscribe((berubah) => {
        if (berubah) this.muat();
      });
  }

  /** Label tanggal terpilih, untuk judul panel rincian. */
  labelDipilih(): string {
    const k = this.dipilih();
    if (!k) return '';
    return new Date(k).toLocaleDateString('id-ID', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  }

  lacakSel = (_: number, s: Sel) => s.kunci;
}
