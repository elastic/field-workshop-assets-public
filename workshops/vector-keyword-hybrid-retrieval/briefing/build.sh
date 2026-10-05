#!/bin/bash
# Build the Briefing deck: merge speaker notes, export one self-contained index.html.
#   src/slides/*.html   slide sources (one standalone 1280x720 page each)
#   src/notes/*.md      speaker notes, one per slide (same base filename)
#   index.html          build output, served in the Instruqt "Briefing" tab (port 5000)
# Present live with notes:  cd src && fslides serve   (N notes, G overview, L laser, F fullscreen, H all keys)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/src"

# notes/*.md -> notes.json (fslides serve reads this)
python3 - <<'EOF'
import json, pathlib
notes = {p.with_suffix(".html").name: p.read_text().strip() for p in sorted(pathlib.Path("notes").glob("*.md"))}
pathlib.Path("notes.json").write_text(json.dumps(notes, indent=2) + "\n")
print(f"notes.json: {len(notes)} slides")
EOF

fslides export ../index.html

# fslides export ships without notes; bake them in so N works in the Briefing tab too.
python3 - "$HERE/index.html" <<'EOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()
notes = pathlib.Path("notes.json").read_text()
marker = "let allNotes  = {};"
assert marker in s, "fslides player changed: notes marker not found"
s = s.replace(marker, "let allNotes  = " + json.dumps(json.loads(notes)) + ";", 1)
p.write_text(s)
print(f"{p}: {len(s)//1024} KB, notes baked in")
EOF
