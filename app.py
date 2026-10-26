
"""
============================================================
TikTok Media Downloader + Backblaze B2 Object Storage
============================================================

Deskripsi:
    Aplikasi web berbasis Flask untuk:
    1. Menerima URL TikTok dari pengguna.
    2. Memvalidasi URL agar hanya domain TikTok yang didukung.
    3. Mengunduh media menggunakan yt-dlp.
    4. Mengunggah media ke Backblaze B2 melalui S3 API.
    5. Menyediakan endpoint untuk mengunduh media ke laptop.

Teknologi:
    - Flask       : web framework
    - yt-dlp      : pengunduhan media yang didukung
    - boto3       : komunikasi dengan Backblaze B2 melalui S3 API
    - python-dotenv: membaca konfigurasi dari file .env

Catatan:
    - File .env berisi kredensial rahasia dan tidak boleh diunggah
      ke repositori publik.
    - Aplikasi ini dirancang untuk penggunaan lokal.
    - JOBS disimpan di memori, sehingga indeks pekerjaan hilang
      ketika aplikasi dimulai ulang.
============================================================
"""

# ============================================================
# 1. IMPORT LIBRARY
# ============================================================

import os
import re
import uuid
import tempfile

from pathlib import Path
from urllib.parse import urlparse

import boto3
import yt_dlp

from botocore.exceptions import ClientError
from dotenv import load_dotenv

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
    abort,
)


# ============================================================
# 2. MEMUAT KONFIGURASI ENVIRONMENT
# ============================================================

# Membaca variabel dari file .env pada direktori kerja aplikasi.
# File .env sebaiknya berada satu folder dengan app.py.
load_dotenv()

# Membuat objek aplikasi Flask.
app = Flask(__name__)

# Secret key digunakan Flask untuk menandatangani session dan flash message.
# Untuk penggunaan publik, wajib menggunakan secret acak dari environment.
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "change-this-local-dev-secret",
)


# ============================================================
# 3. KONFIGURASI BACKBLAZE B2
# ============================================================

# Semua kredensial dibaca dari environment, bukan ditulis langsung
# di dalam kode program.
KEY_ID = os.getenv("B2_KEY_ID")
APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY")
BUCKET_NAME = os.getenv("B2_BUCKET_NAME")
ENDPOINT = os.getenv("B2_ENDPOINT")
REGION = os.getenv("B2_REGION")


# ============================================================
# 4. KONFIGURASI BATAS PENGGUNAAN
# ============================================================

# Jumlah maksimal file media yang diperbolehkan dalam satu pekerjaan.
MAX_FILES_PER_JOB = 20

# Ukuran maksimal satu file media, dalam megabyte.
MAX_FILE_SIZE_MB = 100

# Domain yang diperbolehkan untuk mencegah URL menuju host sembarang.
# Validasi ini membatasi host URL, tetapi bukan pengganti seluruh
# perlindungan keamanan jaringan.
ALLOWED_HOSTS = {
    "tiktok.com",
    "www.tiktok.com",
    "m.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
}


# ============================================================
# 5. PENYIMPANAN INFORMASI PEKERJAAN
# ============================================================

# JOBS menyimpan metadata pekerjaan selama proses Flask berjalan.
#
# Bentuk umum:
# {
#     "job_id": {
#         "dir": "direktori sementara",
#         "files": [
#             {
#                 "name": "nama file",
#                 "key": "object key Backblaze",
#                 "size": ukuran file,
#                 "download_url": "URL unduhan"
#             }
#         ]
#     }
# }
#
# Keterbatasan:
# - Data hilang saat aplikasi restart.
# - Data tidak otomatis dibagikan antarbeberapa worker.
# - File sementara dapat hilang atau memenuhi disk.
#
# Untuk aplikasi produksi, pertimbangkan database dan pembersihan file.
JOBS = {}


# ============================================================
# 6. MEMBUAT KONEKSI KE BACKBLAZE B2
# ============================================================

def get_s3_client():
    """
    Membuat klien boto3 untuk mengakses Backblaze B2 melalui S3 API.

    Returns:
        Klien boto3 S3.

    Raises:
        RuntimeError: jika konfigurasi wajib belum tersedia.

    Penting:
        B2_ENDPOINT harus berupa endpoint lengkap, misalnya:
        https://s3.us-east-005.backblazeb2.com
    """

    # Pastikan seluruh konfigurasi wajib tersedia sebelum koneksi dibuat.
    required = [
        KEY_ID,
        APPLICATION_KEY,
        BUCKET_NAME,
        ENDPOINT,
        REGION,
    ]

    if not all(required):
        raise RuntimeError(
            "Konfigurasi Backblaze belum lengkap. Periksa B2_KEY_ID, "
            "B2_APPLICATION_KEY, B2_BUCKET_NAME, B2_ENDPOINT, "
            "dan B2_REGION di .env."
        )

    # Membuat klien S3 dengan kredensial dan endpoint Backblaze.
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=KEY_ID,
        aws_secret_access_key=APPLICATION_KEY,
        region_name=REGION,
    )


# ============================================================
# 7. VALIDASI URL TIKTOK
# ============================================================

def validate_tiktok_url(raw_url):
    """
    Memvalidasi URL sebelum diteruskan ke yt-dlp.

    Pemeriksaan:
        - URL tidak boleh kosong.
        - Skema harus http atau https.
        - Host harus ada dalam ALLOWED_HOSTS.
        - URL tidak boleh memuat username atau password.

    Args:
        raw_url: URL dari formulir pengguna.

    Returns:
        URL yang sudah dibersihkan dari spasi di awal dan akhir.

    Raises:
        ValueError: jika URL tidak memenuhi aturan.
    """

    # Menghapus spasi di awal dan akhir.
    raw_url = (raw_url or "").strip()

    if not raw_url:
        raise ValueError("Masukkan URL TikTok terlebih dahulu.")

    # Memisahkan URL menjadi skema, host, path, dan komponen lain.
    parsed = urlparse(raw_url)
    hostname = (parsed.hostname or "").lower()

    # Memastikan skema URL aman dan didukung.
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL harus menggunakan http atau https.")

    # Hanya menerima domain TikTok yang sudah ditentukan.
    if hostname not in ALLOWED_HOSTS:
        raise ValueError("Gunakan URL dari domain TikTok yang didukung.")

    # Menolak URL dengan kredensial yang disisipkan.
    if parsed.username or parsed.password:
        raise ValueError("URL tidak boleh berisi kredensial.")

    return raw_url


# ============================================================
# 8. SANITASI NAMA FILE
# ============================================================

def safe_filename(path):
    """
    Membersihkan nama file agar lebih aman digunakan sebagai nama
    file lokal maupun object key di Backblaze.

    Karakter selain huruf, angka, titik, kurung, spasi, garis bawah,
    dan tanda hubung akan diganti dengan garis bawah.

    Args:
        path: objek Path atau lokasi file.

    Returns:
        Nama file yang sudah dibersihkan.
    """

    # Mengambil nama file tanpa direktori induknya.
    name = Path(path).name

    # Mengganti karakter yang tidak diperbolehkan.
    name = re.sub(r"[^A-Za-z0-9._() -]", "_", name).strip(" .")

    # Membatasi panjang nama dan memberikan nama default jika kosong.
    return name[:150] or "media-file"


# ============================================================
# 9. MEMERIKSA JENIS FILE MEDIA
# ============================================================

def is_media_file(path):
    """
    Memastikan sebuah path menunjuk ke file media yang didukung.

    File sementara dan file metadata seperti .part, .json, atau
    subtitle tidak akan dimasukkan ke daftar hasil unduhan.

    Args:
        path: objek Path yang akan diperiksa.

    Returns:
        True jika merupakan file media yang diizinkan, selain itu False.
    """

    # Abaikan folder dan path yang bukan file.
    if not path.is_file():
        return False

    # Abaikan file sementara dan metadata.
    ignored_extensions = {
        ".part",
        ".ytdl",
        ".json",
        ".description",
        ".vtt",
        ".srt",
        ".ass",
        ".lrc",
    }

    if path.suffix.lower() in ignored_extensions:
        return False

    # Ekstensi media yang diterima aplikasi.
    allowed_extensions = {
        ".mp4",
        ".webm",
        ".mov",
        ".mkv",
        ".m4v",
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".mp3",
        ".m4a",
        ".wav",
        ".opus",
    }

    return path.suffix.lower() in allowed_extensions


# ============================================================
# 10. MENGUNDUH MEDIA DENGAN yt-dlp
# ============================================================

def download_tiktok(url, output_dir):
    """
    Mengunduh media dari URL TikTok yang didukung menggunakan yt-dlp.

    Args:
        url: URL TikTok yang sudah divalidasi.
        output_dir: direktori sementara tempat file disimpan.

    Returns:
        Daftar objek Path untuk file media yang berhasil diunduh.

    Raises:
        RuntimeError: jika tidak ada file yang dihasilkan atau batas
                      jumlah/ukuran file terlampaui.
        yt_dlp.utils.DownloadError: jika proses unduh gagal.
    """

    # Pola nama file:
    # judul-media-ID.extensi
    #
    # ID membantu membedakan media dengan judul yang sama.
    output_template = str(
        output_dir / "%(title).80s-%(id)s.%(ext)s"
    )

    # Opsi pengunduhan yt-dlp.
    options = {
        # Lokasi dan format nama output.
        "outtmpl": output_template,

        # Menghindari pengunduhan playlist jika tidak diperlukan.
        "noplaylist": True,

        # Batas ukuran file yang diterapkan yt-dlp.
        "max_filesize": MAX_FILE_SIZE_MB * 1024 * 1024,

        # Mengurangi output terminal.
        "quiet": True,
        "no_warnings": True,

        # Gagalkan proses jika unduhan tidak berhasil.
        "ignoreerrors": False,

        # Tidak menyimpan thumbnail dan metadata JSON terpisah.
        "writethumbnail": False,
        "writeinfojson": False,

        # Membatasi karakter pada nama file.
        "restrictfilenames": True,

        # Jumlah percobaan ulang ketika terjadi kegagalan.
        "retries": 2,

        # Batas waktu socket jaringan dalam detik.
        "socket_timeout": 20,

        # User-Agent browser untuk permintaan HTTP.
        # Ini bukan jaminan bahwa TikTok akan menerima permintaan.
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        ),
    }

    # Menjalankan proses pengunduhan.
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])

    # Mengumpulkan file media yang benar-benar dihasilkan.
    results = [
        path
        for path in output_dir.iterdir()
        if is_media_file(path)
    ]

    # Jika tidak ada media, kembalikan error yang mudah dipahami.
    if not results:
        raise RuntimeError(
            "Tidak ada file media yang berhasil dibuat. "
            "Tautan mungkin tidak didukung, konten mungkin privat, "
            "atau TikTok mengubah dukungannya."
        )

    # Memastikan jumlah file tidak melampaui batas aplikasi.
    if len(results) > MAX_FILES_PER_JOB:
        raise RuntimeError(
            f"Jumlah file melebihi batas "
            f"{MAX_FILES_PER_JOB} file per proses."
        )

    # Memeriksa ukuran aktual setiap file setelah diunduh.
    for path in results:
        file_size = path.stat().st_size
        max_size = MAX_FILE_SIZE_MB * 1024 * 1024

        if file_size > max_size:
            raise RuntimeError(
                f"File {path.name} melebihi batas "
                f"{MAX_FILE_SIZE_MB} MB."
            )

    return results


# ============================================================
# 11. MENENTUKAN CONTENT TYPE FILE
# ============================================================

def content_type_for(path):
    """
    Menentukan MIME type berdasarkan ekstensi file.

    MIME type disimpan bersama metadata objek di Backblaze agar
    file lebih mudah dikenali ketika diakses atau diunduh.

    Args:
        path: objek Path file.

    Returns:
        String MIME type, atau application/octet-stream jika
        jenis file tidak dikenali.
    """

    import mimetypes

    return (
        mimetypes.guess_type(path.name)[0]
        or "application/octet-stream"
    )


# ============================================================
# 12. MENGUNGGAH FILE KE BACKBLAZE B2
# ============================================================

def upload_to_b2(files, job_id):
    """
    Mengunggah daftar file media ke bucket Backblaze B2.

    Setiap file disimpan dengan pola object key:
        tiktok-downloads/{job_id}/{nama-file}

    Args:
        files: daftar objek Path media lokal.
        job_id: ID unik untuk satu pekerjaan unduhan.

    Returns:
        Daftar metadata file yang berhasil diunggah.

    Raises:
        ClientError: jika operasi upload melalui S3 API gagal.
    """

    # Membuat klien koneksi ke Backblaze.
    s3 = get_s3_client()

    uploaded = []

    # Mengunggah file satu per satu.
    for path in files:
        # Bersihkan nama file sebelum digunakan sebagai object key.
        name = safe_filename(path)

        # Setiap pekerjaan mempunyai prefix folder berbeda.
        object_key = f"tiktok-downloads/{job_id}/{name}"

        # Mengirim file lokal ke bucket Backblaze.
        s3.upload_file(
            str(path),
            BUCKET_NAME,
            object_key,
            ExtraArgs={
                "ContentType": content_type_for(path)
            },
        )

        # Menyimpan metadata untuk dipakai oleh route unduhan.
        uploaded.append(
            {
                "name": name,
                "key": object_key,
                "size": path.stat().st_size,
            }
        )

    return uploaded


# ============================================================
# 13. ROUTE HALAMAN UTAMA
# ============================================================

@app.get("/")
def index():
    """
    Menampilkan halaman utama aplikasi.

    Template:
        templates/index.html
    """

    return render_template("index.html")


# ============================================================
# 14. ROUTE PEMROSESAN UNDUHAN
# ============================================================

@app.post("/download")
def process_download():
    """
    Memproses formulir URL TikTok.

    Alur:
        1. Membaca URL dari formulir.
        2. Memvalidasi URL.
        3. Membuat ID pekerjaan dan direktori sementara.
        4. Mengunduh media.
        5. Mengunggah media ke Backblaze B2.
        6. Menyimpan metadata ke JOBS.
        7. Menampilkan hasil pada halaman utama.

    Catatan:
        Proses download dan upload berjalan secara sinkron.
        Untuk file besar atau penggunaan publik, pertimbangkan
        background worker dan pembatasan request.
    """

    # Mengambil nilai dari input formulir bernama "url".
    url = request.form.get("url", "")

    try:
        # Pastikan URL berasal dari domain yang didukung.
        url = validate_tiktok_url(url)

        # Membuat ID acak untuk membedakan setiap pekerjaan.
        job_id = uuid.uuid4().hex

        # Membuat direktori sementara khusus pekerjaan ini.
        work_dir = Path(
            tempfile.mkdtemp(prefix=f"tiktok_{job_id}_")
        )

        # Tahap 1: mengunduh media ke direktori sementara.
        media_files = download_tiktok(url, work_dir)

        # Tahap 2: mengunggah media ke Backblaze B2.
        uploaded = upload_to_b2(media_files, job_id)

        # Menyimpan indeks pekerjaan di memori.
        # Indeks ini diperlukan oleh endpoint unduhan.
        JOBS[job_id] = {
            "dir": str(work_dir),
            "files": [
                {
                    "name": item["name"],
                    "key": item["key"],
                    "size": item["size"],
                    "download_url": url_for(
                        "download_local",
                        job_id=job_id,
                        filename=item["name"],
                    ),
                }
                for item in uploaded
            ],
        }

        # Pesan sukses ditampilkan di halaman hasil.
        flash(
            "Berhasil! Media sudah diunggah ke Backblaze B2 "
            "dan siap diunduh ke laptop.",
            "success",
        )

        # Render halaman yang sama dengan data hasil unduhan.
        return render_template(
            "index.html",
            files=JOBS[job_id]["files"],
            job_id=job_id,
            submitted_url=url,
        )

    # Kesalahan validasi input.
    except ValueError as exc:
        flash(str(exc), "error")

    # Kesalahan saat yt-dlp mengunduh media.
    except yt_dlp.utils.DownloadError:
        flash(
            "Media gagal diambil. Pastikan URL benar dan konten "
            "dapat diakses secara sah tanpa melewati login "
            "atau proteksi.",
            "error",
        )

    # Kesalahan konfigurasi, batas aplikasi, atau penyimpanan.
    except (ClientError, RuntimeError) as exc:
        # Catat jenis error tanpa mencetak kredensial.
        app.logger.warning(
            "Download/storage operation failed: %s",
            type(exc).__name__,
        )

        # RuntimeError berasal dari validasi internal aplikasi.
        # ClientError berasal dari operasi layanan penyimpanan.
        if isinstance(exc, RuntimeError):
            message = str(exc)
        else:
            message = (
                "Upload ke Backblaze gagal. Periksa endpoint, "
                "region, izin key, dan koneksi."
            )

        flash(message, "error")

    # Menangani kesalahan lain yang tidak diperkirakan.
    except Exception as exc:
        app.logger.exception(
            "Unexpected downloader error: %s",
            type(exc).__name__,
        )

        flash(
            "Terjadi kesalahan. Periksa terminal VS Code "
            "untuk detail teknis. Jangan membagikan kredensial.",
            "error",
        )

    # Jika terjadi error, kembali ke halaman utama.
    return redirect(url_for("index"))


# ============================================================
# 15. ROUTE MENGUNDUH FILE DARI PENYIMPANAN LOKAL
# ============================================================

@app.get("/download-local/<job_id>/<path:filename>")
def download_local(job_id, filename):
    """
    Mengirim file hasil unduhan yang masih tersedia di disk lokal.

    Endpoint ini tidak mengambil file dari Backblaze.
    File diambil dari direktori sementara pada komputer yang
    menjalankan aplikasi.

    Args:
        job_id: ID pekerjaan.
        filename: nama file yang ingin diunduh.

    Raises:
        404: jika pekerjaan, metadata file, atau file tidak ditemukan.
    """

    # Pastikan pekerjaan masih tercatat di memori.
    job = JOBS.get(job_id)

    if not job:
        abort(404)

    # Pastikan file tercatat pada daftar hasil pekerjaan.
    # Ini juga mencegah pengguna meminta file sembarang.
    match = next(
        (
            item
            for item in job["files"]
            if item["name"] == filename
        ),
        None,
    )

    if not match:
        abort(404)

    # Membentuk path file berdasarkan direktori pekerjaan.
    local_path = Path(job["dir"]) / filename

    # Pastikan file benar-benar masih ada.
    if not local_path.is_file():
        abort(404)

    # Mengirim file sebagai lampiran untuk diunduh browser.
    return send_file(
        local_path,
        as_attachment=True,
        download_name=filename,
    )


# ============================================================
# 16. ROUTE MENGUNDUH ULANG FILE DARI BACKBLAZE B2
# ============================================================

@app.get("/download-from-b2/<job_id>/<path:filename>")
def download_from_b2(job_id, filename):
    """
    Mengambil file yang sebelumnya diunggah ke Backblaze B2,
    menyimpannya ke direktori sementara, lalu mengirimkannya
    ke browser sebagai file unduhan.

    Berbeda dari download_local(), route ini membaca ulang objek
    dari layanan penyimpanan cloud.

    Catatan:
        Metadata pekerjaan tetap harus tersedia di JOBS.
        Saat aplikasi restart, route ini tidak dapat menemukan
        pekerjaan lama tanpa database atau indeks persisten.
    """

    # Memeriksa keberadaan pekerjaan.
    job = JOBS.get(job_id)

    if not job:
        abort(404)

    # Memastikan nama file merupakan bagian dari pekerjaan tersebut.
    item = next(
        (
            file_info
            for file_info in job["files"]
            if file_info["name"] == filename
        ),
        None,
    )

    if not item:
        abort(404)

    try:
        # Membuat koneksi ke Backblaze.
        s3 = get_s3_client()

        # Membuat direktori sementara untuk menampung hasil unduhan.
        temp_dir = Path(
            tempfile.mkdtemp(prefix="b2_restore_")
        )

        # Menentukan lokasi file hasil pengambilan dari B2.
        local_path = temp_dir / item["name"]

        # Mengunduh objek dari bucket ke disk lokal.
        s3.download_file(
            BUCKET_NAME,
            item["key"],
            str(local_path),
        )

        # Mengirim file hasil unduhan ke browser.
        return send_file(
            local_path,
            as_attachment=True,
            download_name=item["name"],
        )

    except Exception as exc:
        # Catat detail error di log server, bukan di halaman pengguna.
        app.logger.warning(
            "B2 download failed: %s",
            type(exc).__name__,
        )

        flash(
            "Gagal mengambil file dari Backblaze B2. "
            "Periksa konfigurasi dan izin key.",
            "error",
        )

        return redirect(url_for("index"))


# ============================================================
# 17. MENJALANKAN APLIKASI
# ============================================================

if __name__ == "__main__":
    """
    Bagian ini dijalankan hanya ketika app.py dieksekusi langsung.

    debug=True membantu pengembangan lokal, tetapi jangan digunakan
    untuk server publik. Jangan mengekspos server development Flask
    langsung ke internet.
    """

    app.run(debug=True)
