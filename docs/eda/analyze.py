"""Rebuild the EDA summary and figures from the local metadata snapshot."""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
NAMES = {
    "mnnit-v1": "MNNIT",
    "zenodo-10149996": "Zenodo",
    "ucf-crime-shoplifting": "UCF-Crime",
    "retailaction": "RetailAction",
}
COLORS = ["#3775a9", "#36957b", "#d68a34", "#8765a3"]


def load_metadata():
    path = ROOT / "video_metadata.csv"
    provenance = json.loads((ROOT / "sources.json").read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest() != provenance["snapshot_sha256"]:
        raise ValueError("The metadata snapshot does not match sources.json")
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for field in ("size_bytes", "width", "height", "frame_count"):
            row[field] = int(row[field])
        for field in ("container_fps", "container_duration_s", "source_span_s"):
            row[field] = float(row[field]) if row[field] else None
        for field in ("included", "target_annotation_available"):
            row[field] = row[field] == "1"
        if not row["included"] and not row["exclusion_reason"]:
            raise ValueError("An excluded record needs a reason")
    if len({row["record_id"] for row in rows}) != len(rows):
        raise ValueError("Record identifiers must be unique")
    return rows


def summarize(rows):
    result = {
        "records": len(rows),
        "included": sum(row["included"] for row in rows),
        "decode_status": dict(Counter(row["decode_status"] for row in rows)),
        "exclusions": dict(Counter(row["exclusion_reason"] for row in rows if not row["included"])),
        "records_with_target_annotations": sum(row["target_annotation_available"] for row in rows),
        "datasets": {},
    }
    for dataset in NAMES:
        source = [row for row in rows if row["dataset"] == dataset]
        included = [row for row in source if row["included"]]
        spans = [row["source_span_s"] for row in included if row["source_span_s"] is not None]
        dimensions = Counter(f"{row['width']}×{row['height']}" for row in included)
        result["datasets"][dataset] = {
            "records": len(source),
            "included": len(included),
            "source_groups": len({row["group_id"] for row in source}),
            "size_gib": sum(row["size_bytes"] for row in source) / 1024**3,
            "source_classes": dict(sorted(Counter(row["source_class"] for row in source).items())),
            "container_fps_values": sorted({row["container_fps"] for row in source}),
            "median_frames_included": median(row["frame_count"] for row in included),
            "median_container_duration_s_included": median(
                row["container_duration_s"] for row in included
            ),
            "median_source_span_s_included": median(spans) if spans else None,
            "most_common_resolution_included": dimensions.most_common(1)[0][0],
            "source_time_status": dict(Counter(row["source_time_status"] for row in source)),
            "official_splits": dict(
                Counter(row["official_split"] or "unspecified" for row in source)
            ),
        }
    return result


def save_figure(fig, name):
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / name, dpi=160, facecolor="white")
    plt.close(fig)


def composition(summary):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    counts = [summary["datasets"][dataset]["records"] for dataset in NAMES]
    bars = axes[0].barh(list(NAMES.values()), counts, color=COLORS)
    axes[0].bar_label(bars, padding=4)
    axes[0].set_xlim(0, max(counts) * 1.15)
    axes[0].set_title("Состав полученного корпуса")
    axes[0].set_xlabel("Видеофайлы, включая повторные записи")
    quality = {
        "Допущены": summary["included"],
        "Нет авторского времени": summary["exclusions"]["source_timestamps_missing"],
        "Метки не совпали с кадрами": summary["exclusions"]["source_timestamps_mismatch"],
        "Точные дубли": summary["exclusions"]["exact_duplicate"],
    }
    bars = axes[1].barh(list(quality), list(quality.values()), color=COLORS)
    axes[1].bar_label(bars, padding=4)
    axes[1].set_xscale("log")
    axes[1].set_xlim(0.7, summary["records"] * 3)
    axes[1].set_title("Технический отбор")
    axes[1].set_xlabel("Видеофайлы, логарифмическая шкала")
    save_figure(fig, "composition_quality.png")


def source_classes(summary):
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for ax, (dataset, name), color in zip(axes.flat, NAMES.items(), COLORS, strict=True):
        counts = summary["datasets"][dataset]["source_classes"]
        bars = ax.barh(list(counts), list(counts.values()), color=color)
        ax.bar_label(bars, padding=3)
        ax.set_xlim(0, max(counts.values()) * 1.2)
        ax.set_title(name)
        ax.set_xlabel("Видеофайлы с авторской меткой")
    save_figure(fig, "source_classes.png")


def duration_and_frames(rows):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    durations, frames = [], []
    for dataset in NAMES:
        source = [row for row in rows if row["dataset"] == dataset and row["included"]]
        durations.append(
            [
                row["source_span_s"] if dataset == "retailaction" else row["container_duration_s"]
                for row in source
            ]
        )
        frames.append([row["frame_count"] for row in source])
    labels = ["MNNIT", "Zenodo", "UCF-Crime", "RetailAction*"]
    style = {"markersize": 2, "alpha": 0.3}
    axes[0].boxplot(durations, tick_labels=labels, flierprops=style)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Секунды, логарифмическая шкала")
    axes[0].set_title("Длительность / *интервал авторских меток")
    axes[1].boxplot(frames, tick_labels=labels, flierprops=style)
    axes[1].set_yscale("log")
    axes[1].set_ylabel("Декодированные кадры, логарифмическая шкала")
    axes[1].set_title("Число сохранённых кадров")
    fig.suptitle("Допущенные записи; интервал RetailAction не равен непрерывному видео")
    save_figure(fig, "duration_frames.png")


def resolution_and_fps(rows):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    included = [row for row in rows if row["included"]]
    sizes = Counter(f"{row['width']}×{row['height']}" for row in included).most_common(8)
    bars = axes[0].barh([key for key, _ in sizes], [count for _, count in sizes], color=COLORS[0])
    axes[0].bar_label(bars, padding=3)
    axes[0].set_xlim(0, sizes[0][1] * 1.2)
    axes[0].set_xlabel("Видеофайлы")
    axes[0].set_title("Наиболее частые разрешения")
    for dataset, color in zip(NAMES, COLORS, strict=True):
        fps = sorted({row["container_fps"] for row in included if row["dataset"] == dataset})
        axes[1].scatter(fps, [NAMES[dataset]] * len(fps), color=color, s=55)
    axes[1].set_xlabel("FPS контейнера; для RetailAction это не частота съёмки")
    axes[1].set_title("Частота кадров MP4")
    save_figure(fig, "resolution_fps.png")


def groups(summary):
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    positions = list(range(len(NAMES)))
    counts = [summary["datasets"][dataset]["records"] for dataset in NAMES]
    group_counts = [summary["datasets"][dataset]["source_groups"] for dataset in NAMES]
    first = ax.bar([x - 0.18 for x in positions], counts, 0.36, label="Видеофайлы")
    second = ax.bar([x + 0.18 for x in positions], group_counts, 0.36, label="Группы исходников")
    ax.bar_label(first, padding=3)
    ax.bar_label(second, padding=3)
    ax.set_xticks(positions, list(NAMES.values()))
    ax.set_yscale("log")
    ax.set_ylim(0.65, max(counts) * 3)
    ax.set_ylabel("Количество, логарифмическая шкала")
    ax.set_title("Группа исходников не гарантирует независимость людей и магазинов")
    ax.legend()
    save_figure(fig, "source_groups.png")


def main():
    plt.switch_backend("Agg")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    (ROOT / "figures").mkdir(exist_ok=True)
    rows = load_metadata()
    summary = summarize(rows)
    (ROOT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    composition(summary)
    source_classes(summary)
    duration_and_frames(rows)
    resolution_and_fps(rows)
    groups(summary)
    print(
        f"Analyzed {summary['records']} records; {summary['included']} included; 5 figures saved."
    )


if __name__ == "__main__":
    main()
