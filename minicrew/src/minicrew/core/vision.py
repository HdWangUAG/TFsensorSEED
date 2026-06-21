"""Read figure/table DATA off paper pages with a multimodal model.

pdftotext can't recover numbers that live in plotted figures (bar heights, curve
points) or in image-based tables. This renders the relevant pages to PNG
(pdftoppm) and asks a vision model to transcribe tables and read off plot values
— every plot-read number flagged APPROXIMATE for human confirmation.

Vision needs an API model (openai / gemini / anthropic); claude_cli can't see
images. Use sparingly — vision calls over full pages are the priciest path.
"""
from __future__ import annotations

import glob
import os
import subprocess
import tempfile

from . import config, llm

VISION_SYS = """\
You read scientific paper PAGE IMAGES and extract their DATA for a protein-
engineering project. Rules:
- Transcribe TABLES exactly as Markdown (every row/column), citing the label,
  e.g. 〔src: Table 2〕.
- For PLOTS (bar/line/scatter), read the values you can see, but mark EACH as
  approximate: 〔fig: Fig N — read off plot, APPROXIMATE, confirm〕.
- Report ONLY what is visibly present. If a value is unclear, say "unclear".
- Output Markdown under a single heading
  '## Figure / table data (vision-extracted — verify)' and nothing else."""

MAX_PAGES = 8


def _page_range(pages):
    """'3' -> (3,3); '2-4' -> (2,4); None -> (None,None)."""
    if not pages:
        return None, None
    s = str(pages).strip()
    if "-" in s:
        a, b = s.split("-", 1)
        return int(a), int(b)
    return int(s), int(s)


def render_pages(pdf_path, pages=None, dpi=150, max_pages=MAX_PAGES):
    """Render PDF pages to PNGs; returns a list of file paths (in a temp dir)."""
    outdir = tempfile.mkdtemp(prefix="mcfig_")
    cmd = ["pdftoppm", "-png", "-r", str(dpi)]
    first, last = _page_range(pages)
    if first:
        cmd += ["-f", str(first), "-l", str(last)]
    cmd += [pdf_path, os.path.join(outdir, "p")]
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    return sorted(glob.glob(os.path.join(outdir, "p*.png")))[:max_pages]


def extract(pdf_path, pages=None, model="openai"):
    """Vision-extract figure/table data from the given PDF pages → Markdown."""
    pngs = render_pages(pdf_path, pages)
    if not pngs:
        return ""
    spec = config.resolve_model(model)
    prompt = ("Extract all figure and table data from these page image(s). "
              "Transcribe tables; read plot values as approximate.")
    return llm.call_vision(spec, VISION_SYS, prompt, pngs)
