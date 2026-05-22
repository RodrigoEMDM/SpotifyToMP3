"""Build PlaylistSaver.exe with PyInstaller.

Before running:
  1. Drop ffmpeg.exe and ffprobe.exe into this folder.
     Get them from https://www.gyan.dev/ffmpeg/builds/ (the
     "release essentials" zip). Extract, then copy ffmpeg.exe
     and ffprobe.exe out of its bin/ folder into here.
  2. pip install -r requirements.txt
  3. python build.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
FFMPEG = ROOT / "ffmpeg.exe"
FFPROBE = ROOT / "ffprobe.exe"


def main():
    missing = [p.name for p in (FFMPEG, FFPROBE) if not p.exists()]
    if missing:
        print("ERROR: missing required binaries in this folder:")
        for name in missing:
            print(f"  - {name}")
        print()
        print("Download them from https://www.gyan.dev/ffmpeg/builds/")
        print("(the 'release essentials' zip), extract, and copy the .exe files")
        print(f"from its bin/ folder into:")
        print(f"  {ROOT}")
        sys.exit(1)

    print("Installing build dependencies...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "--upgrade",
        "pyinstaller",
    ])

    print("Running PyInstaller...")
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name", "PlaylistSaver",
        "--add-data", "templates;templates",
        "--add-binary", "ffmpeg.exe;.",
        "--add-binary", "ffprobe.exe;.",
        "--collect-all", "yt_dlp",
        "--collect-all", "ytmusicapi",
        "app.py",
    ]
    subprocess.check_call(args, cwd=str(ROOT))

    out = ROOT / "dist" / "PlaylistSaver.exe"
    print()
    print("=" * 60)
    if out.exists():
        size_mb = out.stat().st_size / (1024 * 1024)
        print(f"  Built: {out}")
        print(f"  Size:  {size_mb:.1f} MB")
        print()
        print("  Send this single .exe to your brother.")
        print("  He just double-clicks it. Browser will open automatically.")
        print("  MP3s land in a 'downloads' folder next to the .exe.")
    else:
        print("  Build appears to have finished but the .exe was not found.")
        print("  Check the PyInstaller output above for errors.")
    print("=" * 60)


if __name__ == "__main__":
    main()
