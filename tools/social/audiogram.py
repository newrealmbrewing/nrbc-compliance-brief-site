#!/usr/bin/env python3
"""Render the daily audiogram MP4: the edition's OG card over black with a
green live waveform and a progress bar, synced to the episode audio.

Usage: python3 tools/social/audiogram.py --date YYYY-MM-DD --mp3 /path/episode.mp3 --out /path/audiogram.mp4
Requires ffmpeg. Output: 1280x720 H.264 + AAC (loudness-normalized to
-16 LUFS), faststart, suitable for LinkedIn native video upload.
"""
import argparse, os, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def duration_of(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    return float(out.stdout.strip())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--mp3", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    card = os.path.join(ROOT, "assets", "og", f"{a.date}.png")
    if not os.path.exists(card):
        card = os.path.join(ROOT, "assets", "og-banner.png")
    dur = duration_of(a.mp3)
    # Layout: OG card (1200x630) scaled to 980x515, centered, upper area;
    # mirrored waveform band below it, boosted for visual liveliness;
    # 6px progress bar along the bottom edge.
    fc = (
        # audio: normalize once, then split — one copy to publish, one boosted copy to draw
        "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[an];"
        "[an]asplit=2[aout][aviz];"
        "[aviz]volume=3.5[aloud];"
        "[0:v]scale=980:515[card];"
        f"color=c=black:s=1280x720:d={dur:.2f}[bg];"
        "[bg][card]overlay=x=150:y=34:shortest=0[base];"
        "[aloud]showwaves=s=1180x160:mode=cline:rate=25:colors=0x00B050:scale=sqrt:draw=full[wav];"
        "[base][wav]overlay=x=50:y=550[withwave];"
        f"color=c=0x00B050:s=1280x6:d={dur:.2f}[bar];"
        f"[withwave][bar]overlay=y=714:x='-1280+1280*t/{dur:.2f}':shortest=1[v]"
    )
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-loop", "1", "-i", card, "-i", a.mp3,
           "-filter_complex", fc, "-map", "[v]", "-map", "[aout]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-pix_fmt", "yuv420p",
           "-r", "25", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
           "-t", f"{dur:.2f}", a.out]
    subprocess.run(cmd, check=True)
    size = os.path.getsize(a.out)
    print(f"audiogram: {a.out} ({size//1024} KB, {dur:.0f}s)")

if __name__ == "__main__":
    main()
