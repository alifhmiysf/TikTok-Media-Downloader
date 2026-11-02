
"""
TikTok Media Downloader + Backblaze B2 Object Storage

Fitur:
- Download video TikTok menggunakan yt-dlp.
- Download foto TikTok Photo Mode menggunakan gallery-dl.
- Upload hasil download ke Backblaze B2 melalui S3 API.
- Download file dari penyimpanan lokal.
- Download ulang file dari Backblaze B2.

Catatan:
- Kredensial disimpan di .env.
- JOBS disimpan di memori dan akan hilang saat server restart.
- Aplikasi ditujukan untuk penggunaan lokal.
"""

import os
import re
import sys
import uuid
import tempfile
import mimetypes
import subprocess

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
# 1. KONFIGURASI
# ============================================================

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "change-this-local-dev-secret",
)

KEY_ID = os.getenv("B2_KEY_ID")
APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY")
BUCKET_NAME = os.getenv("B2_BUCKET_NAME")
ENDPOINT = os.getenv("B2_ENDPOINT")
REGION = os.getenv("B2_REGION")

MAX_FILES_PER_JOB = 20
MAX_FILE_SIZE_MB = 100
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

ALLOWED_HOSTS = {
    "tiktok.com",
    "www.tiktok.com",
    "m.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".webm", ".mov", ".mkv", ".m4v",
}

PHOTO_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
}

# Metadata pekerjaan disimpan sementara di memori.
JOBS = {}


# ============================================================
# 2. KONEKSI BACKBLAZE B2
# ============================================================

def get_s3_client():
    required = [
        KEY_ID,
        APPLICATION_KEY,
        BUCKET_NAME,
        ENDPOINT,
        REGION,
    ]

    if not all(required):
        raise RuntimeError(
            "Konfigurasi Backblaze belum lengkap. "
            "Periksa kembali file .env."
        )

    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=KEY_ID,
        aws_secret_access_key=APPLICATION_KEY,
        region_name=REGION,
    )


# ============================================================
# 3. VALIDASI URL TIKTOK
# ============================================================

def validate_tiktok_url(raw_url):
    raw_url = (raw_url or "").strip()

    if not raw_url:
        raise ValueError("Masukkan URL TikTok terlebih dahulu.")

    parsed = urlparse(raw_url)
    hostname = (parsed.hostname or "").lower()

    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL harus menggunakan http atau https.")

    if hostname not in ALLOWED_HOSTS:
        raise ValueError("Gunakan URL dari domain TikTok yang didukung.")

    if parsed.username or parsed.password:
        raise ValueError("URL tidak boleh berisi kredensial.")

    return raw_url


def detect_media_type(url):
    """
    Menentukan jenis konten berdasarkan pola URL TikTok.
    URL /photo/ menggunakan gallery-dl.
    URL lainnya menggunakan yt-dlp.
    """

    path = urlparse(url).path.lower()

    if "/photo/" in path:
        return "photo"

    return "video"


# ============================================================
# 4. SANITASI NAMA FILE
# ============================================================

def safe_filename(filename):
    name = Path(filename).name

    name = re.sub(
        r"[^A-Za-z0-9._() -]",
        "_",
        name,
    ).strip(" .")

    return name[:150] or "media-file"


def flatten_files(files, output_dir):
    """
    Memindahkan hasil unduhan dari subfolder gallery-dl
    ke satu folder utama agar route download lokal tetap
    dapat menemukan semua file.
    """

    flattened = []

    for source in files:
        name = safe_filename(source.name)
        destination = output_dir / name

        # Menghindari nama file yang sama.
        counter = 2

        while destination.exists() and destination != source:
            stem = Path(name).stem
            suffix = Path(name).suffix

            destination = output_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        if source != destination:
            source.rename(destination)

        flattened.append(destination)

    return flattened


# ============================================================
# 5. VALIDASI FILE HASIL DOWNLOAD
# ============================================================

def validate_downloaded_files(files):
    if not files:
        raise RuntimeError(
            "Tidak ada file media yang berhasil diunduh."
        )

    if len(files) > MAX_FILES_PER_JOB:
        raise RuntimeError(
            f"Jumlah file melebihi batas "
            f"{MAX_FILES_PER_JOB} file per proses."
        )

    for path in files:
        if path.stat().st_size > MAX_FILE_SIZE:
            raise RuntimeError(
                f"File {path.name} melebihi batas "
                f"{MAX_FILE_SIZE_MB} MB."
            )

    return files


# ============================================================
# 6. DOWNLOAD VIDEO DENGAN yt-dlp
# ============================================================

def download_tiktok_video(url, output_dir):
    output_template = str(
        output_dir / "%(title).80s-%(id)s.%(ext)s"
    )

    options = {
        "outtmpl": output_template,
        "noplaylist": True,
        "max_filesize": MAX_FILE_SIZE,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "writethumbnail": False,
        "writeinfojson": False,
        "restrictfilenames": True,
        "retries": 3,
        "socket_timeout": 30,
    }

    with yt_dlp.YoutubeDL(options) as downloader:
        downloader.download([url])

    files = [
        path
        for path in output_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in VIDEO_EXTENSIONS
    ]

    files = flatten_files(files, output_dir)

    return validate_downloaded_files(files)


# ============================================================
# 7. DOWNLOAD FOTO DENGAN gallery-dl
# ============================================================

def download_tiktok_photo(url, output_dir):
    """
    gallery-dl dapat menghasilkan beberapa foto sekaligus.
    Hasilnya dapat tersimpan dalam struktur subfolder.

    Hanya file gambar yang diproses. Audio MP3 pendamping
    Photo Mode sengaja tidak ikut diunggah.
    """

    command = [
        sys.executable,
        "-m",
        "gallery_dl",
        url,
    ]

    result = subprocess.run(
        command,
        cwd=str(output_dir),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )

    if result.returncode != 0:
        detail = (
            result.stderr.strip()
            or result.stdout.strip()
            or "gallery-dl gagal memproses URL."
        )

        raise RuntimeError(
            f"Gagal mengunduh foto TikTok: {detail[-1000:]}"
        )

    # Cari semua gambar, termasuk yang berada di subfolder.
    image_files = [
        path
        for path in output_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in PHOTO_EXTENSIONS
    ]

    # Pindahkan foto ke folder utama.
    image_files = flatten_files(image_files, output_dir)

    return validate_downloaded_files(image_files)


# ============================================================
# 8. FUNGSI DOWNLOAD UTAMA
# ============================================================

def download_tiktok(url, output_dir):
    media_type = detect_media_type(url)

    app.logger.info(
        "Memproses konten TikTok dengan tipe: %s",
        media_type,
    )

    if media_type == "photo":
        return download_tiktok_photo(url, output_dir)

    return download_tiktok_video(url, output_dir)


# ============================================================
# 9. CONTENT TYPE
# ============================================================

def content_type_for(path):
    return (
        mimetypes.guess_type(path.name)[0]
        or "application/octet-stream"
    )


# ============================================================
# 10. UPLOAD KE BACKBLAZE B2
# ============================================================

def upload_to_b2(files, job_id):
    s3 = get_s3_client()
    uploaded = []

    for path in files:
        name = safe_filename(path.name)
        safe_path = path.with_name(name)

        if safe_path != path:
            path = path.rename(safe_path)

        object_key = (
            f"tiktok-downloads/{job_id}/{name}"
        )

        s3.upload_file(
            str(path),
            BUCKET_NAME,
            object_key,
            ExtraArgs={
                "ContentType": content_type_for(path)
            },
        )

        uploaded.append({
            "name": name,
            "key": object_key,
            "size": path.stat().st_size,
        })

    return uploaded


# ============================================================
# 11. HALAMAN UTAMA
# ============================================================

@app.get("/")
def index():
    return render_template("index.html")


# ============================================================
# 12. PROSES DOWNLOAD DAN UPLOAD
# ============================================================

@app.post("/download")
def process_download():
    url = request.form.get("url", "")

    try:
        # Validasi URL.
        url = validate_tiktok_url(url)

        # Membuat ID pekerjaan.
        job_id = uuid.uuid4().hex

        # Membuat direktori sementara.
        work_dir = Path(
            tempfile.mkdtemp(
                prefix=f"tiktok_{job_id}_"
            )
        )

        # Tahap 1: download video atau foto.
        media_files = download_tiktok(
            url,
            work_dir,
        )

        # Tahap 2: upload ke Backblaze B2.
        uploaded = upload_to_b2(
            media_files,
            job_id,
        )

        # Tahap 3: simpan informasi pekerjaan.
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

        media_type = detect_media_type(url)

        if media_type == "photo":
            success_message = (
                f"Berhasil! {len(uploaded)} foto telah "
                "diunggah ke Backblaze B2."
            )
        else:
            success_message = (
                "Berhasil! Video telah diunggah "
                "ke Backblaze B2."
            )

        flash(success_message, "success")

        return render_template(
            "index.html",
            files=JOBS[job_id]["files"],
            job_id=job_id,
            submitted_url=url,
        )

    except ValueError as exc:
        flash(str(exc), "error")

    except yt_dlp.utils.DownloadError:
        flash(
            "Video gagal diunduh. Pastikan URL benar "
            "dan konten dapat diakses.",
            "error",
        )

    except subprocess.TimeoutExpired:
        flash(
            "Proses download melewati batas waktu 5 menit.",
            "error",
        )

    except (ClientError, RuntimeError) as exc:
        app.logger.warning(
            "Download/storage operation failed: %s",
            type(exc).__name__,
        )

        if isinstance(exc, RuntimeError):
            message = str(exc)
        else:
            message = (
                "Upload atau akses Backblaze B2 gagal. "
                "Periksa konfigurasi dan izin Application Key."
            )

        flash(message, "error")

    except Exception as exc:
        app.logger.exception(
            "Unexpected downloader error: %s",
            type(exc).__name__,
        )

        flash(
            "Terjadi kesalahan. Periksa terminal "
            "untuk detail teknis.",
            "error",
        )

    return redirect(url_for("index"))


# ============================================================
# 13. DOWNLOAD DARI PENYIMPANAN LOKAL
# ============================================================

@app.get("/download-local/<job_id>/<path:filename>")
def download_local(job_id, filename):
    job = JOBS.get(job_id)

    if not job:
        abort(404)

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

    local_path = Path(job["dir"]) / filename

    if not local_path.is_file():
        abort(404)

    return send_file(
        local_path,
        as_attachment=True,
        download_name=filename,
    )


# ============================================================
# 14. DOWNLOAD ULANG DARI BACKBLAZE B2
# ============================================================

@app.get("/download-from-b2/<job_id>/<path:filename>")
def download_from_b2(job_id, filename):
    job = JOBS.get(job_id)

    if not job:
        abort(404)

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
        s3 = get_s3_client()

        temp_dir = Path(
            tempfile.mkdtemp(
                prefix="b2_restore_"
            )
        )

        local_path = temp_dir / item["name"]

        s3.download_file(
            BUCKET_NAME,
            item["key"],
            str(local_path),
        )

        return send_file(
            local_path,
            as_attachment=True,
            download_name=item["name"],
        )

    except Exception as exc:
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
# 15. MENJALANKAN APLIKASI
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)
