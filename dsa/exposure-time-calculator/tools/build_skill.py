"""Package the Claude skill: skill/dsa-sensitivity + the dsa_etc package + docs/model.md -> dist/dsa-sensitivity-skill.zip

The zip holds one top-level folder, dsa-sensitivity/, with SKILL.md at its root.
"""
import os
import shutil
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "skill", "dsa-sensitivity")
OUT_DIR = os.path.join(ROOT, "dist", "skill", "dsa-sensitivity")
ZIP = os.path.join(ROOT, "dist", "dsa-sensitivity-skill.zip")


def main():
    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    shutil.copytree(SRC, OUT_DIR, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(os.path.join(ROOT, "python", "dsa_etc"), os.path.join(OUT_DIR, "scripts", "dsa_etc"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    os.makedirs(os.path.join(OUT_DIR, "reference"), exist_ok=True)
    shutil.copy(os.path.join(ROOT, "docs", "model.md"), os.path.join(OUT_DIR, "reference", "model.md"))
    if os.path.exists(ZIP):
        os.remove(ZIP)
    base = os.path.dirname(OUT_DIR)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for d, _, files in os.walk(OUT_DIR):
            for f in sorted(files):
                p = os.path.join(d, f)
                z.write(p, os.path.relpath(p, base))
    print("wrote", os.path.relpath(ZIP, ROOT), "(%.0f kB)" % (os.path.getsize(ZIP) / 1e3))


if __name__ == "__main__":
    main()
