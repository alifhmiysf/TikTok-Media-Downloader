# TikTok Media Downloader — Backblaze B2

Aplikasi web berbasis Flask untuk mengunduh media TikTok yang dapat diakses secara sah, menyimpan hasilnya ke Backblaze B2 Object Storage, dan menyediakan file untuk diunduh kembali ke laptop.

## Fitur

- Validasi URL dari domain TikTok yang didukung.
- Pengunduhan media menggunakan `yt-dlp`.
- Penyimpanan file ke Backblaze B2 melalui S3-compatible API.
- Pengunduhan hasil dari penyimpanan lokal maupun Backblaze B2.
- Pembatasan jumlah file dan ukuran file.
- Antarmuka web berbasis Flask.

## Teknologi

- Python
- Flask
- yt-dlp
- boto3
- Backblaze B2
- python-dotenv

## Struktur Proyek

```text
tiktok_b2_downloader/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
└── templates/
    └── index.html
```

## Persyaratan

- Python 3.10 atau versi yang kompatibel dengan dependensi proyek.
- Akun Backblaze B2.
- Bucket Backblaze B2.
- Application Key dengan izin minimum yang diperlukan untuk mengunggah dan mengunduh file.
- Koneksi internet.

## Instalasi Lokal

### 1. Clone repository

```bash
git clone <URL_REPOSITORY>
cd tiktok_b2_downloader
```

Ganti `<URL_REPOSITORY>` dengan URL repository GitHub milikmu.

### 2. Buat virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Instal dependensi

```powershell
pip install -r requirements.txt
```

### 4. Konfigurasi Backblaze B2

Buat file `.env` secara lokal pada direktori yang sama dengan `app.py`.

Isi konfigurasi menggunakan kredensial milikmu sendiri:

- `B2_KEY_ID`
- `B2_APPLICATION_KEY`
- `B2_BUCKET_NAME`
- `B2_ENDPOINT`
- `B2_REGION`
- `FLASK_SECRET_KEY`

Jangan mengunggah file `.env` ke GitHub. File tersebut berisi informasi sensitif.

### 5. Jalankan aplikasi

```powershell
python app.py
```

Buka browser dan akses:

http://127.0.0.1:5000

## Alur Kerja

1. Pengguna memasukkan URL TikTok.
2. Aplikasi memvalidasi URL.
3. `yt-dlp` mencoba mengunduh media ke direktori sementara.
4. File media diunggah ke bucket Backblaze B2.
5. Aplikasi menampilkan hasil dan menyediakan opsi unduh.

## Konfigurasi dan Batasan

Batas default yang ditetapkan dalam kode:

- Maksimal 20 file per pekerjaan.
- Batas ukuran file 100 MB.
- Hanya domain TikTok tertentu yang diterima.

Dukungan pengunduhan bergantung pada jenis konten, aksesibilitas URL, dan kompatibilitas `yt-dlp`. Konten privat atau terlindungi belum tentu dapat diakses.

Informasi pekerjaan disimpan di memori aplikasi. Setelah aplikasi dimulai ulang, indeks pekerjaan dapat hilang. File sementara juga tidak otomatis dibersihkan oleh aplikasi saat ini.

## Keamanan

- Jangan commit `.env`, kredensial, token, atau Application Key.
- Gunakan Application Key dengan izin minimum yang diperlukan.
- Jangan membagikan kredensial di log atau screenshot.
- `debug=True` hanya digunakan untuk pengembangan lokal.
- Gunakan aplikasi hanya untuk media yang dimiliki atau memiliki izin untuk diunduh.

## Lisensi

Tentukan lisensi proyek sebelum mendistribusikan atau mengizinkan penggunaan ulang kode.
