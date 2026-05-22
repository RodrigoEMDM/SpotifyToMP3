# Playlist Saver

A small local app for downloading MP3 versions of the tracks in a public Spotify playlist. It reads the playlist's track list from Spotify's public embed page, finds each song on YouTube Music, lets you review the matches one-by-one, and then downloads them all at once. Everything runs on your own machine — no servers, no logins.

> **For personal use only.** This tool helps you download audio from public sources for personal/offline listening. Don't use it for anything commercial. Respect the terms of service of Spotify and YouTube, and the rights of artists.

## What it does

1. You paste a public Spotify playlist URL.
2. The app fetches the playlist's track list directly from Spotify's public embed page (no Spotify account or API key needed).
3. For each track, it searches YouTube Music for the best match.
4. The app shows you the matches side-by-side and lets you:
   - Cycle through alternate matches per track (`prev` / `next`)
   - Skip individual tracks
5. When everything looks right, click **Download all**. Audio is fetched with `yt-dlp`, converted to MP3 with `ffmpeg`, and tagged with title/artist/cover art using `mutagen`.

The result is a folder of clean, tagged `.mp3` files.

## How to use it

### Option A — Pre-built `.exe` (Windows, easiest)

Grab `PlaylistSaver.exe` from the [Releases](../../releases) page. Double-click it.

- A small console window opens, and your default browser opens to `http://127.0.0.1:5000`.
- MP3s land in a `downloads/` folder created next to the `.exe`.
- To quit, close the console window.

> The first time you run it, Windows SmartScreen will warn you about an unrecognized publisher (the `.exe` is unsigned). Click **More info → Run anyway**, or right-click the file → Properties → check **Unblock** → Apply, then try again.

### Option B — Run from source (any OS)

Requires Python 3.10+ and `ffmpeg` on your `PATH`.

```bash
git clone https://github.com/RodrigoEMDM/SpotifyToMP3.git
cd SpotifyToMP3
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000` in a browser.

## Building the `.exe` yourself

Requires Python 3.10+ on Windows.

1. Download `ffmpeg-release-essentials.zip` from <https://www.gyan.dev/ffmpeg/builds/>, extract it, and copy `ffmpeg.exe` and `ffprobe.exe` from its `bin/` folder into the project root (next to `app.py`).
2. Install dependencies and run the build:
   ```
   pip install -r requirements.txt
   python build.py
   ```
3. The output is `dist\PlaylistSaver.exe` — a single self-contained file you can send to anyone.

## How it works

- **Spotify metadata** — scraped from the public embed page at `https://open.spotify.com/embed/playlist/<id>`. No API key required, but the playlist must be public.
- **Search** — `ytmusicapi` queries YouTube Music with the "songs" filter, which returns clean artist-uploaded tracks (no music videos, lyric videos, or covers by default). If a track has no YouTube Music match, it falls back to a regular YouTube search.
- **Download** — `yt-dlp` fetches the chosen audio stream; `ffmpeg` converts it to 192 kbps MP3.
- **Tagging** — `mutagen` writes title/artist/album tags and embeds the playlist's cover art.
- **UI** — a tiny Flask app serving a single HTML page; it polls a background worker for progress updates.

## Caveats

- **Public playlists only.** The embed scrape only works for public playlists. Private/collaborative playlists won't work.
- **It's a YouTube Music match, not the original Spotify audio.** Sometimes the top match isn't perfect (e.g., a re-recorded or remastered version). That's why the per-track "next match" / "skip" controls exist.
- **No album field.** The Spotify embed page exposes title + artist + duration but not the album. MP3s get title/artist tags + the playlist's cover art instead.
- **YouTube can rate-limit.** Big playlists (hundreds of tracks) downloaded back-to-back might hit a slowdown. Smaller playlists work without issue.

## Project layout

```
app.py              Flask app + worker logic
build.py            PyInstaller build script
requirements.txt    Python deps
templates/
  index.html        Single-page UI
ffmpeg.exe          (added by you before building)
ffprobe.exe         (added by you before building)
```

## License

For personal/educational use. No warranty.
