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
        "training_examples": {"concealment": 25, "ordinary": 25},
        "validation": {"concealment": 25, "ordinary": 25},
        "test": {"concealment": 50, "ordinary": 50},
    }
    count = splits["test"]["concealment"]
    # Maximum half-width of a Wilson interval occurs at observed proportion 0.5.
    half_width = z / (2 * sqrt(count + z * z))
    result = {
        "status": "proposed_budget_not_completed_annotations",
        "unit": "one target event or one reviewed ordinary-action interval",
        "splits": splits,
        "total_intervals": sum(sum(values.values()) for values in splits.values()),
        "pilot_intervals_in_training": 20,
        "pilot_class_counts": {"concealment": 10, "ordinary": 10},
        "confidence_level": confidence,
        "test_count_per_class": count,
        "maximum_wilson_half_width": half_width,
        "test_source_group_target": count,
        "assumptions": [
            "The class-conditional observations must be sufficiently independent.",
            "Related windows and source groups must not cross split boundaries.",
            "The pilot is part of the total budget, not an additional sample.",
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
