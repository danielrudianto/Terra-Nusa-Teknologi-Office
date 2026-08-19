import { CommonModule } from '@angular/common';
import { Component, Inject, OnInit } from '@angular/core';
import {
  FormArray,
  FormBuilder,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';

import { ApiService } from 'src/app/services/api.service';
import { ServerMessageService } from 'src/app/services/server-message.service';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { banks, IBank } from 'src/app/utils/bank';
import { tanggalLokal } from 'src/app/utils/tanggal';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { DialogGeserDirective } from '../../../directives/dialog-geser.directive';

@Component({
  selector: 'app-employee-profile',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    TranslatePipe,
    MatDatepickerModule,
    MatNativeDateModule,
    MatAutocompleteModule,
    MatSlideToggleModule,
    DialogGeserDirective,
  ],
  templateUrl: './employee-profile.component.html',
  styleUrl: './employee-profile.component.scss',
})
export class EmployeeProfileComponent implements OnInit {
  constructor(
    @Inject(MAT_DIALOG_DATA)
    // `nik` ikut diteruskan agar dapat ditampilkan tanpa memanggil server
    // lagi — daftarnya sudah memuatnya.
    public input: { id: number; name?: string; nik?: string },
    private dialogRef: MatDialogRef<EmployeeProfileComponent>,
    private formBuilder: FormBuilder,
    private apiService: ApiService,
    private snackBar: MatSnackBar,
    private serverMessage: ServerMessageService,
    private translate: TranslateService,
  ) {}

  isLoading = true;
  /** True bila profil ini belum pernah ada sebelum dialog dibuka. */
  pertamaKali = false;

  isSubmitting = false;

  /** True bila karyawan ini belum pernah punya profil. */
  baru = false;

  /*
   * Riwayat perubahan profil.
   *
   * Dimuat HANYA ketika diminta, bukan bersama profilnya. Sebagian besar
   * pembukaan dialog ini adalah pengisian atau pembacaan biasa, dan riwayat
   * yang ikut ditarik setiap kali menambah satu permintaan berisi data
   * pribadi yang tidak ada yang membacanya.
   */
  riwayat: any[] = [];
  riwayatDibuka = false;
  memuatRiwayat = false;

  /**
   * Pemuatannya GAGAL — dibedakan dari riwayat yang memang kosong.
   *
   * Keduanya sama-sama menghasilkan daftar kosong, tetapi yang dikatakan
   * kepada yang membaca berbeda jauh: "belum pernah diubah" adalah pernyataan
   * TENTANG catatannya, dan pada layar audit pernyataan itu tidak boleh
   * diucapkan hanya karena satu permintaan gagal.
   */
  gagalRiwayat = false;

  /**
   * Entri yang benar-benar punya isi.
   *
   * Backend menyimpan satu baris setiap kali profil disimpan, termasuk
   * penyimpanan yang tidak mengubah apa pun — dan `changedFields`-nya kosong.
   * Tanpa saringan ini, menekan Simpan tanpa menyunting apa pun melahirkan
   * kartu berisi nama dan jam saja: catatan audit yang menyatakan ada
   * perubahan, padahal tidak ada.
   */
  get riwayatBerisi(): any[] {
    return this.riwayat.filter((e) => e?.changedFields?.length);
  }

  bukaRiwayat(): void {
    this.riwayatDibuka = !this.riwayatDibuka;
    if (!this.riwayatDibuka || this.riwayat.length || this.memuatRiwayat) {
      return;
    }

    this.memuatRiwayat = true;
    this.gagalRiwayat = false;
    this.apiService
      .get(`employee-profiles/${this.input.id}/riwayat`, {})
      .subscribe({
        next: (r: any) => (this.riwayat = Array.isArray(r) ? r : []),
        // Gagal memuat riwayat TIDAK menghalangi penyuntingan; hanya
        // pembandingnya yang tidak muncul — dan kegagalannya dikatakan apa
        // adanya, bukan disamarkan sebagai "belum pernah diubah".
        error: () => {
          this.riwayat = [];
          this.gagalRiwayat = true;
        },
      })
      .add(() => (this.memuatRiwayat = false));
  }

  /** Kunci terjemahan nama kolom; sama dengan yang dipakai isian formulirnya. */
  labelKolom(kolom: string): string {
    return `employeeProfile.${kolom}`;
  }

  /**
   * Nilai sebuah kolom pada keadaan sebelum perubahan.
   *
   * Daftar berulang — pendidikan, susunan keluarga — dirangkum jumlahnya saja.
   * Membentangkannya di dalam riwayat membuat satu perubahan alamat tenggelam
   * di antara dua puluh baris yang tidak berubah.
   */
  nilaiLama(entri: any, kolom: string): string {
    const nilai = entri?.snapshot?.[kolom];
    if (nilai === null || nilai === undefined || nilai === '') return '—';
    if (Array.isArray(nilai)) {
      return this.translate.instant('employeeProfile.riwayatDaftar', {
        n: nilai.length,
      });
    }
    return String(nilai);
  }

  /*
   * Bagian yang dapat dibuka-tutup, disusun sendiri.
   *
   * Formulirnya panjang — dua puluh isian ditambah dua daftar berulang.
   * Ditumpuk sekaligus, penggunanya tidak tahu sudah sampai mana dan mana
   * yang masih kosong, sehingga mengisi asal supaya cepat selesai.
   *
   * Satu bagian terbuka pada satu waktu, seperti akordeon: dua bagian
   * terbuka bersamaan mengembalikan masalah yang sama dalam bentuk lebih
   * kecil.
   */
  readonly bagian = [
    { kunci: 'identitas', ikon: 'person', judul: 'employeeProfile.identity' },
    { kunci: 'kependudukan', ikon: 'badge', judul: 'employeeProfile.idCard' },
    { kunci: 'kontak', ikon: 'home', judul: 'employeeProfile.contact' },
    { kunci: 'keluarga', ikon: 'family_restroom', judul: 'employeeProfile.family' },
    { kunci: 'jaminan', ikon: 'account_balance', judul: 'employeeProfile.social' },
    { kunci: 'pendidikan', ikon: 'school', judul: 'employeeProfile.education' },
    { kunci: 'bahasa', ikon: 'translate', judul: 'employeeProfile.languages' },
    { kunci: 'pengalaman', ikon: 'work_history', judul: 'employeeProfile.experience' },
  ];

  terbuka = 'identitas';

  /** Isian milik tiap bagian; dipakai menghitung kelengkapannya. */
  private readonly isiBagian: Record<string, string[]> = {
    identitas: [
      'birthPlace',
      'gender',
      'bloodType',
      'religion',
      'maritalStatus',
      'citizenship',
      'ethnicity',
      'heightCm',
      'weightKg',
    ],
    kependudukan: ['ktpAddress'],
    kontak: ['homeOwnership', 'homePhone'],
    keluarga: ['motherName', 'fatherName'],
    jaminan: [
      'bpjsKesehatan',
      'bpjsKetenagakerjaan',
      'bankName',
      'bankAccountName',
      'bankAccountNumber',
    ],
  };

  // Golongan D tidak dipakai: tidak ada yang memerlukannya di sini.
  readonly golonganSim = ['A', 'B1', 'B2', 'C'];

  readonly kepemilikanRumah = [
    { value: 'pribadi', key: 'employeeProfile.ownOwn' },
    { value: 'orangtua', key: 'employeeProfile.ownParents' },
    { value: 'kontrak', key: 'employeeProfile.ownRent' },
  ];

  readonly kemampuan = [
    { value: 'aktif', key: 'employeeProfile.active' },
    { value: 'pasif', key: 'employeeProfile.passive' },
  ];

  readonly hubunganKeluarga = [
    { value: 'pasangan', key: 'employeeProfile.spouse' },
    { value: 'anak', key: 'employeeProfile.child' },
    { value: 'saudara', key: 'employeeProfile.sibling' },
  ];

  bukaBagian(kunci: string): void {
    // Menekan bagian yang sedang terbuka menutupnya, sehingga seluruh
    // bagian dapat ditutup untuk melihat ikhtisarnya sekaligus.
    this.terbuka = this.terbuka === kunci ? '' : kunci;
  }

  /**
   * Berapa isian yang sudah terisi pada satu bagian.
   *
   * Ditampilkan di kepala tiap bagian supaya yang masih kosong terlihat
   * tanpa perlu membukanya satu per satu.
   */
  terisi(kunci: string): number {
    if (kunci === 'pendidikan') return this.barisTerisi(this.pendidikan);
    if (kunci === 'pengalaman') return this.barisTerisi(this.pengalaman);
    if (kunci === 'bahasa') return this.barisTerisi(this.bahasa);
    // Kependudukan menghitung alamat KTP DAN daftar SIM-nya.
    if (kunci === 'kependudukan') {
      return (
        (this.isiBagian['kependudukan'] || []).filter((f) =>
          ((this.formGroup.get(f)?.value ?? '') as string).toString().trim(),
        ).length + this.barisTerisi(this.sim)
      );
    }
    // Keluarga menghitung dua hal: nama orang tua DAN susunan keluarga,
    // karena keduanya ada di bagian yang sama.
    if (kunci === 'keluarga') {
      return (
        (this.isiBagian['keluarga'] || []).filter((f) =>
          ((this.formGroup.get(f)?.value ?? '') as string).toString().trim(),
        ).length + this.barisTerisi(this.anggotaKeluarga)
      );
    }
    return (this.isiBagian[kunci] || []).filter((f) =>
      ((this.formGroup.get(f)?.value ?? '') as string).toString().trim(),
    ).length;
  }

  /** Jumlah isian pada satu bagian; untuk daftar berulang, jumlah barisnya. */
  total(kunci: string): number {
    if (kunci === 'pendidikan') return this.pendidikan.length;
    if (kunci === 'pengalaman') return this.pengalaman.length;
    if (kunci === 'bahasa') return this.bahasa.length;
    if (kunci === 'kependudukan') {
      return (this.isiBagian['kependudukan'] || []).length + this.sim.length;
    }
    if (kunci === 'keluarga') {
      return (this.isiBagian['keluarga'] || []).length + this.anggotaKeluarga.length;
    }
    return (this.isiBagian[kunci] || []).length;
  }

  private barisTerisi(arr: FormArray): number {
    return (arr.getRawValue() || []).filter((b: any) =>
      Object.values(b).some((x) => (x ?? '').toString().trim() !== ''),
    ).length;
  }

  readonly jenisKelamin = [
    { value: 'L', key: 'employeeProfile.male' },
    { value: 'P', key: 'employeeProfile.female' },
  ];

  readonly golonganDarah = ['A', 'B', 'AB', 'O'];

  readonly agama = [
    'Islam',
    'Kristen',
    'Katolik',
    'Hindu',
    'Buddha',
    'Konghucu',
  ];

  readonly statusNikah = [
    { value: 'lajang', key: 'employeeProfile.single' },
    { value: 'menikah', key: 'employeeProfile.married' },
    { value: 'cerai', key: 'employeeProfile.divorced' },
  ];

  readonly jenjang = ['SD', 'SMP', 'SMA/SMK', 'D3', 'S1', 'S2', 'S3'];

  /*
   * Jenjang yang mengenal IPK.
   *
   * SD, SMP, dan SMA tidak memakai IPK — kolomnya hanya membuat yang
   * mengisi bertanya-tanya apa yang harus ditulis, lalu mengarang.
   */
  private readonly berIPK = ['D3', 'S1', 'S2', 'S3'];

  /** Jenjang yang mengenal jurusan. SD dan SMP tidak. */
  private readonly berJurusan = ['SMA/SMK', 'D3', 'S1', 'S2', 'S3'];

  /*
   * Nilai penanda "tidak dapat dicantumkan".
   *
   * Disimpan sebagai TEKS pada kolomnya sendiri, bukan sebagai kolom boolean
   * terpisah: kolom baru berarti migrasi basis data, sedangkan yang perlu
   * dibedakan hanya "belum diisi" dari "memang tidak ada".
   *
   * Keduanya berbeda artinya. Kosong berarti belum sempat diisi dan masih
   * perlu ditanyakan; penanda ini berarti sudah ditanyakan dan jawabannya
   * memang tidak ada — sehingga tidak perlu ditanyakan lagi.
   */
  static readonly TIDAK_ADA = '-';

  /** True bila baris pendidikan ini ditandai tidak ber-IPK. */
  ipkTidakAda(i: number): boolean {
    return (
      this.barisPendidikan(i).get('gpa')?.value ===
      EmployeeProfileComponent.TIDAK_ADA
    );
  }

  /**
   * Tandai bahwa jenjang ini tidak menerbitkan IPK.
   *
   * Isian IPK-nya dimatikan, bukan disembunyikan: yang mengisi tetap perlu
   * melihat bahwa kolom itu ada dan sengaja dilewati.
   */
  toggleIpkTidakAda(i: number): void {
    const c = this.barisPendidikan(i).get('gpa');
    if (!c) return;
    if (this.ipkTidakAda(i)) {
      c.enable({ emitEvent: false });
      c.setValue('', { emitEvent: false });
    } else {
      c.setValue(EmployeeProfileComponent.TIDAK_ADA, { emitEvent: false });
      c.disable({ emitEvent: false });
    }
  }

  /** True bila golongan darahnya ditandai tidak diketahui. */
  get darahTidakTahu(): boolean {
    return (
      this.formGroup.get('bloodType')?.value ===
      EmployeeProfileComponent.TIDAK_ADA
    );
  }

  /**
   * Tandai bahwa golongan darahnya tidak diketahui.
   *
   * Sebagian orang memang tidak pernah mengetahuinya, dan membiarkannya
   * kosong membuat pengisinya ditanya berulang kali oleh siapa pun yang
   * memeriksa kelengkapan berikutnya.
   */
  toggleDarahTidakTahu(): void {
    const c = this.formGroup.get('bloodType');
    if (!c) return;
    if (this.darahTidakTahu) {
      c.enable({ emitEvent: false });
      c.setValue('', { emitEvent: false });
    } else {
      c.setValue(EmployeeProfileComponent.TIDAK_ADA, { emitEvent: false });
      c.disable({ emitEvent: false });
    }
  }

  punyaIPK(i: number): boolean {
    return this.berIPK.includes(this.barisPendidikan(i).get('level')?.value);
  }

  punyaJurusan(i: number): boolean {
    return this.berJurusan.includes(this.barisPendidikan(i).get('level')?.value);
  }

  /*
   * Bahasa sebagai pilihan, bukan ketikan bebas.
   *
   * Ketikan bebas menghasilkan "Inggris", "inggris", "English", dan
   * "Bhs Inggris" sebagai empat bahasa berbeda — dan tidak ada satu pun
   * daftar yang dapat dipercaya sesudahnya.
   */
  /**
   * Daftar bank yang SAMA dengan yang dipakai pembelian dan pembayaran.
   *
   * Diambil dari `utils/bank`, bukan ditulis ulang di sini: daftar terpisah
   * berarti dua daftar yang harus diperbarui bersamaan, dan rekening yang
   * ditulis "BCA" di satu layar dan "PT Bank Central Asia Tbk." di layar lain
   * tidak dapat dicocokkan.
   */
  /**
   * Kewarganegaraan sebagai pilihan, bukan ketikan bebas.
   *
   * Cukup dua: yang dibedakan perlakuan ketenagakerjaannya memang hanya warga
   * negara Indonesia dan bukan. Negara asalnya, bila diperlukan, dicatat
   * pada kolom lain — bukan di sini.
   */
  readonly kewarganegaraan = ['WNI', 'WNA'];

  readonly daftarBank = banks;

  /**
   * Saran bank yang cocok dengan yang sedang diketik.
   *
   * Dicocokkan ke nama RESMI maupun aliasnya — orang mengetik "BCA", bukan
   * "PT Bank Central Asia Tbk.".
   */
  bankTersaring(nilai: string | null | undefined): IBank[] {
    const k = String(nilai || '').toLowerCase().trim();
    if (!k) return this.daftarBank;
    return this.daftarBank.filter(
      (b) =>
        b.name.toLowerCase().includes(k) ||
        (b.alias || '').toLowerCase().includes(k),
    );
  }

  readonly daftarBahasa = [
    // Indonesia lebih dulu: itu yang paling sering diisi, dan menaruhnya di
    // urutan pertama menghemat gulir bagi hampir semua orang.
    'Indonesia',
    'Inggris',
    'Mandarin',
    'Arab',
    'Jepang',
    'Korea',
    'Jerman',
    'Belanda',
    'Lainnya',
  ];

  /*
   * Seluruh isian OPSIONAL, kecuali panjangnya.
   *
   * Profil diisi bertahap: sebagian datanya baru tersedia setelah orangnya
   * masuk. Menolak simpan karena satu kolom belum terisi membuat yang sudah
   * diketik ikut hilang — dan yang terjadi kemudian adalah orang menunda
   * mengisi sampai datanya lengkap, lalu tidak pernah mengisinya.
   *
   * Batas panjang mengikuti kolomnya di basis data, agar isian terlalu
   * panjang ditolak di layar dan bukan setelah dikirim.
   */
  formGroup: FormGroup = new FormGroup({
    birthPlace: new FormControl('', Validators.maxLength(100)),
    gender: new FormControl(''),
    bloodType: new FormControl(''),
    religion: new FormControl(''),
    maritalStatus: new FormControl(''),
    // Nama ibu kandung kerap dipakai bank dan BPJS sebagai pertanyaan
    // verifikasi; diminta sekali di awal, bukan tiap tahun.
    motherName: new FormControl('', Validators.maxLength(150)),
    fatherName: new FormControl('', Validators.maxLength(150)),
    citizenship: new FormControl('', Validators.maxLength(50)),
    ethnicity: new FormControl('', Validators.maxLength(50)),
    // Batas atas wajar; bukan aturan medis, hanya penjaga salah ketik.
    heightCm: new FormControl<number | null>(null, [
      Validators.min(0),
      Validators.max(300),
    ]),
    weightKg: new FormControl<number | null>(null, [
      Validators.min(0),
      Validators.max(500),
    ]),

    // `ktpNumber` tidak ada: NIK adalah nomor KTP itu sendiri, dan sudah
    // tersimpan di data karyawan. Layar ini menampilkannya sebagai bacaan.
    ktpAddress: new FormControl('', Validators.maxLength(500)),
    // SIM sebagai DAFTAR bergolongan dan bernomor, bukan sekadar centang.
    //
    // Tiap golongan diterbitkan sebagai kartu tersendiri dengan nomornya
    // sendiri. Mengetahui seseorang "punya SIM A" tanpa nomornya tidak
    // menyelesaikan apa pun saat mengurus perizinan atau penugasan
    // mengemudi.
    drivingLicenses: new FormArray([]),

    // Alamat tinggal, HP, dan surel ada di data karyawan — tidak diminta
    // ulang di sini. Dua kotak untuk satu data pasti berbeda suatu saat,
    // dan tidak ada yang tahu mana yang berlaku.
    homeOwnership: new FormControl(''),
    homePhone: new FormControl('', Validators.maxLength(30)),

    bpjsKesehatan: new FormControl('', Validators.maxLength(30)),
    bpjsKetenagakerjaan: new FormControl('', Validators.maxLength(30)),

    bankName: new FormControl('', Validators.maxLength(100)),
    bankAccountName: new FormControl('', Validators.maxLength(100)),
    bankAccountNumber: new FormControl('', Validators.maxLength(50)),

    formalEducation: new FormArray([]),
    workExperience: new FormArray([]),
    languages: new FormArray([]),
    familyMembers: new FormArray([]),
  });

  ngOnInit(): void {
    this.muat();
  }

  get pendidikan(): FormArray {
    return this.formGroup.get('formalEducation') as FormArray;
  }

  get pengalaman(): FormArray {
    return this.formGroup.get('workExperience') as FormArray;
  }

  get sim(): FormArray {
    return this.formGroup.get('drivingLicenses') as FormArray;
  }

  barisSim(i: number): FormGroup {
    return this.sim.at(i) as FormGroup;
  }

  private buatSim(v: any = {}): FormGroup {
    return this.formBuilder.group({
      golongan: [v.golongan ?? ''],
      /*
       * Nomor SIM Indonesia 12–16 digit, kerap ditulis berkelompok dengan
       * tanda hubung. Batas bawah dipasang karena nomor yang terpotong
       * separuh lolos tanpa itu — dan baru ketahuan saat dipakai mengurus
       * perizinan.
       */
      nomor: [
        v.nomor ?? '',
        [Validators.minLength(12), Validators.maxLength(20)],
      ],
    });
  }

  tambahSim(): void {
    this.sim.push(this.buatSim());
  }

  hapusSim(i: number): void {
    this.sim.removeAt(i);
  }

  get bahasa(): FormArray {
    return this.formGroup.get('languages') as FormArray;
  }

  get anggotaKeluarga(): FormArray {
    return this.formGroup.get('familyMembers') as FormArray;
  }

  barisBahasa(i: number): FormGroup {
    return this.bahasa.at(i) as FormGroup;
  }

  barisKeluarga(i: number): FormGroup {
    return this.anggotaKeluarga.at(i) as FormGroup;
  }

  private buatBahasa(v: any = {}): FormGroup {
    return this.formBuilder.group({
      language: [v.language ?? '', Validators.maxLength(50)],
      // Lisan dan tulisan dicatat terpisah: banyak orang mampu membaca
      // tetapi tidak berbicara, dan satu penilaian menyembunyikan itu.
      speaking: [v.speaking ?? ''],
      writing: [v.writing ?? ''],
    });
  }

  private buatKeluarga(v: any = {}): FormGroup {
    return this.formBuilder.group({
      relation: [v.relation ?? ''],
      name: [v.name ?? '', Validators.maxLength(150)],
      birthday: [v.birthday ?? '', Validators.maxLength(20)],
      education: [v.education ?? '', Validators.maxLength(50)],
      job: [v.job ?? '', Validators.maxLength(100)],
    });
  }

  tambahBahasa(): void {
    this.bahasa.push(this.buatBahasa());
  }

  hapusBahasa(i: number): void {
    this.bahasa.removeAt(i);
  }

  tambahKeluarga(): void {
    this.anggotaKeluarga.push(this.buatKeluarga());
  }

  hapusKeluarga(i: number): void {
    this.anggotaKeluarga.removeAt(i);
  }

  barisPendidikan(i: number): FormGroup {
    return this.pendidikan.at(i) as FormGroup;
  }

  barisPengalaman(i: number): FormGroup {
    return this.pengalaman.at(i) as FormGroup;
  }

  private buatPendidikan(v: any = {}): FormGroup {
    return this.formBuilder.group({
      level: [v.level ?? '', Validators.maxLength(50)],
      school: [v.school ?? '', Validators.maxLength(200)],
      major: [v.major ?? '', Validators.maxLength(150)],
      /*
       * Tahun disimpan sebagai TEKS empat angka.
       *
       * Skema backend menyatakannya `Optional[str]`; mengirimnya sebagai
       * bilangan membuat seluruh penyimpanan ditolak 422 tanpa menyebut
       * kolom mana yang salah.
       *
       * Polanya membatasi ke empat angka, bukan sekadar panjangnya —
       * "20a5" lolos `maxLength` tetapi bukan tahun.
       */
      fromYear: [
        v.fromYear ?? '',
        [Validators.pattern(/^\d{4}$/), Validators.maxLength(4)],
      ],
      toYear: [
        v.toYear ?? '',
        [Validators.pattern(/^\d{4}$/), Validators.maxLength(4)],
      ],
      gpa: [v.gpa ?? '', Validators.maxLength(10)],
    });
  }

  private buatPengalaman(v: any = {}): FormGroup {
    return this.formBuilder.group({
      company: [v.company ?? '', Validators.maxLength(200)],
      field: [v.field ?? '', Validators.maxLength(150)],
      position: [v.position ?? '', Validators.maxLength(150)],
      fromDate: [v.fromDate ?? '', Validators.maxLength(20)],
      toDate: [v.toDate ?? '', Validators.maxLength(20)],
      reasonLeaving: [v.reasonLeaving ?? '', Validators.maxLength(500)],
    });
  }

  tambahPendidikan(): void {
    this.pendidikan.push(this.buatPendidikan());
  }

  hapusPendidikan(i: number): void {
    this.pendidikan.removeAt(i);
  }

  tambahPengalaman(): void {
    this.pengalaman.push(this.buatPengalaman());
  }

  hapusPengalaman(i: number): void {
    this.pengalaman.removeAt(i);
  }

  /**
   * Muat profil; kosong bukan galat.
   *
   * Karyawan yang sudah ada sebelum profil diperkenalkan memang belum
   * punya. Layarnya menampilkan formulir kosong, bukan pesan galat —
   * itulah cara data lama dilengkapi.
   */
  private muat(): void {
    this.apiService.get(`employee-profiles/${this.input.id}`, {}).subscribe({
      next: (data: any) => {
        /*
         * Apakah ini pengisian PERTAMA, ditentukan di sini.
         *
         * Sesudah menyimpan, profilnya selalu ada — bedanya tidak dapat
         * diketahui lagi. Karena itu ditandai saat memuat, bukan sesudah.
         */
        this.pertamaKali = !data;
        this.baru = !data;
        if (data) this.isi(data);
        this.isLoading = false;
      },
      error: (err: any) => {
        this.isLoading = false;
        this.snackBar.open(
          this.serverMessage.terjemahkan(err),
          this.translate.instant('common.close'),
          { duration: 5000 },
        );
      },
    });
  }

  private isi(d: any): void {
    this.formGroup.patchValue({
      birthPlace: d.birthPlace ?? '',
      gender: d.gender ?? '',
      bloodType: d.bloodType ?? '',
      religion: d.religion ?? '',
      maritalStatus: d.maritalStatus ?? '',
      motherName: d.motherName ?? '',
      fatherName: d.fatherName ?? '',
      citizenship: d.citizenship ?? '',
      ethnicity: d.ethnicity ?? '',
      heightCm: d.heightCm ?? null,
      weightKg: d.weightKg ?? null,
      homeOwnership: d.homeOwnership ?? '',
      homePhone: d.homePhone ?? '',
      ktpAddress: d.ktpAddress ?? '',
      bpjsKesehatan: d.bpjsKesehatan ?? '',
      bpjsKetenagakerjaan: d.bpjsKetenagakerjaan ?? '',
      bankName: d.bankName ?? '',
      bankAccountName: d.bankAccountName ?? '',
      bankAccountNumber: d.bankAccountNumber ?? '',
    });

    /*
     * JSON dari server bisa berupa string atau larik.
     *
     * Driver MySQL mengembalikan kolom JSON sebagai teks pada sebagian
     * versi; menganggapnya selalu larik membuat daftarnya kosong tanpa
     * galat apa pun, dan penggunanya mengira datanya hilang.
     */
    const urai = (x: any): any[] => {
      if (!x) return [];
      if (Array.isArray(x)) return x;
      try {
        const hasil = JSON.parse(x);
        return Array.isArray(hasil) ? hasil : [];
      } catch {
        return [];
      }
    };

    this.pendidikan.clear();
    urai(d.formalEducation).forEach((x) =>
      this.pendidikan.push(this.buatPendidikan(x)),
    );

    this.pengalaman.clear();
    urai(d.workExperience).forEach((x) =>
      this.pengalaman.push(this.buatPengalaman(x)),
    );

    this.bahasa.clear();
    urai(d.languages).forEach((x) => this.bahasa.push(this.buatBahasa(x)));

    this.anggotaKeluarga.clear();
    urai(d.familyMembers).forEach((x) =>
      this.anggotaKeluarga.push(this.buatKeluarga(x)),
    );

    this.sim.clear();
    urai(d.drivingLicenses).forEach((x: any) => {
      // Bentuk LAMA berupa daftar teks golongan saja; dibaca sebagai
      // golongan tanpa nomor supaya data yang sudah tersimpan tidak hilang.
      const baris = typeof x === 'string' ? { golongan: x } : x;
      this.sim.push(this.buatSim(baris));
    });
  }

  simpan(): void {
    if (this.formGroup.invalid || this.isSubmitting) return;
    this.isSubmitting = true;

    const v = this.formGroup.getRawValue();

    /*
     * Isian kosong dikirim sebagai null, bukan string kosong.
     *
     * Kolomnya nullable; menyimpan string kosong membuat "belum diisi" dan
     * "sengaja dikosongkan" tidak dapat dibedakan saat HRD memeriksa
     * kelengkapan.
     */
    const DAFTAR = [
      'formalEducation',
      'workExperience',
      'languages',
      'familyMembers',
      'drivingLicenses',
    ];
    const ANGKA = ['heightCm', 'weightKg'];

    const bersih: any = {};
    Object.keys(v).forEach((k) => {
      if (DAFTAR.includes(k)) return;
      if (ANGKA.includes(k)) {
        // Angka dikirim sebagai bilangan atau null, bukan string kosong —
        // server menolaknya sebagai bilangan yang tidak sah.
        const n = Number(v[k]);
        bersih[k] = v[k] === null || v[k] === '' || isNaN(n) ? null : n;
        return;
      }
      const nilai = (v[k] ?? '').toString().trim();
      bersih[k] = nilai === '' ? null : nilai;
    });

    // Baris kosong tidak ikut disimpan.
    const isiBaris = (baris: any[]) =>
      baris.filter((b) =>
        Object.values(b).some((x) => (x ?? '').toString().trim() !== ''),
      );

    bersih.formalEducation = isiBaris(v.formalEducation || []);
    bersih.workExperience = isiBaris(v.workExperience || []);
    bersih.languages = isiBaris(v.languages || []);
    /*
     * Tanggal lahir diubah menjadi tanggal LOKAL sebelum dikirim.
     *
     * Datepicker memberikan objek `Date`; diserialisasi apa adanya ia menjadi
     * "1990-03-12T00:00:00.000Z" — dua puluh enam karakter, sedangkan
     * kolomnya dibatasi dua puluh, sehingga seluruh penyimpanan ditolak
     * `string_too_long` tanpa menyebut baris mana.
     *
     * Bentuk ISO juga menggeser tanggalnya ke UTC: 12 Maret dapat tersimpan
     * sebagai 11 Maret bagi yang berada di zona waktu timur.
     */
    bersih.familyMembers = isiBaris(v.familyMembers || []).map((x: any) => ({
      ...x,
      birthday: tanggalLokal(x.birthday) ?? '',
    }));
    bersih.drivingLicenses = isiBaris(v.drivingLicenses || []);

    this.apiService
      .put(`employee-profiles/${this.input.id}`, bersih)
      .subscribe({
        next: () => {
          this.snackBar.open(
            this.translate.instant('employeeProfile.saved'),
            this.translate.instant('common.close'),
            { duration: 3000 },
          );
          /*
           * Pengisian PERTAMA berlanjut ke formulir keadaan.
           *
           * Profil hanya memuat data yang tidak berubah — KTP, orang tua,
           * pendidikan. Riwayat kesehatan, kontak darurat, jumlah tanggungan,
           * dan kesediaan ditempatkan ada di formulir keadaan, dan enam belas
           * dari tujuh belas pertanyaannya TIDAK ada di profil.
           *
           * Tanpa sambungan ini, hal-hal itu tidak pernah ditanyakan sampai
           * pengingat setahun berbunyi — termasuk kontak darurat, yang justru
           * diperlukan pada hari pertama orangnya turun ke lapangan.
           *
           * Hanya pada pengisian pertama. Penyuntingan berikutnya tidak
           * memaksa siapa pun mengisi ulang formulir keadaan.
           */
          this.dialogRef.close({ tersimpan: true, baru: this.pertamaKali });
        },
        error: (err: any) => {
          this.isSubmitting = false;
          this.snackBar.open(
            this.serverMessage.terjemahkan(err),
            this.translate.instant('common.close'),
            { duration: 5000 },
          );
        },
      });
  }

  tutup(): void {
    this.dialogRef.close(false);
  }
}
