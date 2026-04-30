"""Generate per-group GIFs via fal.ai (nano-banana + kling-video) + ffmpeg.

Usage:
    python scripts/generate_gif.py --group 5               # one group
    python scripts/generate_gif.py --all                    # all confirmed topics
    python scripts/generate_gif.py --placeholder            # reusable placeholder
    python scripts/generate_gif.py --group 5 --dry-run      # print prompts only

Requires:
    pip install fal-client python-dotenv requests
    ffmpeg on PATH
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows so Korean + unicode arrows don't crash.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "data.json"
TMP_DIR = ROOT / "tmp"
OUT_DIR = ROOT / "docs" / "assets" / "gifs"

# ---- Prompt templates ------------------------------------------------------
# Keyed by (slide, topic keywords) — extend as more topics are finalized.
IMAGE_PROMPTS: dict[int, dict[str, str]] = {
    3: {
        "image": (
            "Clean scientific illustration, 16:9 educational diagram aesthetic, "
            "blue-teal palette with red and gold accents. Depicts the mechanism "
            "of the 2006 TGN1412 clinical trial failure. Center: a single large "
            "T cell with a Y-shaped antibody labeled 'TGN1412 (CD28 super-"
            "agonist)' bound to its surface receptor. Concentric expanding rings "
            "of small colorful molecule dots burst outward from the T cell, "
            "labeled clearly: 'IL-2', 'IL-6', 'TNF-α', 'IFN-γ' — a cytokine "
            "storm. Around the periphery, six stylized human silhouettes with "
            "small red alert symbols above their heads. Soft red radial "
            "gradient in the background suggesting systemic inflammation. "
            "Minimalist, high contrast, clean uppercase labels, no extra text."
        ),
        "motion": (
            "Subtle camera push-in toward the central T cell. The TGN1412 "
            "antibody binds with a brief golden pulse. Cytokine molecules burst "
            "outward in expanding concentric waves with a faint red glow. The "
            "six silhouettes light up sequentially with red alert pulses above "
            "their heads. The background inflammation gradient brightens "
            "slowly. Loop-friendly, 4 seconds, no text changes."
        ),
    },
    5: {
        "image": (
            "Clean scientific illustration of the blood-brain barrier, "
            "horizontal cross-section. Left side shows blood vessel with "
            "several colorful drug molecules approaching. Center shows tightly "
            "packed endothelial cells forming the barrier with tight junctions. "
            "Right side shows brain tissue with neurons. One small drug molecule "
            "glows green and passes through the barrier toward the neurons; two "
            "larger molecules bounce off with faint red outlines. Minimalist, "
            "high contrast, educational diagram aesthetic, subtle blue-teal "
            "palette, 16:9 aspect ratio, clean labels in English: 'BLOOD', "
            "'BBB', 'BRAIN'."
        ),
        "motion": (
            "Slow cinematic push-in toward the barrier. Drug molecules drift "
            "gently from left to right. Two molecules bounce off the barrier "
            "with a faint red flash. One molecule smoothly glides through with "
            "a soft green glow trailing behind. Neurons in the brain region "
            "pulse subtly. Loop-friendly, 4 seconds, no text changes."
        ),
    },
    8: {
        "image": (
            "Clean two-panel scientific illustration on a 16:9 canvas, "
            "educational diagram aesthetic, blue-teal palette with green and "
            "red accents. Left panel labeled 'PRECLINICAL': a laboratory mouse "
            "in profile with a small green checkmark badge, a drug molecule "
            "entering its body, a tiny rising biomarker line chart in the "
            "background. Right panel labeled 'CLINICAL': a stylized human "
            "silhouette receiving the same drug molecule, a red X overlay on "
            "the body, a falling biomarker chart in the background. Between "
            "the two panels a thick horizontal arrow with the label "
            "'TRANSLATION GAP' in clean uppercase. Minimalist, high contrast, "
            "no clutter, no extra text."
        ),
        "motion": (
            "Slow cinematic camera pan from the left mouse panel to the right "
            "human panel. On the left the drug molecule glides into the mouse, "
            "a soft green pulse blooms, the rising chart line draws upward. "
            "The 'TRANSLATION GAP' arrow draws across the middle. On the right "
            "the drug molecule arrives at the human silhouette, a red X fades "
            "in, the falling chart line drops. Loop-friendly, 4 seconds, no "
            "text changes."
        ),
    },
}

PLACEHOLDER_IMAGE_PROMPT = (
    "Abstract minimalist preclinical laboratory scene, soft blue and teal "
    "gradient background, floating pipette tips, petri dishes and DNA helix "
    "silhouettes, low contrast, muted palette, 16:9, editorial illustration."
)
PLACEHOLDER_MOTION_PROMPT = (
    "Gentle floating motion of lab glassware and DNA strand, slow drift, "
    "subtle parallax, loop-friendly, 4 seconds, calm atmosphere."
)


# ---- I/O helpers -----------------------------------------------------------
def load_groups() -> list[dict]:
    if not DATA_PATH.exists():
        sys.exit(
            f"data.json not found. Run: python scripts/build_data.py\n"
            f"Expected at {DATA_PATH}"
        )
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))["groups"]


def ensure_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        sys.exit(
            "ffmpeg not found on PATH.\n"
            "Windows: winget install Gyan.FFmpeg (or https://ffmpeg.org)\n"
            "macOS:   brew install ffmpeg\n"
            "Linux:   apt-get install ffmpeg"
        )
    return path


def mp4_to_gif(mp4: Path, gif_out: Path, fps: int = 15, width: int = 800) -> None:
    ensure_ffmpeg()
    palette = mp4.with_suffix(".palette.png")
    vf_common = f"fps={fps},scale={width}:-1:flags=lanczos"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(mp4),
            "-vf", f"{vf_common},palettegen=max_colors=128",
            str(palette),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(mp4), "-i", str(palette),
            "-filter_complex", f"[0:v]{vf_common}[v];[v][1:v]paletteuse=dither=sierra2_4a",
            str(gif_out),
        ],
        check=True,
    )
    palette.unlink(missing_ok=True)


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as resp, dest.open("wb") as out:
        shutil.copyfileobj(resp, out)


def url_from_result(result, key: str = "url") -> str:
    """fal-client responses vary: dict w/ 'images'/'video', plain dict, etc."""
    if isinstance(result, dict):
        for k in ("video", "image"):
            sub = result.get(k)
            if isinstance(sub, dict) and key in sub:
                return sub[key]
        imgs = result.get("images")
        if isinstance(imgs, list) and imgs and isinstance(imgs[0], dict):
            return imgs[0].get(key) or ""
        if key in result:
            return result[key]
    raise RuntimeError(f"Unexpected fal.ai response shape: {result!r}")


# ---- fal.ai orchestration --------------------------------------------------
def run_fal(image_prompt: str, motion_prompt: str, slug: str) -> Path:
    import fal_client  # imported lazily so --dry-run works without install

    TMP_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[{slug}] nano-banana -> keyframe image...")
    img_result = fal_client.run(
        "fal-ai/nano-banana",
        arguments={"prompt": image_prompt, "num_images": 1},
    )
    img_url = url_from_result(img_result)
    img_path = TMP_DIR / f"{slug}_keyframe.png"
    download(img_url, img_path)
    print(f"[{slug}]   saved {img_path.name}")

    print(f"[{slug}] kling-video -> motion (this takes a minute)...")
    vid_result = fal_client.run(
        "fal-ai/kling-video/v2.1/standard/image-to-video",
        arguments={
            "prompt": motion_prompt,
            "image_url": img_url,
            "duration": "5",
        },
    )
    vid_url = url_from_result(vid_result)
    mp4_path = TMP_DIR / f"{slug}.mp4"
    download(vid_url, mp4_path)
    print(f"[{slug}]   saved {mp4_path.name}")
    return mp4_path


def render(slug: str, image_prompt: str, motion_prompt: str, dry: bool) -> Path | None:
    gif_out = OUT_DIR / f"{slug}.gif"
    print(f"\n=== {slug} -> {gif_out.relative_to(ROOT)} ===")
    print(f"  IMAGE  PROMPT: {image_prompt}")
    print(f"  MOTION PROMPT: {motion_prompt}")
    if dry:
        print("  (dry-run: skipping API calls)")
        return None

    if not os.environ.get("FAL_KEY"):
        sys.exit("FAL_KEY missing. Fill it in .env or env vars.")

    mp4 = run_fal(image_prompt, motion_prompt, slug)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mp4_to_gif(mp4, gif_out)
    print(f"  [ok] wrote {gif_out.relative_to(ROOT)} ({gif_out.stat().st_size // 1024} KB)")
    return gif_out


def main() -> None:
    load_dotenv(ROOT / ".env")

    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--group", type=int, help="Group id (1-10)")
    mode.add_argument("--all", action="store_true", help="All confirmed topics")
    mode.add_argument("--placeholder", action="store_true", help="Reusable placeholder")
    ap.add_argument("--dry-run", action="store_true", help="Print prompts only")
    args = ap.parse_args()

    if args.placeholder:
        render("placeholder", PLACEHOLDER_IMAGE_PROMPT, PLACEHOLDER_MOTION_PROMPT, args.dry_run)
        return

    groups = load_groups()

    if args.group:
        target = next((g for g in groups if g["id"] == args.group), None)
        if not target:
            sys.exit(f"Group {args.group} not found in data.json")
        if not target["topicConfirmed"]:
            sys.exit(f"Group {args.group} topic is '미정'. Nothing to illustrate.")
        prompts = IMAGE_PROMPTS.get(args.group)
        if not prompts:
            sys.exit(
                f"No prompt template for group {args.group}. Add one to "
                f"IMAGE_PROMPTS in this script."
            )
        render(f"group-{args.group}", prompts["image"], prompts["motion"], args.dry_run)
        return

    if args.all:
        confirmed = [g for g in groups if g["topicConfirmed"]]
        if not confirmed:
            sys.exit("No confirmed topics yet. Nothing to generate.")
        for g in confirmed:
            prompts = IMAGE_PROMPTS.get(g["id"])
            if not prompts:
                print(f"(skip) group {g['id']}: no prompt template")
                continue
            render(f"group-{g['id']}", prompts["image"], prompts["motion"], args.dry_run)


if __name__ == "__main__":
    main()
