# Playlist Saver

A small program for Windows that saves a Spotify playlist as MP3 files on your computer. Paste the playlist link, pick the matches that look right, click one button. Done.

No installs. No accounts. No setup.

---

## Download

### [⬇ Click here to download Playlist Saver](https://github.com/RodrigoEMDM/SpotifyToMP3/releases/latest/download/PlaylistSaver.exe)

That link gives you one file: **`PlaylistSaver.exe`**. Save it anywhere you want — Desktop, Documents, a USB drive, wherever. The MP3s you download will appear in a folder right next to that file.

---

## How to use it

### Step 1 — Get past the Windows warning (first time only)

Because this program isn't signed by a big company, Windows will show a scary blue warning the first time you open it. Here's how to handle it:

**Easiest way (recommended):**
1. Find the `PlaylistSaver.exe` file you just downloaded.
2. **Right-click** it → choose **Properties**.
3. At the bottom of the window, check the box that says **Unblock**.
4. Click **Apply** → **OK**.

Now when you open it, no warning.

**If you skipped that and got the warning anyway:**
A blue box appears saying *"Windows protected your PC"*.
1. Click the small text **"More info"**.
2. A new button appears: **"Run anyway"**. Click it.

This is normal for any program made by an individual instead of a big company. Your antivirus may also pop up — it's safe to allow.

### Step 2 — Open the program

Double-click **`PlaylistSaver.exe`**.

Two things happen:
- A small black window appears with some text. **Don't close it** — that's the program running.
- Your web browser opens to a page that looks like this:

> The page title says "Playlist Saver" with a box to paste a link.

If the browser doesn't open automatically, open Chrome / Edge / Firefox and go to: **http://127.0.0.1:5000**

### Step 3 — Get a Spotify playlist link

1. Open Spotify (app or website).
2. Find the playlist you want.
3. Click the three dots **`...`** next to the playlist name → **Share** → **Copy link to playlist**.

> The playlist has to be **public**. If it's private, this won't work. Most playlists are public by default.

### Step 4 — Paste and load

1. Paste the link into the box on the Playlist Saver page.
2. Click **Load playlist**.
3. Wait a few seconds. The list of songs appears, each one paired with a match from YouTube Music.

### Step 5 — Check the matches (optional)

For each song, the program shows the version it found on YouTube Music — with a thumbnail, the channel name, and how long it is.

- If a match looks wrong, click **`next →`** to try a different version.
- If you don't want a song downloaded at all, click **`Skip this track`**.
- Don't want to bother checking? Skip this step — the first match is usually right.

### Step 6 — Download

Click the big green **Download all** button at the bottom.

Wait. Each song takes a few seconds. You'll see a progress bar and the rows turn green as they finish.

When it says **"Finished"**, your MP3s are in a folder called **`downloads`** right next to `PlaylistSaver.exe`.

### Step 7 — Done

Close the black window to quit. Open the `downloads` folder and listen to your music.

---

## Important notes

- **For personal use only.** Don't sell these files or share them publicly. Respect the artists.
- **Sound quality:** Songs come from YouTube Music at 192 kbps. Good for casual listening; not studio quality.
- **Sometimes a song won't have a match** — that's normal. The row will say "No matches found" and that song gets skipped automatically.
- **MP3s have title, artist, and album cover** baked in, so they look right in any music player.

---

## Help / troubleshooting

<details>
<summary><b>Windows says it's a virus</b></summary>

Some antivirus programs flag this kind of file. It's not a virus — it's a flagging of the *tool* used to bundle it (PyInstaller), which is also used by some malware authors. The full source code is in this repository so you can verify it.

If your AV deletes the file, you may need to add an exception, or build the program yourself (see "For developers" below).
</details>

<details>
<summary><b>Browser doesn't open by itself</b></summary>

Open Chrome / Edge / Firefox manually and go to **http://127.0.0.1:5000** while the black window is still open.
</details>

<details>
<summary><b>"Is the playlist public?" error</b></summary>

The playlist must be public. On Spotify: open the playlist → three dots `...` → if you see **"Make public"**, click it.
</details>

<details>
<summary><b>"This job is no longer on the server"</b></summary>

This happens if you closed the black window and reopened it, but left the browser tab open. Just reload the browser tab and paste the link again.
</details>

<details>
<summary><b>One specific song won't download</b></summary>

Click **`next →`** on that row to try a different YouTube Music match. Some songs only exist as covers or live versions on YouTube — pick the closest one or skip it.
</details>

---

## For developers

<details>
<summary><b>How it works</b></summary>

- **Spotify metadata** is scraped from the public embed page at `https://open.spotify.com/embed/playlist/<id>`. No API key required.
- **Search** uses `ytmusicapi` with the "songs" filter for clean artist-uploaded tracks. Falls back to regular YouTube search if YouTube Music has no match.
- **Download** uses `yt-dlp`; **conversion** uses `ffmpeg`; **tagging** uses `mutagen`.
- **UI** is a Flask app serving a single HTML page that polls a background worker for progress.

Everything runs on `127.0.0.1` (your own computer). Nothing is sent to a server I control.
</details>

<details>
<summary><b>Run from source</b></summary>

Requires Python 3.10+ and `ffmpeg` on your `PATH`.

```bash
git clone https://github.com/RodrigoEMDM/SpotifyToMP3.git
cd SpotifyToMP3
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000`.
</details>

<details>
<summary><b>Build the .exe yourself</b></summary>

1. Download `ffmpeg-release-essentials.zip` from <https://www.gyan.dev/ffmpeg/builds/>, extract it, and copy `ffmpeg.exe` + `ffprobe.exe` from its `bin/` folder into the project root.
2. ```
   pip install -r requirements.txt
   python build.py
   ```
3. Output: `dist\PlaylistSaver.exe`.
</details>

<details>
<summary><b>Project layout</b></summary>

```
app.py              Flask app + background worker
build.py            PyInstaller build script
requirements.txt    Python dependencies
templates/
  index.html        Single-page UI
README.md
.gitignore
```
</details>

---

*Made for personal use. Not affiliated with Spotify or YouTube.*
