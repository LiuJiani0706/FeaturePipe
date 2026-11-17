"""Review already generated files offline, without extra API calls."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from featurepipe.evidence import quote_audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    case = json.loads(Path(args.input).read_text(encoding="utf-8"))
    run = Path(args.run)
    files = list(run.glob("00-baseline.md")) + sorted(run.glob("05-draft-*.md")) + sorted(run.glob("r*-polished.md")) + list(run.glob("article.md"))
    results = {file.name: quote_audit(file.read_text(encoding="utf-8"), case["materials"]) for file in files}
    (run/"literal-evidence.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({name: {k: result[k] for k in ("chinese_chars", "marked_quotes", "unmatched_quotes")} for name, result in results.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
