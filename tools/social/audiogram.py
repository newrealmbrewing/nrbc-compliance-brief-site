#!/usr/bin/env python3
"""Render the daily audiogram MP4: the edition's OG card over black with a
green live waveform, synced to the episode audio.

Usage: python3 tools/social/audiogram.py --date YYYY-MM-DD --mp3 /path/episode.mp3 --out /path/audiogram.mp4
Requires ffmpeg. Output: 1280x720 H.264 + AAC, faststart, suitable for
LinkedIn native video upload (well under the 15s–30min duration window).
"""
import argparse, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--mp3", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    card = os.path.join(ROOT, "assets", "og", f"{a.date}.png")
    if not os.path.exists(card):
        card = os.path.join(ROOT, "assets", "og-banner.png")
    # OG card (1200x630) scaled to 960x504, centered horizontally, near the top;
    # waveform strip (brand green on black) across the lower band.
    fc = (
        "[0:v]scale=960:504[card];"
        "color=c=black:s=1280x720:d=1[bg];"
        "[bg][card]overlay=x=160:y=48:shortest=0[base];"
        "[1:a]showwaves=s=1120x120:mode=cline:rate=25:colors=0x00B050[wav];"
        "[base][wav]overlay=x=80:y=580:shortest=1[v]"
    )
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-loop", "1", "-i", card, "-i", a.mp3,
           "-filter_complex", fc, "-map", "[v]", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
           "-r", "25", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
           a.out]
    subprocess.run(cmd, check=True)
    size = os.path.getsize(a.out)
    print(f"audiogram: {a.out} ({size//1024} KB)")

if __name__ == "__main__":
    main()
