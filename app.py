import json
import logging
import re
import sys
import uuid
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from flask import Flask, render_template, request, jsonify
import flask.cli

import yt_dlp
from ytmusicapi import YTMusic
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
import requests


FROZEN = getattr(sys, "frozen", False)
# Bundled resources (templates, ffmpeg) live next to the script in dev,
# and in sys._MEIPASS at runtime when PyInstaller --onefile-extracted.
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
# Where to actually save MP3s — next to the .exe in production, next to app.py in dev.
APP_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).parent

DOWNLOAD_DIR = APP_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Tell yt-dlp where to find the bundled ffmpeg/ffprobe binaries.
FFMPEG_LOCATION = str(RESOURCE_DIR) if FROZEN else None

SEARCH_RESULTS_PER_TRACK = 10
SEARCH_WORKERS = 6

app = Flask(__name__, template_folder=str(RESOURCE_DIR / "templates"))


class _QuietStatusFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        return "/status/" not in msg


logging.getLogger("werkzeug").addFilter(_QuietStatusFilter())

ytmusic = YTMusic()


class Job:
    def __init__(self):
        self.status = "fetching_playlist"  # fetching_playlist | searching | ready | downloading | done | error
        self.tracks = []
        self.candidates = {}        # track_index -> list[candidate]
        self.selected_index = {}    # track_index -> int
        self.skipped = set()        # track_index
        self.search_done_count = 0
        self.download_done = 0
        self.download_total = 0
        self.current_download_index = None
        self.log = []
        self.error = None
        self.start_download_event = threading.Event()
        self.lock = threading.Lock()


jobs = {}
jobs_lock = threading.Lock()


def extract_playlist_id(url):
    m = re.search(r"playlist[/:]([A-Za-z0-9]+)", url)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9]{22}", url):
        return url
    return None


def _walk_find(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _walk_find(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _walk_find(v, key)
            if r is not None:
                return r
    return None


def get_playlist_tracks(playlist_id):
    url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        r.text, re.DOTALL,
    )
    if not m:
        raise RuntimeError("Could not find playlist data on Spotify embed page (layout may have changed)")
    data = json.loads(m.group(1))

    track_list = _walk_find(data, "trackList") or []
    if not track_list:
        raise RuntimeError("Spotify embed page returned no tracks. Is the playlist public?")

    playlist_cover = None
    cover_art = _walk_find(data, "coverArt")
    if isinstance(cover_art, dict):
        sources = cover_art.get("sources") or []
        if sources:
            playlist_cover = sources[-1].get("url")

    tracks = []
    for t in track_list:
        title = t.get("title")
        if not title:
            continue
        tracks.append({
            "title": title,
            "artist": t.get("subtitle") or "",
            "cover_url": playlist_cover,
            "duration_ms": t.get("duration") or t.get("durationMilliseconds"),
        })
    return tracks


def sanitize(name):
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


def format_duration(seconds):
    if seconds is None:
        return "?"
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def search_ytmusic(query, n=SEARCH_RESULTS_PER_TRACK):
    try:
        results = ytmusic.search(query, filter="songs", limit=n) or []
    except Exception:
        results = []
    out = []
    for r in results[:n]:
        vid = r.get("videoId")
        if not vid:
            continue
        artists = ", ".join(a["name"] for a in (r.get("artists") or []) if a.get("name"))
        album = ""
        if isinstance(r.get("album"), dict):
            album = r["album"].get("name") or ""
        thumbs = r.get("thumbnails") or []
        thumb = thumbs[-1]["url"] if thumbs else None
        dur_s = r.get("duration_seconds")
        dur_str = format_duration(dur_s) if dur_s else (r.get("duration") or "?")
        channel_label = artists or ""
        if album:
            channel_label = f"{artists}  ({album})" if artists else album
        out.append({
            "title": r.get("title"),
            "url": f"https://music.youtube.com/watch?v={vid}",
            "channel": channel_label,
            "duration_str": dur_str,
            "thumbnail": thumb,
            "source": "YouTube Music",
        })
    return out


def search_youtube_fallback(query, n=SEARCH_RESULTS_PER_TRACK):
    ydl_opts = {
        "quiet": True, "no_warnings": True,
        "extract_flat": True, "skip_download": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    entries = info.get("entries") or []
    out = []
    for e in entries:
        if not e:
            continue
        vid = e.get("id")
        url = e.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else None)
        thumb = None
        thumbs = e.get("thumbnails")
        if thumbs:
            thumb = thumbs[-1].get("url")
        out.append({
            "title": e.get("title"),
            "url": url,
            "channel": e.get("channel") or e.get("uploader") or "",
            "duration_str": format_duration(e.get("duration")),
            "thumbnail": thumb,
            "source": "YouTube",
        })
    return out


def search_candidates(query, n=SEARCH_RESULTS_PER_TRACK):
    results = search_ytmusic(query, n)
    if results:
        return results
    try:
        return search_youtube_fallback(query, n)
    except Exception:
        return []


def download_from_url(url, track):
    filename_base = sanitize(f"{track['artist']} - {track['title']}")
    outtmpl = str(DOWNLOAD_DIR / f"{filename_base}.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": True, "no_warnings": True, "noprogress": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }
    if FFMPEG_LOCATION:
        ydl_opts["ffmpeg_location"] = FFMPEG_LOCATION
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    mp3_path = DOWNLOAD_DIR / f"{filename_base}.mp3"
    if not mp3_path.exists():
        return False

    try:
        audio = EasyID3(mp3_path)
    except Exception:
        audio = EasyID3()
        audio.save(mp3_path)
        audio = EasyID3(mp3_path)
    audio["title"] = track["title"]
    audio["artist"] = track["artist"]
    audio.save()

    if track.get("cover_url"):
        try:
            r = requests.get(track["cover_url"], timeout=10)
            if r.ok:
                id3 = ID3(mp3_path)
                id3.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=r.content))
                id3.save()
        except Exception:
            pass
    return True


def run_job(job, playlist_url):
    try:
        playlist_id = extract_playlist_id(playlist_url)
        if not playlist_id:
            with job.lock:
                job.status = "error"
                job.error = "Could not parse playlist URL"
            return

        with job.lock:
            job.status = "fetching_playlist"
        tracks = get_playlist_tracks(playlist_id)
        with job.lock:
            job.tracks = tracks
            job.status = "searching"

        def do_search(i):
            t = tracks[i]
            return i, search_candidates(f"{t['artist']} - {t['title']}")

        with ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as ex:
            futures = [ex.submit(do_search, i) for i in range(len(tracks))]
            for fut in as_completed(futures):
                try:
                    i, cands = fut.result()
                except Exception:
                    continue
                with job.lock:
                    job.candidates[i] = cands
                    job.selected_index[i] = 0
                    job.search_done_count += 1

        with job.lock:
            job.status = "ready"

        job.start_download_event.wait()

        with job.lock:
            job.status = "downloading"
            to_download = [
                i for i in range(len(tracks))
                if i not in job.skipped and job.candidates.get(i)
            ]
            job.download_total = len(to_download)
            job.download_done = 0

        for i in to_download:
            track = tracks[i]
            label = f"{track['artist']} - {track['title']}"
            cands = job.candidates.get(i) or []
            sel = job.selected_index.get(i, 0)
            if sel >= len(cands):
                sel = 0
            cand = cands[sel]
            with job.lock:
                job.current_download_index = i
            try:
                ok = download_from_url(cand["url"], track)
                if ok:
                    job.log.append(f"OK    {label}  <-  {cand['title']}")
                else:
                    job.log.append(f"FAIL  {label}  (mp3 not produced)")
            except Exception as e:
                job.log.append(f"FAIL  {label}  ({e})")
            with job.lock:
                job.download_done += 1

        with job.lock:
            job.current_download_index = None
            job.status = "done"
    except Exception as e:
        with job.lock:
            job.status = "error"
            job.error = str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/download", methods=["POST"])
def start_download():
    url = request.form.get("url", "").strip()
    if not url:
        return jsonify({"error": "Missing URL"}), 400
    job = Job()
    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = job
    threading.Thread(target=run_job, args=(job, url), daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "unknown job"}), 404
    with job.lock:
        track_list = []
        for i, t in enumerate(job.tracks):
            cands = job.candidates.get(i)
            sel = job.selected_index.get(i, 0)
            cand = None
            if cands:
                if sel >= len(cands):
                    sel = 0
                cand = cands[sel]
            track_list.append({
                "index": i,
                "title": t["title"],
                "artist": t["artist"],
                "duration_ms": t.get("duration_ms"),
                "current_candidate": cand,
                "candidate_index": sel,
                "candidate_count": len(cands) if cands is not None else 0,
                "search_done": i in job.candidates,
                "skipped": i in job.skipped,
            })
        return jsonify({
            "status": job.status,
            "tracks": track_list,
            "search_done_count": job.search_done_count,
            "total": len(job.tracks),
            "download_done": job.download_done,
            "download_total": job.download_total,
            "current_download_index": job.current_download_index,
            "log": job.log[-300:],
            "error": job.error,
        })


@app.route("/track_action/<job_id>", methods=["POST"])
def track_action(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "unknown job"}), 404
    try:
        ti = int(request.form.get("track_index", "-1"))
    except ValueError:
        ti = -1
    action = request.form.get("action", "")
    with job.lock:
        if ti < 0 or ti >= len(job.tracks):
            return jsonify({"error": "bad track_index"}), 400
        if job.status not in ("searching", "ready"):
            return jsonify({"error": f"cannot change selection in status {job.status}"}), 409
        cands = job.candidates.get(ti, [])
        if action == "next":
            cur = job.selected_index.get(ti, 0)
            if cands and cur + 1 < len(cands):
                job.selected_index[ti] = cur + 1
        elif action == "prev":
            cur = job.selected_index.get(ti, 0)
            if cur > 0:
                job.selected_index[ti] = cur - 1
        elif action == "skip":
            job.skipped.add(ti)
        elif action == "unskip":
            job.skipped.discard(ti)
        else:
            return jsonify({"error": "bad action"}), 400
    return jsonify({"ok": True})


@app.route("/start_download/<job_id>", methods=["POST"])
def start_download_endpoint(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "unknown job"}), 404
    job.start_download_event.set()
    return jsonify({"ok": True})


def _open_browser():
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    print("=" * 52)
    print("  Playlist Saver")
    print("=" * 52)
    print()
    print(f"  MP3s will be saved to:")
    print(f"    {DOWNLOAD_DIR}")
    print()
    print("  A browser window will open in a moment.")
    print("  If it does not, open http://127.0.0.1:5000")
    print()
    print("  To quit: close this window.")
    print("=" * 52)
    print()
    threading.Timer(1.5, _open_browser).start()
    flask.cli.show_server_banner = lambda *a, **kw: None
    app.run(host="127.0.0.1", port=5000, debug=False)
