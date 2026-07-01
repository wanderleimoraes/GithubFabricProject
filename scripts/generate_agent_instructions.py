"""Generate docs/fabric-data-agent-instructions.md from nl_query/ontology.py.

The project has ONE semantic layer, defined in ``nl_query/ontology.py``. This script
renders the Fabric Data Agent instruction document from it, so the Streamlit engine
and the Fabric agent can never drift apart — edit the ontology, re-run this, commit.

Run:   ``python -m scripts.generate_agent_instructions``
Check: ``python -m scripts.generate_agent_instructions --check``  (CI: fails if stale)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nl_query.ontology import ENTITIES, METRIC_GLOSSARY, RELATIONSHIPS

OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "fabric-data-agent-instructions.md"

# DAX measures defined on the semantic model (dashboards/sp500_Analytics.SemanticModel).
MEASURES = (
    "Company Count, Latest Close, Net Margin %, RnD Intensity %, Total AI Committed,\n"
    "  Material Fact Count, Quantified AI $"
)

ANSWERING_RULES = """\
ANSWERING:
- Group by gics_sector directly on facts that carry it (prices, fundamentals,
  material_facts); for commitments, join dim_tickers for sector.
- When citing AI commitments or material facts, include the source_url so the user can
  verify against the filing.
- Use only the data in the model. If something is not in the data, say so. Do not add
  external facts, figures, or company details that are not in the result."""

EXAMPLE_QUESTIONS = """\
- Top 15 companies by total R&D spend over the last 5 years.
- Total AI committed by sector.
- Which are the 10 largest companies by market cap?
- Apple's year-over-year revenue growth.
- Companies with the highest net margin in the latest fiscal year.
- Highest-confidence AI commitments over $1 billion, with sources.
- Most significant AI partnership facts in the last 5 years, with source links.
- Which companies outperformed their sector on the latest trading day?
- Do companies with higher R&D intensity make larger AI commitments?"""

TEMPLATE = """\
# Fabric Data Agent — instructions (generated — do not edit by hand)

> **Generated from [`nl_query/ontology.py`](../nl_query/ontology.py)** by
> `python -m scripts.generate_agent_instructions`. That file is the single source of
> truth for the project's semantic layer; this document is its Fabric rendering, so the
> Streamlit engine and the Fabric Data Agent always share one vocabulary.

This is the instruction text for the **`sp500_agent`** Fabric Data Agent built on the
`sp500_directlake` semantic model.

## How to use
1. Fabric → `sp500-analytics` → open **`sp500_agent`**.
2. Paste the **Agent instructions** block below into the agent's instructions box.
3. Optionally pin the example questions at the bottom.
4. Save and test in the playground.

---

## Agent instructions (paste this whole block)

```
You answer questions about S&P 500 companies in the AI era, over a star-schema
semantic model. Be accurate, cite the data, and never invent figures.

{entities}

{relationships}

MEASURES (prefer these over re-deriving):
- {measures}

{glossary}

{answering}
```

---

## Example questions to pin (optional)

{examples}
"""


def render() -> str:
    return TEMPLATE.format(
        entities=ENTITIES,
        relationships=RELATIONSHIPS,
        measures=MEASURES,
        glossary=METRIC_GLOSSARY,
        answering=ANSWERING_RULES,
        examples=EXAMPLE_QUESTIONS,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the Fabric agent instructions.")
    parser.add_argument(
        "--check", action="store_true",
        help="Exit 1 if the committed document is stale (CI guard).",
    )
    args = parser.parse_args()

    content = render()
    if args.check:
        current = OUTPUT.read_text() if OUTPUT.exists() else ""
        if current != content:
            print(
                "docs/fabric-data-agent-instructions.md is stale. "
                "Run `python -m scripts.generate_agent_instructions` and commit."
            )
            sys.exit(1)
        print("fabric-data-agent-instructions.md is up to date.")
        return

    OUTPUT.write_text(content)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
