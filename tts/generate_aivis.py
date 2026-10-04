#!/usr/bin/env python3
"""
Generate Episode 1 narration with a local AivisSpeech Engine.

Requirements:
- Python 3.9+
- AivisSpeech / AivisSpeech Engine running on http://127.0.0.1:10101
- At least one installed AivisSpeech voice model
- Optional: ffmpeg (for MP3 conversion). Without ffmpeg, WAV files are kept and
  episode01-video.html can play them directly.

No API key and no third-party Python package are required.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCRIPT = ROOT / "tts" / "episode01-script.json"
DEFAULT_ENGINE = "http://127.0.0.1:10101"


class AivisError(RuntimeError):
    pass


def request_json(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise AivisError(f"AivisSpeech Engine に接続できません: {url}\n{exc}") from exc


def request_bytes(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            return res.read()
    except urllib.error.URLError as exc:
        raise AivisError(f"AivisSpeech Engine の音声合成に失敗しました: {url}\n{exc}") from exc


def list_styles(engine: str) -> list[dict]:
    speakers = request_json(f"{engine.rstrip('/')}/speakers")
    rows: list[dict] = []
    for speaker in speakers:
        speaker_name = speaker.get("name", "Unknown")
        speaker_uuid = speaker.get("speaker_uuid", "")
        for style in speaker.get("styles", []):
            rows.append(
                {
                    "speaker_name": speaker_name,
                    "speaker_uuid": speaker_uuid,
                    "style_name": style.get("name", "Default"),
                    "style_id": int(style["id"]),
                }
            )
    return rows


def print_styles(styles: list[dict]) -> None:
    if not styles:
        print("利用可能な音声スタイルが見つかりません。AivisSpeech に音声モデルを追加してください。")
        return
    print("利用可能な AivisSpeech 音声:")
    for row in styles:
        print(f"  {row['style_id']:>10}  {row['speaker_name']} / {row['style_name']}")


def synthesize_wav(engine: str, speaker_id: int, text: str) -> bytes:
    params = urllib.parse.urlencode({"speaker": speaker_id, "text": text})
    query_url = f"{engine.rstrip('/')}/audio_query?{params}"
    query = request_json(query_url, method="POST")

    synth_url = f"{engine.rstrip('/')}/synthesis?speaker={speaker_id}"
    payload = json.dumps(query, ensure_ascii=False).encode("utf-8")
    return request_bytes(
        synth_url,
        method="POST",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )


def convert_to_mp3(wav_path: Path, mp3_path: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(wav_path),
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "3",
            str(mp3_path),
        ],
        check=True,
    )
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AivisSpeech で第1回動画のナレーションを一括生成します。"
    )
    parser.add_argument("--engine", default=DEFAULT_ENGINE, help=f"AivisSpeech Engine URL (default: {DEFAULT_ENGINE})")
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT, help="ナレーション原稿 JSON")
    parser.add_argument("--speaker", type=int, help="使用する style_id。省略時は最初の音声スタイルを使用")
    parser.add_argument("--list-voices", action="store_true", help="利用可能な音声スタイルを表示して終了")
    parser.add_argument(
        "--format",
        choices=("auto", "wav", "mp3"),
        default="auto",
        help="auto: ffmpeg があれば MP3、なければ WAV (default: auto)",
    )
    parser.add_argument("--keep-wav", action="store_true", help="MP3化した後も WAV を残す")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    engine = args.engine.rstrip("/")

    try:
        styles = list_styles(engine)
    except AivisError as exc:
        print(exc, file=sys.stderr)
        print(
            "\nAivisSpeech を起動してから再実行してください。"
            "\nブラウザで http://127.0.0.1:10101/docs が開けば準備完了です。",
            file=sys.stderr,
        )
        return 2

    if args.list_voices:
        print_styles(styles)
        return 0

    if not styles:
        print("音声モデルがありません。AivisSpeech に音声モデルを1つ以上追加してください。", file=sys.stderr)
        return 2

    style_ids = {row["style_id"] for row in styles}
    speaker_id = args.speaker if args.speaker is not None else styles[0]["style_id"]
    if speaker_id not in style_ids:
        print(f"style_id={speaker_id} が見つかりません。", file=sys.stderr)
        print_styles(styles)
        return 2

    selected = next(row for row in styles if row["style_id"] == speaker_id)
    print(f"使用音声: {selected['speaker_name']} / {selected['style_name']} (style_id={speaker_id})")

    script_path = args.script if args.script.is_absolute() else (ROOT / args.script)
    if not script_path.exists():
        print(f"原稿ファイルがありません: {script_path}", file=sys.stderr)
        return 2

    payload = json.loads(script_path.read_text(encoding="utf-8"))
    segments = payload.get("segments", [])
    if not segments:
        print("segments が空です。", file=sys.stderr)
        return 2

    out_dir = ROOT / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg_available = shutil.which("ffmpeg") is not None
    if args.format == "mp3" and not ffmpeg_available:
        print(
            "MP3 出力には ffmpeg が必要です。\n"
            "Homebrew がある場合: brew install ffmpeg\n"
            "または --format wav / --format auto を使ってください。",
            file=sys.stderr,
        )
        return 2

    generated: list[Path] = []

    for i, segment in enumerate(segments, start=1):
        text = str(segment.get("text", "")).strip()
        if not text:
            print(f"[{i}/{len(segments)}] 空の原稿なのでスキップ")
            continue

        requested = Path(segment.get("file", f"audio/ep01-{i:02d}.mp3"))
        stem = requested.stem
        wav_path = out_dir / f"{stem}.wav"
        mp3_path = out_dir / f"{stem}.mp3"

        print(f"[{i}/{len(segments)}] 合成中: {text[:32]}{'…' if len(text) > 32 else ''}")
        try:
            wav_bytes = synthesize_wav(engine, speaker_id, text)
        except AivisError as exc:
            print(exc, file=sys.stderr)
            return 3

        wav_path.write_bytes(wav_bytes)

        want_mp3 = args.format == "mp3" or (args.format == "auto" and ffmpeg_available)
        if want_mp3:
            try:
                convert_to_mp3(wav_path, mp3_path)
            except subprocess.CalledProcessError as exc:
                print(f"ffmpeg 変換に失敗しました: {exc}", file=sys.stderr)
                return 4
            generated.append(mp3_path)
            if not args.keep_wav:
                wav_path.unlink(missing_ok=True)
            print(f"  -> {mp3_path.relative_to(ROOT)}")
        else:
            generated.append(wav_path)
            print(f"  -> {wav_path.relative_to(ROOT)}")

    print("\n完了しました。")
    if args.format == "auto" and not ffmpeg_available:
        print("ffmpeg が見つからなかったため WAV で保存しました。動画ページは WAV に自動フォールバックします。")
    print("生成ファイル:")
    for path in generated:
        print(f"  {path.relative_to(ROOT)}")
    print("\nブラウザで episode01-video.html を開いて音声を確認してください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
