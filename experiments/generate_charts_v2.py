#!/usr/bin/env python3
"""
Generate paper figures using audited results.

Fig 1: Safety-guard ablation bar chart (Config A with/without safety)
Fig 2: Self-learning curve (unchanged)
Fig 3: Safety guard prevention rate (unchanged)
"""
import json
import os
import sys

RESULTS_DIR = "experiments/results"
CHARTS_DIR = "experiments/charts"


def _ensure_dirs():
    os.makedirs(CHARTS_DIR, exist_ok=True)


def generate_fig1_safety_ablation(plt, np):
    """
    Fig 1: Safety-guard ablation — side-by-side bars for
    Rule Engine (no safety) vs Rule Engine (with safety).
    Shows the 6pp accuracy improvement from the safety guard.
    """
    # Audited numbers from run_no_safety_ablation.py
    data = {
        "Rule Engine\n(no safety)": {
            "overall": 82.0, "known": 85.3, "novel": 20.0
        },
        "Rule Engine\n+ Safety Guard": {
            "overall": 88.0, "known": 91.6, "novel": 20.0
        },
    }

    configs = list(data.keys())
    colors = ["#ED7D31", "#C00000"]
    groups = ["Overall\n(n=100)", "Known Patterns\n(n=95)", "Novel Patterns\n(n=5)"]

    x = np.arange(len(groups))
    width = 0.32

    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    for i, (label, color) in enumerate(zip(configs, colors)):
        vals = [data[label]["overall"], data[label]["known"], data[label]["novel"]]
        offset = x + (i - 0.5) * width
        bars = ax.bar(offset, vals, width * 0.92, label=label,
                      color=color, edgecolor="white", linewidth=1.5)
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.annotate(f"{h:.1f}%",
                            xy=(bar.get_x() + bar.get_width() / 2, h),
                            xytext=(0, 3), textcoords="offset points",
                            ha="center", va="bottom", fontsize=9, fontweight="bold")

    # Annotate the +6pp improvement on Overall
    ax.annotate("", xy=(x[0] + 0.5 * width, 88.5),
                xytext=(x[0] - 0.5 * width, 82.5),
                arrowprops=dict(arrowstyle="->", color="#2E75B6", lw=2))
    ax.text(x[0] + 0.02, 85.5, "+6 pp", color="#2E75B6",
            fontsize=10, fontweight="bold", ha="center")

    ax.set_xlabel("Accuracy Metric", fontsize=12, labelpad=8)
    ax.set_ylabel("Accuracy (%)", fontsize=12)
    ax.set_title(
        "Safety-Guard Ablation\n"
        "Rule Engine with vs. without Deterministic Safety Guard",
        fontsize=12, fontweight="bold", pad=12
    )
    ax.set_xticks(x)
    ax.set_xticklabels(groups, fontsize=11)
    ax.set_ylim(0, 110)
    ax.yaxis.grid(True, alpha=0.35, linestyle="--")
    ax.set_axisbelow(True)
    ax.legend(fontsize=10, loc="upper right", framealpha=0.9)

    note = ("Safety guard adds 6 percentage points overall by correctly forcing abstention "
            "on 6 platform-event cases.\nNovel-pattern accuracy is unchanged (1/5 = 20%) "
            "because novel cases are not platform-event cases.")
    fig.text(0.5, -0.04, note, ha="center", fontsize=8.5,
             style="italic", color="#555555", wrap=True)

    plt.tight_layout()
    out_path = os.path.join(CHARTS_DIR, "fig1_accuracy_comparison.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Saved: {out_path}")


def generate_fig2_learning_curve(plt, np):
    """Fig 2: Self-learning curve — unchanged from original."""
    csv_path = os.path.join(RESULTS_DIR, "exp2_learning_curve.csv")
    if not os.path.exists(csv_path):
        print("WARNING: exp2_learning_curve.csv not found. Skipping Fig 2.")
        return

    import csv
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    cycles = [int(r["cycle"]) for r in rows]
    overall = [float(r["accuracy"]) for r in rows]
    known = [float(r["known_accuracy"]) for r in rows]
    novel = [float(r["novel_accuracy"]) for r in rows]

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=300)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ax.plot(cycles, overall, "o-", color="#4472C4", linewidth=2.5,
            markersize=8, label="Overall Accuracy", zorder=3)
    ax.plot(cycles, known, "s--", color="#70AD47", linewidth=2,
            markersize=7, label="Known Pattern Accuracy", zorder=3)
    ax.plot(cycles, novel, "^-", color="#C00000", linewidth=2.5,
            markersize=9, label="Novel Pattern Accuracy", zorder=3)

    for x_val, y_val in zip(cycles, novel):
        ax.annotate(f"{y_val:.0f}%",
                    xy=(x_val, y_val),
                    xytext=(0, 10), textcoords="offset points",
                    ha="center", fontsize=9, color="#C00000", fontweight="bold")

    ax.set_xlabel("Feedback Cycle (verified cases in memory)", fontsize=12)
    ax.set_ylabel("Accuracy (%)", fontsize=12)
    ax.set_title(
        "Feedback-Driven Memory Improvement\n"
        "Novel-Pattern Accuracy vs. Memory Growth (20-case held-out set)",
        fontsize=12, fontweight="bold", pad=12
    )
    ax.set_xticks(cycles)
    memory_labels = ["0\n(Cycle 0)", "10\n(Cycle 1)", "25\n(Cycle 2)",
                     "50\n(Cycle 3)", "75\n(Cycle 4)", "80\n(Cycle 5)"]
    ax.set_xticklabels(memory_labels, fontsize=9)
    ax.set_ylim(0, 115)
    ax.yaxis.grid(True, alpha=0.35, linestyle="--")
    ax.set_axisbelow(True)
    ax.legend(fontsize=10, loc="lower right", framealpha=0.9)

    note = ("Each 20pp step in novel accuracy = 1 case (n=5 novel cases). "
            "Confidence intervals are wide; trend is indicative.")
    fig.text(0.5, -0.04, note, ha="center", fontsize=8.5,
             style="italic", color="#555555")

    plt.tight_layout()
    out_path = os.path.join(CHARTS_DIR, "fig2_learning_curve.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Saved: {out_path}")


def generate_fig3_safety_guard(plt, np):
    """Fig 3: Safety guard prevention rate per rule."""
    json_path = os.path.join(RESULTS_DIR, "table3_safety.json")
    if not os.path.exists(json_path):
        print("WARNING: table3_safety.json not found. Skipping Fig 3.")
        return

    with open(json_path) as f:
        data = json.load(f)

    rules = sorted(data.keys())
    prevented = [data[r]["prevented"] for r in rules]
    tested = [data[r]["tested"] for r in rules]
    rule_labels = [r.replace(" ", "\n") for r in rules]

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    x = np.arange(len(rules))
    width = 0.35

    bars_tested = ax.bar(x - width / 2, tested, width, label="Cases Tested",
                         color="#4472C4", edgecolor="white")
    bars_prevented = ax.bar(x + width / 2, prevented, width, label="Unsafe Prevented",
                            color="#C00000", edgecolor="white")

    for bar in bars_prevented:
        h = bar.get_height()
        ax.annotate(f"{h}/5",
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9, fontweight="bold",
                    color="#C00000")

    ax.set_xlabel("Safety Rule", fontsize=12)
    ax.set_ylabel("Number of Cases", fontsize=12)
    ax.set_title(
        "Safety Guard Prevention Rate per Rule\n"
        "All 30 adversarial suggestions intercepted (100% recall)",
        fontsize=12, fontweight="bold", pad=12
    )
    ax.set_xticks(x)
    ax.set_xticklabels(rule_labels, fontsize=9)
    ax.set_ylim(0, 8)
    ax.yaxis.grid(True, alpha=0.35, linestyle="--")
    ax.set_axisbelow(True)
    ax.legend(fontsize=10, framealpha=0.9)

    note = "False-block rate on 100-case benchmark: 0/100 (0.0%)"
    fig.text(0.5, -0.02, note, ha="center", fontsize=9,
             style="italic", color="#555555")

    plt.tight_layout()
    out_path = os.path.join(CHARTS_DIR, "fig3_safety_guard.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Saved: {out_path}")


def main():
    _ensure_dirs()
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib/numpy not installed. Install with: pip install matplotlib numpy")
        sys.exit(1)

    print("Generating updated paper figures...")
    generate_fig1_safety_ablation(plt, np)
    generate_fig2_learning_curve(plt, np)
    generate_fig3_safety_guard(plt, np)
    print("Done. Figures saved to experiments/charts/")


if __name__ == "__main__":
    main()
