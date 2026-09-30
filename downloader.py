import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Callable, Optional

import yt_dlp


# ============================================================
# CONFIG
# ============================================================

DEFAULT_DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE_MB = 49
MAX_RETRIES = 3
RETRY_DELAY = 3
DOWNLOAD_TIMEOUT = 300  # 5 minutes


# ============================================================
# QUALITY OPTIONS
# ============================================================

VIDEO_QUALITY = {
    "best": "bestvideo*+bestaudio/best",
    "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360": "bestvideo[height<=360]+bestaudio/best[height<=360]",
}

MP3_QUALITY = {
    "128": "128",
    "192": "192",
    "256": "256",
    "320": "320",
}


# ============================================================
# EXCEPTIONS
# ============================================================

class DownloaderError(Exception):
    """Base downloader error."""


class InvalidURLError(DownloaderError):
    """Invalid or unsupported URL."""


class DownloadFailedError(DownloaderError):
    """Download failed after retries."""


class FileTooLargeError(DownloaderError):
    """Downloaded file exceeds configured size limit."""


class FFmpegNotFoundError(DownloaderError):
    """FFmpeg is not installed."""


# ============================================================
# DOWNLOADER
# ============================================================

class NuthhDownloader:

    def __init__(
        self,
        download_dir: str = DEFAULT_DOWNLOAD_DIR,
        max_file_size_mb: int = MAX_FILE_SIZE_MB,
    ):
        self.download_dir = Path(download_dir)
        self.max_file_size_mb = max_file_size_mb

        self.download_dir.mkdir(
            parents=True,
            exist_ok=True
        )

    # ========================================================
    # FFmpeg CHECK
    # ========================================================

    def check_ffmpeg(self) -> bool:
        """
        Check whether FFmpeg exists.
        """
        return shutil.which("ffmpeg") is not None

    # ========================================================
    # URL VALIDATION
    # ========================================================

    def is_valid_url(self, url: str) -> bool:
        if not url:
            return False

        url = url.strip().lower()

        supported_domains = (
            "tiktok.com",
            "www.tiktok.com",
            "vm.tiktok.com",
            "vt.tiktok.com",
        )

        return url.startswith(
            (
                "https://",
                "http://",
            )
        ) and any(
            domain in url
            for domain in supported_domains
        )

    # ========================================================
    # FILE SIZE
    # ========================================================

    def get_file_size_mb(self, file_path: str) -> float:
        if not os.path.exists(file_path):
            return 0

        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)

    # ========================================================
    # CLEANUP
    # ========================================================

    def cleanup(self, path: Optional[str]):
        if not path:
            return

        try:
            file_path = Path(path)

            if file_path.exists():
                if file_path.is_file():
                    file_path.unlink()
                elif file_path.is_dir():
                    shutil.rmtree(file_path)

        except Exception:
            pass

    # ========================================================
    # CLEAN OLD FILES
    # ========================================================

    def cleanup_old_files(
        self,
        max_age_minutes: int = 30,
    ):
        now = time.time()
        max_age = max_age_minutes * 60

        try:
            for file in self.download_dir.iterdir():
                try:
                    if now - file.stat().st_mtime > max_age:
                        self.cleanup(str(file))
                except Exception:
                    continue
        except Exception:
            pass

    # ========================================================
    # PROGRESS FORMAT
    # ========================================================

    @staticmethod
    def format_progress(data: dict) -> dict:
        status = data.get("status")
        downloaded = data.get("downloaded_bytes", 0)
        total = (
            data.get("total_bytes")
            or data.get("total_bytes_estimate")
            or 0
        )
        speed = data.get("speed") or 0
        eta = data.get("eta")

        percent = 0
        if total > 0:
            percent = (downloaded / total) * 100

        speed_mb = speed / (1024 * 1024)
        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total / (1024 * 1024)

        return {
            "status": status,
            "percent": round(percent, 1),
            "downloaded_mb": round(downloaded_mb, 2),
            "total_mb": round(total_mb, 2),
            "speed_mb": round(speed_mb, 2),
            "eta": eta,
        }

    # ========================================================
    # PROGRESS BAR
    # ========================================================

    @staticmethod
    def progress_bar(
        percent: float,
        length: int = 10,
    ) -> str:
        filled = int(length * percent / 100)
        filled = max(0, min(filled, length))
        return "█" * filled + "░" * (length - filled)

    # ========================================================
    # DOWNLOAD VIDEO
    # ========================================================

    async def download_video(
        self,
        url: str,
        quality: str = "best",
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> str:
        if not self.is_valid_url(url):
            raise InvalidURLError("Invalid or unsupported TikTok URL.")

        if quality not in VIDEO_QUALITY:
            quality = "best"

        output_template = str(self.download_dir / "%(id)s.%(ext)s")

        options = {
            "format": VIDEO_QUALITY[quality],
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
            "concurrent_fragment_downloads": 4,
            "restrictfilenames": True,
            "windowsfilenames": True,
            "continuedl": True,
            "overwrites": True,
            "postprocessors": [],
        }

        if progress_callback:
            options["progress_hooks"] = [progress_callback]

        return await self._download_with_retry(
            url=url,
            options=options,
            media_type="video",
        )

    # ========================================================
    # DOWNLOAD MP3
    # ========================================================

    async def download_mp3(
        self,
        url: str,
        quality: str = "192",
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> str:
        if not self.is_valid_url(url):
            raise InvalidURLError("Invalid or unsupported TikTok URL.")

        if not self.check_ffmpeg():
            raise FFmpegNotFoundError("FFmpeg is not installed.")

        if quality not in MP3_QUALITY:
            quality = "192"

        output_template = str(self.download_dir / "%(id)s.%(ext)s")

        options = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
            "concurrent_fragment_downloads": 4,
            "restrictfilenames": True,
            "windowsfilenames": True,
            "continuedl": True,
            "overwrites": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": MP3_QUALITY[quality],
                },
            ],
        }

        if progress_callback:
            options["progress_hooks"] = [progress_callback]

        return await self._download_with_retry(
            url=url,
            options=options,
            media_type="mp3",
        )

    # ========================================================
    # RETRY ENGINE
    # ========================================================

    async def _download_with_retry(
        self,
        url: str,
        options: dict,
        media_type: str,
    ) -> str:
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            downloaded_files = set()

            try:
                def run_download():
                    with yt_dlp.YoutubeDL(options) as ydl:
                        info = ydl.extract_info(url, download=True)
                        return ydl.prepare_filename(info)

                original_file = await asyncio.wait_for(
                    asyncio.to_thread(run_download),
                    timeout=DOWNLOAD_TIMEOUT,
                )

                final_file = self._find_final_file(original_file, media_type)

                if not final_file:
                    raise DownloadFailedError("Downloaded file was not found.")

                downloaded_files.add(final_file)

                size_mb = self.get_file_size_mb(final_file)

                if (
                    self.max_file_size_mb > 0
                    and size_mb > self.max_file_size_mb
                ):
                    self.cleanup(final_file)
                    raise FileTooLargeError(f"File is too large: {size_mb:.2f} MB")

                self.cleanup_old_files()
                return final_file

            except asyncio.TimeoutError as error:
                last_error = error
            except Exception as error:
                last_error = error

            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * attempt)

        raise DownloadFailedError(
            f"Download failed after {MAX_RETRIES} attempts: {last_error}"
        )

    # ========================================================
    # FIND FINAL FILE
    # ========================================================

    def _find_final_file(
        self,
        original_file: str,
        media_type: str,
    ) -> Optional[str]:
        original_path = Path(original_file)

        if media_type == "mp3":
            mp3_file = original_path.with_suffix(".mp3")
            if mp3_file.exists():
                return str(mp3_file)

        if media_type == "video":
            if original_path.exists():
                if original_path.suffix.lower() == ".mp4":
                    return str(original_path)

            mp4_file = original_path.with_suffix(".mp4")
            if mp4_file.exists():
                return str(mp4_file)

        try:
            files = list(self.download_dir.glob("*"))

            if media_type == "mp3":
                candidates = [f for f in files if f.suffix.lower() == ".mp3"]
            else:
                candidates = [
                    f for f in files if f.suffix.lower() in (".mp4", ".mkv", ".webm")
                ]

            if candidates:
                candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                return str(candidates[0])

        except Exception:
            pass

        return None


# ============================================================
# EXPORTED FUNCTIONS
# ============================================================

_downloader = NuthhDownloader()


async def download(
    url: str,
    quality: str = "best",
    progress_callback=None,
) -> str:
    """Default download function (calls download_video)."""
    return await _downloader.download_video(
        url=url,
        quality=quality,
        progress_callback=progress_callback,
    )


async def download_video(
    url: str,
    quality: str = "best",
    progress_callback=None,
) -> str:
    return await _downloader.download_video(
        url=url,
        quality=quality,
        progress_callback=progress_callback,
    )


async def download_mp3(
    url: str,
    quality: str = "192",
    progress_callback=None,
) -> str:
    return await _downloader.download_mp3(
        url=url,
        quality=quality,
        progress_callback=progress_callback,
    )


def cleanup_file(file_path: str):
    _downloader.cleanup(file_path)


def cleanup_old_files():
    _downloader.cleanup_old_files()
