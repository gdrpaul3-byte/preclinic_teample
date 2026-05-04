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
    1: {
        "image": (
            "Clean two-panel scientific illustration on a 16:9 canvas, "
            "educational diagram aesthetic, blue-teal palette with green and "
            "red accents and a warm gold molecular highlight. Top horizontal "
            "label across both panels: 'TROGLITAZONE — IDIOSYNCRATIC "
            "HEPATOTOXICITY' with a small simplified 2D thiazolidinedione "
            "molecular structure drawn in gold beside it. Left panel labeled "
            "'ANIMAL STUDIES (RAT/MOUSE)': a small rodent silhouette "
            "receiving the gold troglitazone molecule; below it a healthy "
            "pink liver organ shape with a green checkmark badge and a "
            "subtle label 'NORMAL LIVER FUNCTION'. Right panel labeled "
            "'HUMAN PATIENTS (1997 → 2000)': a human silhouette receiving the "
            "same gold troglitazone molecule; below it a damaged liver in "
            "mottled dark red and brown with cracked-cell texture, small "
            "hepatocyte death icons floating off, and a red warning triangle "
            "labeled 'ACUTE HEPATIC FAILURE'; a small footnote pill near the "
            "bottom reads 'WITHDRAWN 2000'. A vertical hairline divides the "
            "panels. Minimalist, high contrast, clean uppercase English "
            "labels, no extra text."
        ),
        "motion": (
            "Slow camera reveal panning from the left animal panel to the "
            "right human panel. On the left, the gold troglitazone molecule "
            "glides into the rodent, the healthy pink liver pulses softly "
            "with a green checkmark. On the right, the same gold molecule "
            "arrives at the human silhouette, the liver darkens as cracked "
            "red-brown cell textures spread outward, hepatocyte death icons "
            "drift away, and the red warning triangle pulses. The molecular "
            "structure at the top emits a faint warm glow. Loop-friendly, 4 "
            "seconds, no text changes."
        ),
    },
    2: {
        "image": (
            "Clean scientific two-panel illustration, 16:9 educational diagram, "
            "blue-teal palette with red, green, and gold accents. Top label "
            "across both panels: 'IMMUNO-ONCOLOGY MODELS'. Left panel labeled "
            "'PRECLINICAL: MOUSE XENOGRAFT': a small immunodeficient lab mouse "
            "silhouette tagged 'nude/SCID' with a purple human tumor mass "
            "growing on its flank; ghosted, semi-transparent T-cell silhouettes "
            "around the mouse with red strikethrough marks; a small red "
            "callout reads 'NO ADAPTIVE IMMUNITY'; a Y-shaped antibody labeled "
            "'anti-PD-1' floats nearby with a small question mark icon above "
            "it. Right panel labeled 'HUMAN PATIENT': a stylized human "
            "silhouette holding a tumor inside, surrounded by a busy tumor "
            "microenvironment — green CD8 T cells, orange regulatory T cells, "
            "tumor cells with red PD-L1 receptors on their surface; the "
            "anti-PD-1 antibody binds a PD-L1 receptor with a brief golden "
            "highlight; small curved arrows labeled 'IMMUNE EVASION' wrap the "
            "tumor. Between the two panels a vertical hairline divider with a "
            "horizontal arrow labeled 'TRANSLATIONAL GAP'. Minimalist, high "
            "contrast, clean uppercase English labels, no extra text."
        ),
        "motion": (
            "Slow camera pan from the left mouse panel to the right human "
            "panel. On the left, the purple human tumor on the mouse pulses "
            "softly, the ghost T-cells flicker once and fade, the question "
            "mark above the anti-PD-1 antibody bobs gently. The 'TRANSLATIONAL "
            "GAP' arrow draws across the middle from left to right. On the "
            "right, the anti-PD-1 antibody glides into the human tumor "
            "microenvironment and binds a PD-L1 receptor with a brief golden "
            "flash; the green CD8 T cells activate and pulse outward; the "
            "'IMMUNE EVASION' arrows briefly retract. Loop-friendly, 4 "
            "seconds, no text changes."
        ),
    },
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
    4: {
        "image": (
            "Clean scientific dose-response diagram, 16:9 educational "
            "illustration, blue-teal palette with green and red accents. "
            "X-axis labeled 'DOSE', Y-axis labeled 'RESPONSE'. Two overlapping "
            "bell-shaped curves: a green curve labeled 'EFFICACY' rising "
            "smoothly to a peak; a red curve labeled 'TOXICITY' rising sharply "
            "right behind it and overlapping the upper portion of the efficacy "
            "curve. The narrow strip between the two curves is highlighted in "
            "warm gold and labeled 'THERAPEUTIC WINDOW'. A small circular dose "
            "marker (a glowing dot) sits inside this narrow gold strip, "
            "visibly squeezed between the two rising curves. Minimalist, high "
            "contrast, clean uppercase English labels, no extra text."
        ),
        "motion": (
            "Slow camera push-in toward the therapeutic window. The green "
            "EFFICACY curve draws upward from left to right. The red TOXICITY "
            "curve draws upward right behind it, overlapping. The 'THERAPEUTIC "
            "WINDOW' band glows gold. The circular dose marker oscillates "
            "gently left and right inside the narrow gold strip, struggling to "
            "find a stable position. Loop-friendly, 4 seconds, no text changes."
        ),
    },
    6: {
        "image": (
            "Clean side-by-side comparison illustration on a 16:9 canvas, "
            "educational diagram aesthetic, blue-teal palette with green and "
            "warm gold accents. Title at top: 'PRECLINICAL EVALUATION — "
            "SMALL MOLECULE vs MONOCLONAL ANTIBODY'. Left panel labeled "
            "'SMALL MOLECULE': a simple 2D ball-and-stick chemical structure, "
            "an oral pill icon, and a single lab mouse silhouette with a "
            "green checkmark. Below it three small metric pills: 'MW ~500 Da', "
            "'ORAL', 'CROSS-SPECIES OK'. Right panel labeled 'MONOCLONAL "
            "ANTIBODY (mAb)': a prominent Y-shaped antibody molecule rendered "
            "in soft gold, an IV infusion bag with a drip drop, plus two "
            "species silhouettes side by side — a humanized mouse and a "
            "cynomolgus monkey — with subtle caution markers indicating "
            "species-specific binding considerations. Below it three small "
            "metric pills: 'MW ~150 kDa', 'IV / SC', 'SPECIES-SPECIFIC'. A "
            "vertical hairline divides the panels with a tiny label "
            "'KEY DIFFERENCES' at the top of the divider. Minimalist, high "
            "contrast, clean uppercase English labels, no extra text."
        ),
        "motion": (
            "Slow camera reveal panning from the left small-molecule panel "
            "to the right monoclonal antibody panel. On the left, the small "
            "ball-and-stick chemical structure rotates gently, the oral pill "
            "drops down toward the mouse with a green checkmark pulse. On "
            "the right, the gold Y-shaped antibody floats and rotates slowly, "
            "the IV bag releases a single drop, and the humanized mouse and "
            "cynomolgus monkey silhouettes briefly highlight to indicate "
            "species-specific binding. The metric pills appear sequentially "
            "underneath each panel. Loop-friendly, 4 seconds, no text changes."
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
    7: {
        "image": (
            "Clean scientific two-panel diagram, 16:9 educational illustration, "
            "blue-teal palette with a strong red accent reflecting "
            "doxorubicin's signature deep red color. Top horizontal label "
            "across both panels: 'DOXORUBICIN' with a simplified molecular "
            "structure icon. Left panel labeled 'TUMOR': several malignant "
            "cancer cells in muted purple, with DNA double-helix strands "
            "inside them being intercalated and broken by red doxorubicin "
            "molecules; a small green checkmark badge indicates successful "
            "tumor cell death. Right panel labeled 'HEART': a stylized "
            "cardiac muscle cell (sarcomere fibers visible) receiving the "
            "same red doxorubicin molecules; orange-yellow oxidative stress "
            "burst icons radiate outward, sarcomere fibers appear damaged or "
            "frayed; a red warning triangle indicates cardiotoxicity. A "
            "vertical hairline divides the two panels. Minimalist, high "
            "contrast, clean uppercase English labels, no extra text."
        ),
        "motion": (
            "Slow camera reveal panning from the left tumor panel to the "
            "right heart panel. On the left, red doxorubicin molecules glide "
            "into cancer cells, DNA strands fracture with a brief flash, "
            "cells dim while a green checkmark pulses softly. On the right, "
            "doxorubicin molecules arrive at the cardiac muscle cell, "
            "orange-yellow oxidative stress bursts radiate outward in pulses, "
            "the sarcomere fibers waver, and the red warning triangle pulses. "
            "The 'DOXORUBICIN' label across the top emits a faint red glow. "
            "Loop-friendly, 4 seconds, no text changes."
        ),
    },
    9: {
        "image": (
            "Clean scientific illustration, 16:9 educational diagram, blue-"
            "teal palette with red and gold accents. Top header in uppercase: "
            "'PRECLINICAL SAFETY EVALUATION'. Center: a stylized AAV "
            "(adeno-associated virus) capsid as a 20-sided icosahedral shape "
            "with a small glowing DNA double helix payload visible inside, "
            "labeled 'AAV + GENE PAYLOAD'. Four arrows radiate from the AAV "
            "outward to four small evaluation panels arranged around it. "
            "Top-left panel labeled 'BIODISTRIBUTION': a stylized body "
            "silhouette with liver, heart, and brain organ icons highlighted "
            "with small dots. Top-right panel labeled 'IMMUNOGENICITY': "
            "Y-shaped antibodies surrounding and neutralizing an AAV particle, "
            "with a small red exclamation mark. Bottom-left panel labeled "
            "'INTEGRATION': a chromosome with the AAV payload inserting into "
            "it, golden highlight at the insertion site. Bottom-right panel "
            "labeled 'TOXICITY': a liver icon with a small red warning "
            "triangle and a falling biomarker line. Minimalist, high contrast, "
            "clean uppercase English labels, no extra text."
        ),
        "motion": (
            "Subtle camera push-in toward the central AAV capsid. The DNA "
            "helix inside the AAV pulses gently with a golden glow. The four "
            "arrows draw outward to their evaluation panels in clockwise "
            "sequence: the body organs in the biodistribution panel light up "
            "briefly, the antibodies in the immunogenicity panel close around "
            "the AAV with a red flash, the chromosome in the integration "
            "panel receives the payload with a golden highlight, the liver "
            "icon in the toxicity panel emits a faint red warning pulse. "
            "Loop-friendly, 4 seconds, no text changes."
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

IMAGE_PROMPTS[10] = {
    "image": (
        "Clean scientific case-study poster, 16:9 educational diagram aesthetic, "
        "blue-teal palette with red and warm gold accents. Title at top: "
        "'HEPATOTOXICITY — TERMINATED DRUG CANDIDATES'. Center: a large "
        "stylized human liver organ in soft red with subtle cracked-cell "
        "texture and a small gold magnifying glass icon overlaid as if "
        "examining a sample. Around the liver in four corners: four labeled "
        "drug card tiles, each containing a small pill or capsule icon and a "
        "drug name in clean uppercase — top-left 'TROGLITAZONE  1997→2000', "
        "top-right 'FIALURIDINE  1993', bottom-left 'XIMELAGATRAN  2006', "
        "bottom-right 'LUMIRACOXIB  2007'. Each card has a red 'TERMINATED' "
        "stamp angled across it and a small red X badge in its corner. Thin "
        "lines connect each card toward the central liver. A footer pill "
        "near the bottom reads 'PRECLINICAL  →  CLINICAL  →  WITHDRAWN'. "
        "Minimalist, high contrast, clean uppercase English labels, no extra "
        "text."
    ),
    "motion": (
        "Slow camera push-in toward the central damaged liver. The liver "
        "pulses softly in red with cracked-texture detail. The four corner "
        "drug cards appear in sequence (top-left, top-right, bottom-left, "
        "bottom-right), each receiving its red 'TERMINATED' stamp with a "
        "brief red flash and a small X badge appearing. Thin connecting "
        "lines draw from each card into the liver one by one. The gold "
        "magnifying glass slowly slides across the liver surface. Loop-"
        "friendly, 4 seconds, no text changes."
    ),
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
