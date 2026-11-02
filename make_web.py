"""Build Night Survivors for the browser and write docs/ for GitHub Pages.

Run:  python make_web.py
It stages only the files the game needs, runs pygbag, then adds the dark
loading page and docs/.nojekyll.  The built docs/ folder is committed.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
TOOLS = ROOT / "tools"

THEME_CSS = '''
    <style id="night-survivors-theme">
        html, body {
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
            background: #0b0810 !important;
            overscroll-behavior: none;
            -webkit-tap-highlight-color: transparent;
        }
        body {
            font-family: "PingFang HK", "Helvetica Neue", Arial, sans-serif;
        }
        #transfer {
            display: none !important;
        }
        canvas.emscripten {
            background: #0b0810;
            image-rendering: auto;
            max-width: 100vw;
            max-height: 100dvh;
        }
        #infobox {
            box-sizing: border-box;
            position: fixed !important;
            left: 50% !important;
            top: 50% !important;
            right: auto !important;
            bottom: auto !important;
            transform: translate(-50%, -50%);
            width: min(330px, 82vw);
            padding: 24px 28px 20px;
            border: 1px solid rgba(255, 159, 186, .34);
            border-radius: 20px;
            background:
                radial-gradient(120% 130% at 50% 0%, rgba(255, 159, 186, .16), transparent 60%),
                linear-gradient(160deg, #211626, #0e0914);
            color: #f8edf3;
            font-size: 12px;
            font-weight: 500;
            line-height: 1.7;
            letter-spacing: .02em;
            text-align: center;
            box-shadow: 0 26px 80px rgba(0, 0, 0, .65);
        }
        #infobox::before {
            content: "NIGHT SURVIVORS";
            display: block;
            margin-bottom: 10px;
            color: #ffd23f;
            font-size: 20px;
            font-weight: 800;
            letter-spacing: .08em;
        }
        #infobox::after {
            content: "First load can take 30-60 seconds";
            display: block;
            margin-top: 10px;
            color: #9a8491;
            font-size: 10px;
            letter-spacing: .03em;
        }
        #system, #pyconsole, #dlg, #html, #crt {
            display: none !important;
        }
    </style>
'''


def stage_game(stage: Path):
    files = ["main.py", "rules.py"]
    folders = ["data", "assets", "sounds"]
    for name in files:
        shutil.copy2(ROOT / name, stage / name)
    for name in folders:
        shutil.copytree(ROOT / name, stage / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    # Keep the CC0 license next to the art in the archive for attribution.
    (stage / "LICENSES").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "raw_art" / "LICENSE-Kenney-CC0.txt", stage / "LICENSES" / "LICENSE-Kenney-CC0.txt")
    shutil.copy2(ROOT / "assets" / "fonts" / "LICENSE_DEJAVU.txt", stage / "LICENSES" / "LICENSE-DEJAVU.txt")


def build(stage: Path):
    cmd = [
        sys.executable, "-m", "pygbag", "--build",
        "--template", str(TOOLS / "pygbag-default.tmpl"),
        "--icon", str(TOOLS / "pygbag-favicon.png"),
        "--app_name", "night-survivors",
        "--title", "Night Survivors", ".",
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, cwd=stage, check=True)


def patch_page(page: Path):
    text = page.read_text(encoding="utf-8")
    text = text.replace(
        'platform.document.body.style.background = "#7f7f7f"',
        'platform.document.body.style.background = "#0b0810"',
    )
    text = text.replace(
        '<meta name="viewport" content="height=device-height, initial-scale=1.0">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">\n'
        '    <meta name="theme-color" content="#0b0810">\n'
        '    <meta name="color-scheme" content="dark">\n'
        '    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n'
        '    <meta name="description" content="Night Survivors - a 2-minute survivors game built with pygame-ce.">\n'
        '    <meta property="og:title" content="Night Survivors">\n'
        '    <meta property="og:description" content="Survive 2:00. Walk, level up, and let your weapons do the rest.">\n'
        '    <meta property="og:type" content="website">\n'
        '    <meta name="twitter:card" content="summary">\n'
        '    <link rel="apple-touch-icon" href="favicon.png">',
    )
    text = text.replace('msg  = "Ready to start ! Please click/touch page"', 'msg  = "Tap to start"')
    text = text.replace("</head>", THEME_CSS + "</head>")
    page.write_text(text, encoding="utf-8")


def main():
    if not (ROOT / "main.py").is_file():
        raise SystemExit("main.py not found")
    with tempfile.TemporaryDirectory(prefix="night-survivors-") as temp:
        stage = Path(temp) / "night-survivors"
        stage.mkdir()
        stage_game(stage)
        build(stage)
        built = stage / "build" / "web"
        if not (built / "index.html").is_file():
            raise SystemExit("pygbag did not create build/web/index.html")
        if DOCS.exists():
            shutil.rmtree(DOCS)
        shutil.copytree(built, DOCS)
    patch_page(DOCS / "index.html")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    print("Built", DOCS)
    print("Pages URL: https://wgawga041815-create.github.io/night-survivors/")


if __name__ == "__main__":
    main()
