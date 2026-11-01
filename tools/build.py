#!/usr/bin/env python3
"""Build everything that ships: demo state, the live demo page, screenshots' source, and the skill zip.

    python3 tools/build.py

Outputs:
  plugin/skills/wealth-dashboard/assets/demo-state.json   (invented household)
  docs/index.html                                          (live demo, served by GitHub Pages)
  dist/wealth-dashboard.zip                                (upload this in Claude: Customize > Skills)
"""
import os
import re
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugin", "skills", "wealth-dashboard")
PY = sys.executable


def run(*args):
    subprocess.run([PY, *args], check=True, cwd=ROOT)


def check_skill_md():
    text = open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "SKILL.md needs YAML frontmatter"
    front = m.group(1)
    name = re.search(r"^name:\s*(\S+)", front, re.M).group(1)
    desc = re.search(r"^description:\s*(.+)$", front, re.M).group(1)
    assert re.match(r"^[a-z0-9-]{1,64}$", name), "bad skill name"
    assert len(desc) <= 1024 and "<" not in desc and ">" not in desc, "description too long or has angle brackets"
    lines = text.count("\n")
    assert lines < 500, "SKILL.md should stay under 500 lines (%d)" % lines
    print("SKILL.md ok: %s, description %d chars, %d lines" % (name, len(desc), lines))


def zip_skill():
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    out = os.path.join(ROOT, "dist", "wealth-dashboard.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, dirs, files in os.walk(SKILL):
            dirs[:] = sorted(d for d in dirs if d not in ("__pycache__", "node_modules", "evals"))
            for f in sorted(files):
                if f.endswith(".pyc") or f == ".DS_Store":
                    continue
                full = os.path.join(folder, f)
                arc = os.path.join("wealth-dashboard", os.path.relpath(full, SKILL))
                info = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o755 if f.endswith(".py") else 0o644) << 16
                with open(full, "rb") as fh:
                    z.writestr(info, fh.read())
    print("Wrote %s (%d KB)" % (os.path.relpath(out, ROOT), os.path.getsize(out) // 1024))


if __name__ == "__main__":
    check_skill_md()
    run("tools/make_demo.py")
    wealth = os.path.join(SKILL, "scripts", "wealth.py")
    state = os.path.join(SKILL, "assets", "demo-state.json")
    run(wealth, "validate", state)
    run(wealth, "standalone", state, "docs/index.html")
    zip_skill()
