import re
raw = open("paper/main.tex", encoding="utf-8").read()
c = re.sub(r"\s+", " ", raw)

checks = {
    "Upgrade 1 (validity table)":    "tab:validity" in raw and "Threats to Validity" in raw,
    "Upgrade 2 (abstract closing)":  "necessary architectural component" in c,
    "Upgrade 3 (shadow deployment)": "shadow mode" in c and "30 days" in c,
    "sec:exp1 label":                "label{sec:exp1}" in raw,
    "sec:conclusion label":          "label{sec:conclusion}" in raw,
    "Leaked note gone":              "verify these values against actual per-case" not in raw,
    "GitHub URL present":            "github.com/[username]" in raw,
}
for name, ok in checks.items():
    print(f"  {'OK' if ok else 'FAIL'} {name}")

import os
print(f"\nLines: {len(raw.splitlines())}")
print(f"ZIP:   {os.path.getsize('paper/overleaf_package.zip'):,} bytes")
print(f"Cover letter: {os.path.exists('paper/cover_letter.md')}")
