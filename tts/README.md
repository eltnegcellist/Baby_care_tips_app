# 第1回動画：AivisSpeech ナレーション生成

第1回の60秒動画用ナレーションを、Mac上の **AivisSpeech** で無料・ローカル生成するための手順です。

生成対象:

- `audio/ep01-01.mp3` ～ `audio/ep01-06.mp3`
- `ffmpeg` がない場合は `.wav` で保存されます
- `episode01-video.html` は **MP3を優先し、なければWAVへ自動フォールバック**します

APIキーは不要です。

## 1. AivisSpeechを起動する

AivisSpeechを起動し、使いたい音声モデルを1つ以上追加してください。

エンジン起動後、ブラウザで以下が開ければ準備完了です。

```
http://127.0.0.1:10101/docs
```

## 2. 利用できる声を確認する

リポジトリのルートで実行します。

```bash
python3 tts/generate_aivis.py --list-voices
```

表示例:

```
利用可能な AivisSpeech 音声:
   888753760  Voice Name / Normal
```

左端の数字が `style_id` です。

## 3. 第1回の6本を一括生成する

声を指定する場合:

```bash
python3 tts/generate_aivis.py --speaker 888753760
```

`--speaker` を省略した場合は、AivisSpeechで最初に見つかった音声スタイルを使います。

原稿は以下です。

```
tts/episode01-script.json
```

## MP3にする場合

Macに `ffmpeg` が入っていれば、自動でMP3になります。

Homebrew利用時:

```bash
brew install ffmpeg
```

その後:

```bash
python3 tts/generate_aivis.py --speaker 888753760
```

### ffmpegを入れたくない場合

そのままでも問題ありません。

```bash
python3 tts/generate_aivis.py --format wav --speaker 888753760
```

WAVを生成し、動画ページ側が自動で読み込みます。

## 4. 動画で確認する

生成後、ローカルWebサーバーを立ち上げます。

```bash
python3 -m http.server 8000
```

ブラウザで:

```
http://localhost:8000/episode01-video.html
```

> HTMLを `file://` で直接開くより、簡易HTTPサーバー経由の方が音声ファイル確認が確実です。

## 5. 公開する

音声を確認したら、生成された `audio/` 以下をGitに追加してpushします。

例:

```bash
git add audio/
git commit -m "Add AivisSpeech narration for episode 1"
git push
```

GitHub Pagesに反映されると、第1回動画で高品質ナレーションが自動的に使われます。

## オプション

### WAVも残したい

```bash
python3 tts/generate_aivis.py --speaker 888753760 --keep-wav
```

### MP3を必須にする

```bash
python3 tts/generate_aivis.py --speaker 888753760 --format mp3
```

`ffmpeg` がない場合は、インストール方法を表示して終了します。

### EngineのURLを変える

```bash
python3 tts/generate_aivis.py --engine http://127.0.0.1:10101
```

## エラー時

### AivisSpeech Engine に接続できません

- AivisSpeechが起動しているか確認
- `http://127.0.0.1:10101/docs` が開くか確認

### 音声モデルがありません

AivisSpeech側で音声モデルを追加してから再実行します。

### 声を変えたい

```bash
python3 tts/generate_aivis.py --list-voices
```

で一覧を出し、別の `style_id` を `--speaker` に指定します。

## 実装メモ

AivisSpeech EngineのローカルAPIを使用します。

1. `GET /speakers`
2. `POST /audio_query?speaker=...&text=...`
3. `POST /synthesis?speaker=...`

既定のEngine URLは `http://127.0.0.1:10101` です。
