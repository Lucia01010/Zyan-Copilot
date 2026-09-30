"""Build the allowed intent taxonomy from Gold v1 labels."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.intent_taxonomy import IntentTaxonomy


def main() -> None:
    rows = [json.loads(line) for line in Path("data/generated/evaluation/manual_gold_v1.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    taxonomy = IntentTaxonomy.from_rows(rows)
    output = Path("data/generated/evaluation/intent_taxonomy.json")
    output.write_text(json.dumps({"major_to_minors": taxonomy.major_to_minors}, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Intent Taxonomy", "", "Gold v1-derived allowed labels. Model outputs must normalize to one of these exact major/minor pairs.", "", "## Allowed labels", ""]
    for major, minors in taxonomy.major_to_minors.items():
        lines.append(f"- `{major}`")
        for minor in minors:
            lines.append(f"  - `{minor}`")
    lines += ["", "## Normalization rules", "", "- Trim leading/trailing whitespace and collapse internal whitespace.", "- Exact major/minor pairs are accepted; invalid combinations are rejected.", "- Alias matching may use exact normalized text or an unambiguous substring match.", "- Unknown labels are not silently converted to a different intent; they remain unmapped.", "- This taxonomy is derived from human Gold v1, not from model-generated labels."]
    Path("docs/INTENT_TAXONOMY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"majors": len(taxonomy.major_to_minors), "pairs": sum(len(v) for v in taxonomy.major_to_minors.values())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
