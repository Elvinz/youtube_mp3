#!/usr/bin/env python3
"""
Скрипт для скачивания только аудиодорожки с YouTube.
По умолчанию скачивает в MP3 с максимальным битрейтом.
Поддерживает автоматические повторные попытки при обрывах сети
и докачку недокачанных файлов.

Использование:
    python download_audio.py <URL> [--format mp3|m4a|wav] [--output DIR]
                                         [--quality 0-9] [--retries N] [--retry-delay SEC]
"""

import argparse
import sys
import time
from pathlib import Path

import yt_dlp


def download_audio(
    url: str,
    output_dir: str = ".",
    audio_format: str = "mp3",
    quality: str = "0",
    retries: int = 20,
    retry_delay: float = 2.0,
) -> None:
    """Скачивает только аудио с YouTube-видео и конвертирует в указанный формат.

    По умолчанию: MP3 с максимальным качеством (V0, ~245 kbps VBR).
    Повторяет запросы при сетевых сбоях, использует докачку при обрыве.
    """
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    # Экспоненциальная задержка между попытками: base, base*2, base*4, ...
    # с ограничением сверху, чтобы не уходить в бесконечное ожидание.
    def _sleep(n: int) -> float:
        return min(retry_delay * (2 ** n), 300)

    ydl_opts = {
        # --- Источник: только аудио, лучшее доступное ---
        "format": "bestaudio/best",
        "noplaylist": True,

        # --- Постпроцессинг: извлечь и конвертировать аудио ---
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
                # Для mp3: "0" = V0 (VBR ~245 kbps, максимальное качество).
                # Для lossless (wav/flac) параметр игнорируется.
                "preferredquality": quality,
            }
        ],

        # --- Куда сохранять ---
        "outtmpl": str(output_path / "%(title)s.%(ext)s"),
        "paths": {"temp": str(output_path)},

        # --- 🔁 Повторные попытки при сетевых сбоях ---
        "retries": retries,             # повторы основных запросов
        "fragment_retries": retries,    # повторы для фрагментов (HLS/DASH)
        "extractor_retries": retries,   # повторы при сбоях экстрактора
        "retry_sleep_functions": {
            "http": _sleep,
            "fragment": _sleep,
            "extractor": _sleep,
        },

        # --- 💾 Докачка ---
        "continuedl": True,             # продолжать .part-файлы
        "nopart": False,                # не удалять .part при ошибке

        # --- Прочее ---
        "quiet": False,
        "no_warnings": False,
        "ignoreerrors": False,
        "overwrites": False,            # не перезаписывать уже готовые файлы
    }

    print(f"[+] Скачиваю аудио: {url}")
    print(f"[+] Формат: {audio_format.upper()}, качество: V{quality} (максимум)")
    print(f"[+] Папка: {output_path}")
    print(f"[+] Повторы при сбоях: {retries}, базовая задержка: {retry_delay}s")

    # Внешний цикл: yt-dlp сам повторяет попытки, но если сеть пропала
    # надолго — YoutubeDL может выбросить исключение. Тогда даём паузу
    # и пробуем ещё раз целиком (докачка не даст скачать заново).
    attempt = 0
    while True:
        attempt += 1
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            print("[✓] Готово!")
            return
        except KeyboardInterrupt:
            print("\n[!] Прервано пользователем.")
            sys.exit(130)
        except Exception as e:
            if attempt >= retries:
                print(f"[!] Не удалось после {attempt} попыток: {e}", file=sys.stderr)
                sys.exit(1)

            wait = _sleep(attempt)
            print(
                f"[!] Ошибка (попытка {attempt}/{retries}): {e}\n"
                f"    Повтор через {wait:.0f} сек..."
            )
            try:
                time.sleep(wait)
            except KeyboardInterrupt:
                print("\n[!] Прервано пользователем.")
                sys.exit(130)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Скачивание только аудио с YouTube (по умолчанию — MP3 максимального качества)"
    )
    parser.add_argument("url", help="URL YouTube-видео")
    parser.add_argument(
        "-f", "--format",
        default="mp3",
        choices=["mp3", "m4a", "wav", "opus", "flac"],
        help="Формат аудио (по умолчанию: mp3)",
    )
    parser.add_argument(
        "-q", "--quality",
        default="0",
        help=(
            "Качество для MP3: 0 = максимальное VBR (~245 kbps), "
            "2 = ~190 kbps, 5 = ~130 kbps, 9 = минимальное (по умолчанию: 0)"
        ),
    )
    parser.add_argument(
        "-o", "--output",
        default=".",
        help="Папка для сохранения (по умолчанию: текущая)",
    )
    parser.add_argument(
        "-r", "--retries",
        type=int,
        default=20,
        help="Сколько раз повторять при сбоях (по умолчанию: 20)",
    )
    parser.add_argument(
        "-d", "--retry-delay",
        type=float,
        default=2.0,
        help="Базовая задержка между попытками в секундах (по умолчанию: 2)",
    )
    args = parser.parse_args()

    download_audio(
        url=args.url,
        output_dir=args.output,
        audio_format=args.format,
        quality=args.quality,
        retries=args.retries,
        retry_delay=args.retry_delay,
    )


if __name__ == "__main__":
    main()