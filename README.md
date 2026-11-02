# TikTok Media Downloader — Backblaze B2 Object Storage

Aplikasi web berbasis **Python Flask** untuk mengunduh video dan foto dari TikTok, kemudian menyimpan hasilnya ke **Backblaze B2 Object Storage** melalui S3-Compatible API.

Aplikasi mendukung dua jenis konten TikTok:
- **Video TikTok** menggunakan `yt-dlp`.
- **Photo Mode TikTok** menggunakan `gallery-dl`.

File yang berhasil diunduh akan diunggah ke bucket Backblaze B2. Pengguna juga dapat mengunduh file langsung dari penyimpanan lokal atau mengambil kembali salinannya dari Backblaze B2.

Proyek ini dikembangkan sebagai implementasi penggunaan object storage dengan integrasi aplikasi Python/Flask.

---

## Fitur Utama

- **TikTok Video Downloader** — Mengunduh video TikTok menggunakan `yt-dlp`.
- **TikTok Photo Downloader** — Mengunduh seluruh gambar dalam satu postingan Photo Mode menggunakan `gallery-dl`.
- **Automatic Media Detection** — Mendeteksi jenis konten berdasarkan pola URL `/video/` atau `/photo/`.
- **Multiple Photo Support** — Mendukung pengunduhan beberapa gambar dari satu postingan.
- **Backblaze B2 Integration** — Mengunggah file ke Backblaze B2 melalui S3-Compatible API menggunakan `boto3`.
- **Local Download** — Menyediakan opsi untuk mengunduh file dari penyimpanan sementara lokal.
- **Download from B2** — Mengambil kembali file dari bucket Backblaze B2.
- **URL Validation** — Memvalidasi URL berdasarkan domain TikTok yang didukung.
- **File Size Limitation** — Membatasi ukuran setiap file yang diproses.
- **Temporary Job Management** — Menyimpan informasi pekerjaan unduhan selama aplikasi berjalan.
- **Web Interface** — Antarmuka sederhana dan responsif menggunakan Flask dan HTML/CSS.

## Teknologi yang Digunakan

| Teknologi | Fungsi |
|---|---|
| Python | Bahasa pemrograman utama |
| Flask | Framework backend dan web server |
| yt-dlp | Pengunduhan video TikTok |
| gallery-dl | Pengunduhan foto TikTok Photo Mode |
| boto3 | Integrasi dengan S3-Compatible API |
| Backblaze B2 | Object storage untuk menyimpan file media |
| python-dotenv | Mengelola konfigurasi environment |
| HTML5 | Struktur halaman web |
| CSS3 | Tampilan dan styling antarmuka |

---

## Arsitektur Aplikasi

Aplikasi menggunakan Flask sebagai backend yang menghubungkan proses pengunduhan media dengan layanan object storage Backblaze B2.

```text
                  USER / BROWSER
                        |
                        v
                Input TikTok URL
                        |
                        v
                 FLASK APPLICATION
                        |
                        v
                  URL VALIDATION
                        |
                        v
                 MEDIA DETECTION
                        |
               +--------+--------+
               |                 |
               v                 v
          TikTok Video       TikTok Photo
               |                 |
               v                 v
             yt-dlp           gallery-dl
               |                 |
               +--------+--------+
                        |
                        v
                TEMPORARY STORAGE
                        |
                        v
                 MEDIA FILES
                        |
                        v
                BOTO3 / S3 API
                        |
                        v
              BACKBLAZE B2 BUCKET
                        |
               +--------+--------+
               |                 |
               v                 v
         Local Download     Download from B2
               |                 |
               +--------+--------+
                        |
                        v
                   USER DEVICE
```

## Struktur Proyek

```text
TikTok-Media-Downloader/
│
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── .env
├── .env.example
│
└── templates/
    └── index.html
```

Keterangan:

| File / Folder | Keterangan |
|---|---|
| `app.py` | Backend Flask, validasi URL, pengunduhan media, dan integrasi B2 |
| `requirements.txt` | Daftar dependensi Python |
| `README.md` | Dokumentasi proyek |
| `.gitignore` | Mengatur file yang tidak disertakan dalam Git |
| `.env` | Konfigurasi dan kredensial lokal |
| `.env.example` | Contoh konfigurasi environment tanpa kredensial asli |
| `templates/` | Folder template HTML |
| `index.html` | Antarmuka utama aplikasi |

---

## Persyaratan Sistem

Sebelum menjalankan aplikasi, pastikan perangkat telah memiliki:

- Python 3.10 atau lebih baru yang kompatibel dengan dependensi.
- pip.
- Akun Backblaze B2.
- Bucket Backblaze B2.
- Application Key dengan izin yang diperlukan.
- Koneksi internet.
- Git (opsional, untuk clone repository).

## Instalasi dan Konfigurasi

### 1. Clone Repository

```bash
git clone https://github.com/alifhmiysf/TikTok-Media-Downloader.git
```

Masuk ke direktori proyek:

```bash
cd TikTok-Media-Downloader
```

### 2. Membuat Virtual Environment

**Windows (PowerShell):**

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**Windows (Git Bash):**

```bash
python -m venv venv
source venv/Scripts/activate
```

### 3. Instalasi Dependensi

Jalankan perintah:

```bash
python -m pip install -r requirements.txt
```

Dependensi yang digunakan:

```text
Flask>=3.0,<4.0
boto3>=1.34
python-dotenv>=1.0
yt-dlp[default,curl-cffi]>=2025.1.15
gallery-dl
```

Keterangan:
- `yt-dlp` digunakan untuk memproses video TikTok.
- `gallery-dl` digunakan untuk memproses foto TikTok.
- `curl-cffi` tersedia melalui extra `yt-dlp[default,curl-cffi]` untuk mendukung mekanisme impersonation browser pada yt-dlp.

### 4. Konfigurasi Backblaze B2

Buat bucket melalui dashboard Backblaze B2.

Selanjutnya, buat Application Key dengan izin yang diperlukan untuk mengunggah dan mengunduh objek dari bucket.

Buat file `.env` pada direktori utama proyek.

Contoh konfigurasi:

```env
FLASK_SECRET_KEY=isi_dengan_secret_key_lokal

B2_KEY_ID=isi_dengan_key_id
B2_APPLICATION_KEY=isi_dengan_application_key
B2_BUCKET_NAME=nama_bucket
B2_ENDPOINT=https://s3.us-east-005.backblazeb2.com
B2_REGION=us-east-005
```

Sesuaikan endpoint, region, bucket, dan kredensial dengan konfigurasi akun Backblaze B2 masing-masing.

**Penting:** Jangan mengunggah file `.env` ke GitHub karena berisi kredensial sensitif.

### 5. Menjalankan Aplikasi

Setelah konfigurasi selesai, jalankan:

```bash
python app.py
```

Akses aplikasi melalui browser:

```text
http://127.0.0.1:5000
```

---

## Alur Kerja Aplikasi

### 1. Input URL

Pengguna memasukkan tautan postingan TikTok melalui halaman utama aplikasi.

Aplikasi menerima URL video maupun Photo Mode.

### 2. Validasi URL

Backend Flask memeriksa:
- URL tidak kosong.
- Protokol menggunakan HTTP atau HTTPS.
- Domain termasuk domain TikTok yang didukung.

### 3. Deteksi Jenis Media

Aplikasi mendeteksi pola URL untuk menentukan downloader yang digunakan.

| Pola URL | Downloader |
|---|---|
| `/video/` | yt-dlp |
| `/photo/` | gallery-dl |

### 4. Proses Pengunduhan

Untuk video, aplikasi menggunakan `yt-dlp`.

Untuk Photo Mode, aplikasi menggunakan `gallery-dl` yang dapat menghasilkan beberapa gambar dari satu postingan.

File gambar akan diproses, sedangkan file audio pendamping Photo Mode tidak disertakan dalam proses upload.

### 5. Penyimpanan Sementara

Hasil unduhan disimpan terlebih dahulu pada direktori sementara di komputer yang menjalankan Flask.

Direktori ini digunakan sebagai sumber file sebelum proses upload ke Backblaze B2.

### 6. Upload ke Backblaze B2

Backend menggunakan `boto3` untuk mengunggah file melalui S3-Compatible API.

Struktur penyimpanan objek:

```text
tiktok-downloads/
│
├── job_id_1/
│   └── video_tiktok.mp4
│
├── job_id_2/
│   ├── foto_01.jpg
│   ├── foto_02.jpg
│   └── foto_03.jpg
│
└── job_id_3/
    └── video_tiktok.mp4
```

Setiap pekerjaan memiliki direktori objek tersendiri berdasarkan ID pekerjaan (`job_id`).

### 7. Download File

Setelah proses upload berhasil, aplikasi menampilkan daftar file yang tersedia.

Pengguna memiliki dua pilihan:

- **Unduh ke Laptop:** Mengambil file dari penyimpanan sementara lokal.
- **Ambil dari B2:** Mengunduh kembali objek dari bucket Backblaze B2 melalui backend Flask.

---

## Konfigurasi dan Batasan

Konfigurasi batas penggunaan pada aplikasi:

| Pengaturan | Nilai |
|---|---|
| Maksimal file per pekerjaan | 20 file |
| Maksimal ukuran setiap file | 100 MB |
| Penyimpanan sementara | Direktori temporary lokal |
| Penyimpanan cloud | Backblaze B2 |
| Pengelolaan pekerjaan | In-memory dictionary |

Beberapa batasan aplikasi:

1. Aplikasi hanya menerima domain TikTok yang telah ditentukan dalam kode.
2. Konten privat, memerlukan autentikasi, atau tidak dapat diakses mungkin gagal diunduh.
3. Keberhasilan pengunduhan bergantung pada kompatibilitas `yt-dlp`, `gallery-dl`, dan perubahan sistem TikTok.
4. Maksimal 20 file diproses dalam satu pekerjaan.
5. Batas 100 MB diterapkan pada setiap file, bukan total seluruh file dalam satu pekerjaan.
6. Informasi pekerjaan disimpan dalam variabel `JOBS` di memori. Informasi tersebut hilang ketika aplikasi dimulai ulang.
7. File sementara belum dibersihkan secara otomatis.
8. Fitur pengambilan file dari B2 bergantung pada informasi pekerjaan yang masih tersimpan di memori aplikasi.

---

## Keamanan

Beberapa hal yang perlu diperhatikan:

- Simpan kredensial Backblaze B2 dalam file `.env`.
- Jangan mengunggah `.env` ke repository publik.
- Gunakan Application Key dengan izin minimum yang diperlukan.
- Jangan menampilkan Application Key atau token pada log dan screenshot.
- Gunakan `FLASK_SECRET_KEY` yang berbeda dari nilai default.
- `debug=True` hanya untuk pengembangan lokal dan tidak digunakan pada deployment produksi.
- Jangan membuka Flask development server secara langsung ke internet.
- Unduh hanya konten yang dimiliki atau yang penggunaannya telah mendapatkan izin.

Pastikan `.gitignore` mencakup:

```gitignore
.env
venv/
.venv/
__pycache__/
*.pyc
instance/
```

---

## Pengembangan Selanjutnya

Beberapa pengembangan yang dapat dipertimbangkan:

- Menambahkan sistem database untuk menyimpan riwayat pekerjaan.
- Menambahkan autentikasi pengguna.
- Menambahkan penghapusan file sementara secara otomatis.
- Menambahkan progress bar selama proses download dan upload.
- Menambahkan validasi format dan ukuran file yang lebih terperinci.
- Menambahkan dukungan penyimpanan metadata media.
- Menambahkan konfigurasi deployment untuk lingkungan produksi.

## Lisensi

Belum ada lisensi distribusi yang ditetapkan pada repository ini. Penggunaan ulang dan distribusi kode mengikuti ketentuan yang nantinya ditentukan oleh pemilik proyek.

---

**Developer:** Ali Fahmi Yusuf  
**Project:** TikTok Media Downloader — Backblaze B2 Object Storage  
**Backend:** Python & Flask  
**Cloud Storage:** Backblaze B2
