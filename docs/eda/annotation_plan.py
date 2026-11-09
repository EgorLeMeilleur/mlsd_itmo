"""Calculate the proposed annotation budget and its statistical rationale."""

import json
from math import sqrt
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parent


def main():
    confidence = 0.95
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    splits = {
        "validation": {"concealment": 20, "ordinary": 20},
        "test": {"concealment": 30, "ordinary": 30},
    }
    count = splits["test"]["concealment"]
    # Maximum half-width of a Wilson interval occurs at observed proportion 0.5.
    half_width = z / (2 * sqrt(count + z * z))
    result = {
        "status": "proposed_budget_not_completed_annotations",
        "unit": "one target event or one reviewed ordinary-action interval",
        "splits": splits,
        "total_intervals": sum(sum(values.values()) for values in splits.values()),
        "training_examples": "VLM-assisted and human-reviewed; separate from manual evaluation budget",
        "confidence_level": confidence,
        "test_count_per_class": count,
        "maximum_wilson_half_width": half_width,
        "test_source_group_target": count,
        "assumptions": [
            "The class-conditional observations must be sufficiently independent.",
            "Related windows and source groups must not cross split boundaries.",
            "Validation and test labels are created independently of VLM answers.",
            "This calculation does not justify precision at natural prevalence or false alerts/hour.",
            "Increase the budget or use group-level uncertainty estimates if observations cluster.",
        ],
        "method_reference": "NIST/SEMATECH e-Handbook, 7.2.4.1: Wilson confidence intervals",
    }
    (ROOT / "annotation_plan.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        f"Proposed {result['total_intervals']} intervals; "
        f"test {count} per class; maximum Wilson half-width {100 * half_width:.2f} pp."
    )


if __name__ == "__main__":
    main()
