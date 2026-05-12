"""
Interaction engine eval: recall, severity accuracy, specificity.

Run from backend/:  python -m eval.runners.eval_interactions
Targets: recall ≥ 90%, specificity ≥ 90%
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def main() -> None:
    from db.client import get_pool, close_pool
    from rag.ingest import init_chroma
    from models.medication import Medication
    from tools.interaction_checker import check_interaction_pair

    init_chroma()
    await get_pool()

    test_set_path = Path(__file__).parent.parent / "test_sets" / "interaction_pairs.json"
    cases = json.loads(test_set_path.read_text())

    known_interaction = [c for c in cases if c["expected_has_interaction"]]
    known_non_interaction = [c for c in cases if not c["expected_has_interaction"]]

    print(f"\nRunning eval on {len(cases)} pairs "
          f"({len(known_interaction)} interactions, {len(known_non_interaction)} non-interactions)\n")

    results = []
    for case in cases:
        med_a = Medication(
            rxcui=case["rxcui_a"], name=case["name_a"],
            input_text=case["name_a"], type="prescription", confidence=1.0,
        )
        med_b = Medication(
            rxcui=case["rxcui_b"], name=case["name_b"],
            input_text=case["name_b"], type="prescription", confidence=1.0,
        )
        interaction = await check_interaction_pair(med_a, med_b)
        predicted_has = interaction.severity != "unknown"
        severity_correct = interaction.severity == case["expected_severity"]

        results.append({
            "pair": f"{case['name_a']} + {case['name_b']}",
            "expected_severity": case["expected_severity"],
            "predicted_severity": interaction.severity,
            "expected_has": case["expected_has_interaction"],
            "predicted_has": predicted_has,
            "severity_correct": severity_correct,
            "confidence": interaction.confidence,
        })
        status = "✓" if severity_correct else "✗"
        print(f"  {status} {case['name_a']:20} + {case['name_b']:20} "
              f"expected={case['expected_severity']:8} got={interaction.severity:8} "
              f"conf={interaction.confidence}")

    # Metrics
    true_positives  = sum(1 for r in results if r["expected_has"] and r["predicted_has"])
    false_negatives = sum(1 for r in results if r["expected_has"] and not r["predicted_has"])
    true_negatives  = sum(1 for r in results if not r["expected_has"] and not r["predicted_has"])
    false_positives = sum(1 for r in results if not r["expected_has"] and r["predicted_has"])
    severity_correct = sum(1 for r in results if r["severity_correct"])

    recall      = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) else 0
    specificity = true_negatives / (true_negatives + false_positives) if (true_negatives + false_positives) else 0
    sev_acc     = severity_correct / len(results) if results else 0

    print(f"\n{'─'*60}")
    print(f"  Recall (interaction detection):  {recall:.0%}  (target ≥ 90%)")
    print(f"  Specificity (non-interaction):   {specificity:.0%}  (target ≥ 90%)")
    print(f"  Severity accuracy:               {sev_acc:.0%}")
    print(f"{'─'*60}\n")

    passed = recall >= 0.90 and specificity >= 0.90
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
