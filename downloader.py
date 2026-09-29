import os
import re
import asyncio

import yt_dlp


TIKTOK_URL = re.compile(
    r"^https?://"
    r"(www\.)?"
    r"(tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com)/",
    re.I
)


def valid_tiktok_url(url):

    return bool(
        TIKTOK_URL.match(
            url.strip()
        )
    )


def _download(
    url,
    out_dir,
    audio=False
):

    os.makedirs(
        out_dir,
        exist_ok=True
    )

    template = os.path.join(
        out_dir,
        "%(id)s.%(ext)s"
    )

    if audio:

        options = {

            "format":
                "bestaudio/best",

            "outtmpl":
                template,

            "noplaylist":
                True,

            "quiet":
                True,

            "no_warnings":
                True,

            "postprocessors": [

                {
                    "key":
                        "FFmpegExtractAudio",

                    "preferredcodec":
                        "mp3",

                    "preferredquality":
                        "192"
                }

            ]
        }

    else:

        options = {

            "format":
                "bv*+ba/b",

            "outtmpl":
                template,

            "merge_output_format":
                "mp4",

            "noplaylist":
                True,

            "quiet":
                True,

            "no_warnings":
                True
        }

    with yt_dlp.YoutubeDL(options) as ydl:

        info = ydl.extract_info(
            url,
            download=True
        )

        path = ydl.prepare_filename(
            info
        )

        if audio:

            path = (
                os.path.splitext(path)[0]
                + ".mp3"
            )

        title = (
            info.get("title")
            or "TikTok"
        )

        return path, title


async def download(
    url,
    out_dir,
    audio=False
):

    return await asyncio.to_thread(
        _download,
        url,
        out_dir,
        audio
    )
