"""Rebuild contact sheets from local, privacy-masked source frames."""

import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
from PIL import Image

ROOT = Path(__file__).resolve().parent
SOURCES = {
    "mnnit-v1": ("MNNIT", "visual_mnnit.png"),
    "zenodo-10149996": ("Zenodo", "visual_zenodo.png"),
    "ucf-crime-shoplifting": ("UCF-Crime", "visual_ucf.png"),
    "retailaction": ("RetailAction: два ракурса одного эпизода", "visual_retailaction.png"),
}


def main():
    plt.switch_backend("Agg")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    manifest = json.loads((ROOT / "visual_samples.json").read_text())
    (ROOT / "figures").mkdir(exist_ok=True)
    for dataset, (title, filename) in SOURCES.items():
        cases = [case for case in manifest["cases"] if case["dataset"] == dataset]
        fig, axes = plt.subplots(len(cases), 4, figsize=(16, 9), squeeze=False)
        for row, case in zip(axes, cases, strict=True):
            for ax, frame in zip(row, case["frames"], strict=True):
                path = ROOT / frame["file"]
                if hashlib.sha256(path.read_bytes()).hexdigest() != frame["sha256"]:
                    raise ValueError(f"Source frame checksum mismatch: {path.name}")
                with Image.open(path) as image:
                    ax.imshow(image)
                ax.set_title(
                    f"{case['case_id']} · {case['source_class']} · кадр {frame['frame_index']}",
                    fontsize=9,
                )
                ax.axis("off")
        fig.suptitle(title)
        fig.text(
            0.5,
            0.015,
            "Серые прямоугольники скрывают лица; это не естественные перекрытия. "
            "Класс указан по источнику.",
            ha="center",
            fontsize=9,
        )
        fig.subplots_adjust(left=0.01, right=0.99, top=0.89, bottom=0.08, wspace=0.06, hspace=0.28)
        fig.savefig(ROOT / "figures" / filename, dpi=140, facecolor="white")
        plt.close(fig)
    print("Rebuilt 4 visual contact sheets from 32 local frames.")


if __name__ == "__main__":
    main()
