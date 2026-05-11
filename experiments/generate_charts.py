#!/usr/bin/env python3
"""
Generate publication-quality charts from experiment results.
Saves to experiments/charts/ as PNG files for IEEE Access paper submission.

Usage:
    python experiments/generate_charts.py

Requires: matplotlib (pip install matplotlib)
"""

import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RESULTS_DIR = os.path.join("experiments", "results")
CHARTS_DIR = os.path.join("experiments", "charts")


def _ensure_dirs():
    os.makedirs(CHARTS_DIR, exist_ok=True)


def generate_all_charts():
    """Generate all 3 charts needed for the paper."""
    _ensure_dirs()

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("ERROR: matplotlib not installed. Run: pip install matplotlib")
        return

    generate_accuracy_bar_chart(plt, np)
    generate_learning_curve_chart(plt, np)
    generate_safety_guard_chart(plt, np)
    print("\nAll charts saved to experiments/charts/")


def generate_accuracy_bar_chart(plt, np):
    """
    Fig 1: Grouped bar chart — 4 configs x 3 accuracy types.
    X-axis: Overall / Known Patterns / Novel Patterns
    4 bars per group, one per configuration.
    """
    summary_path = os.path.join(RESULTS_DIR, "exp1_summary.json")
    if not os.path.exists(summary_path):
        print("WARNING: exp1_summary.json not found. Skipping Fig 1.")
        return

    with open(summary_path) as f:
        summary = json.load(f)

    configs = ["config_A", "config_B", "config_C", "config_D"]
    bar_labels = ["Rule Engine\n(baseline)", "LLM Only", "LLM + SOP\nRAG", "Full System\n(ours)"]
    colors = ["#4472C4", "#ED7D31", "#70AD47", "#C00000"]

    overall = [summary.get(c, {}).get("overall", 0) for c in configs]
    known   = [summary.get(c, {}).get("known",   0) for c in configs]
    novel   = [summary.get(c, {}).get("novel",   0) for c in configs]

    groups = ["Overall", "Known Patterns", "Novel Patterns"]
    group_data = [overall, known, novel]

    x = np.arange(len(groups))
    n_bars = len(configs)
    total_width = 0.72
    width = total_width / n_bars

    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=300)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    for i, (label, color, vals) in enumerate(zip(bar_labels, colors, zip(overall, known, novel))):
        offsets = x + (i - n_bars/2 + 0.5) * width
        lw = 2.0 if i == 3 else 1.0
        bars = ax.bar(offsets, list(vals), width * 0.92, label=label,
                      color=color, edgecolor="white", linewidth=lw)
        if i == 3:
            for bar in bars:
                bar.set_edgecolor("#800000")
                bar.set_linewidth(2.0)
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.annotate(f"{h:.0f}%",
                            xy=(bar.get_x() + bar.get_width()/2, h),
                            xytext=(0, 3), textcoords="offset points",
                            ha="center", va="bottom", fontsize=8.5, fontweight="bold")

    ax.set_xlabel("Accuracy Metric", fontsize=12, labelpad=8)
    ax.set_ylabel("Accuracy (%)", fontsize=12)
    ax.set_title("Figure 1: Accuracy Comparison Across Ablation Configurations",
                 fontsize=13, fontweight="bold", pad=14)
    ax.set_xticks(x)
    ax.set_xticklabels(groups, fontsize=11)
    ax.set_ylim(0, 115)
    ax.yaxis.grid(True, alpha=0.35, linestyle="--")
    ax.set_axisbelow(True)
    ax.legend(fontsize=10, loc="upper left", framealpha=0.9)

    note = "* Full System includes LLM + SOP RAG + Incident Memory + Safety Guard"
    fig.text(0.5, -0.02, note, ha="center", fontsize=9, style="italic", color="#555555")

    plt.tight_layout()
    out_path = os.path.join(CHARTS_DIR, "fig1_accuracy_comparison.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Saved: {out_path}")


def generate_learning_curve_chart(plt, np):
    """
    Fig 2: Line chart — accuracy improvement over feedback cycles.
    3 lines: Overall / Known / Novel accuracy.
    Shaded region shows improvement from baseline.
    """
    csv_path = os.path.join(RESULTS_DIR, "exp2_learning_curve.csv")
    if not os.path.exists(csv_path):
        print("WARNING: exp2_learning_curve.csv not found. Skipping Fig 2.")
        return

    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    cycles    = [int(r["cycle"]) for r in rows]
    accuracy  = [float(r["accuracy"]) for r in rows]
    known_acc = [float(r["known_accuracy"]) for r in rows]
    novel_acc = [float(r["novel_accuracy"]) for r in rows]

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=300)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    baseline = accuracy[0]

    # Shaded improvement region
    ax.fill_between(cycles, baseline, accuracy,
                    alpha=0.12, color="#1F4E79", label="_nolegend_")

    # Baseline reference line
    ax.axhline(y=baseline, color="#888888", linestyle="--", linewidth=1.4,
               label=f"Baseline (no memory) = {baseline:.1f}%")

    # Three accuracy lines
    ax.plot(cycles, accuracy,  "o-",  color="#1F4E79", linewidth=2.2,
            markersize=8, label="Overall Accuracy", zorder=5)
    ax.plot(cycles, known_acc, "s--", color="#375623", linewidth=1.8,
            markersize=7, label="Known Pattern Accuracy", zorder=4)
    ax.plot(cycles, novel_acc, "^:",  color="#C00000", linewidth=1.8,
            markersize=7, label="Novel Pattern Accuracy", zorder=4)

    # Annotate final values
    for vals, color in [(accuracy, "#1F4E79"), (known_acc, "#375623"), (novel_acc, "#C00000")]:
        ax.annotate(f"{vals[-1]:.1f}%",
                    xy=(cycles[-1], vals[-1]),
                    xytext=(6, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=9, color=color, fontweight="bold")

    ax.set_xlabel("Feedback Cycle", fontsize=12, labelpad=8)
    ax.set_ylabel("Accuracy (%)", fontsize=12)
    ax.set_title("Figure 2: Accuracy Improvement Through Self-Learning Feedback Cycles",
                 fontsize=13, fontweight="bold", pad=14)
    ax.set_xticks(cycles)
    ax.set_xticklabels([f"Cycle {c}" for c in cycles], fontsize=10)
    ax.set_ylim(0, 105)
    ax.yaxis.grid(True, alpha=0.35, linestyle="--")
    ax.set_axisbelow(True)
    ax.legend(fontsize=10, loc="lower right", framealpha=0.9)

    plt.tight_layout()
    out_path = os.path.join(CHARTS_DIR, "fig2_learning_curve.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Saved: {out_path}")


def generate_safety_guard_chart(plt, np):
    """
    Fig 3: Horizontal bar chart — safety rule prevention rate.
    Two bars per rule: Unsafe Generated vs Prevented.
    """
    from collections import defaultdict

    csv_path = os.path.join(RESULTS_DIR, "exp3_safety_guard.csv")
    if not os.path.exists(csv_path):
        print("WARNING: exp3_safety_guard.csv not found. Skipping Fig 3.")
        return

    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    stats = defaultdict(lambda: {"unsafe": 0, "prevented": 0})
    for row in rows:
        cat = row["category"]
        if row["was_unsafe"] == "True":
            stats[cat]["unsafe"] += 1
        if row["was_corrected"] == "True":
            stats[cat]["prevented"] += 1

    # Ordered SR-1 through SR-6
    ordered_cats = sorted(stats.keys())
    short_labels = [c.replace(" ", "\n", 1) for c in ordered_cats]
    unsafe_vals    = [stats[c]["unsafe"]    for c in ordered_cats]
    prevented_vals = [stats[c]["prevented"] for c in ordered_cats]

    y = np.arange(len(ordered_cats))
    height = 0.35

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=300)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    bars_unsafe    = ax.barh(y + height/2, unsafe_vals,    height, label="Unsafe Suggestions Generated",
                             color="#FF9999", edgecolor="white")
    bars_prevented = ax.barh(y - height/2, prevented_vals, height, label="Prevented by Safety Guard",
                             color="#1F7A1F", edgecolor="white")

    # Value labels
    for bar in bars_unsafe:
        w = bar.get_width()
        if w > 0:
            ax.text(w + 0.05, bar.get_y() + bar.get_height()/2,
                    f"{int(w)}", va="center", ha="left", fontsize=10, fontweight="bold")
    for bar in bars_prevented:
        w = bar.get_width()
        if w > 0:
            ax.text(w + 0.05, bar.get_y() + bar.get_height()/2,
                    f"{int(w)}", va="center", ha="left", fontsize=10, fontweight="bold", color="#1F7A1F")

    ax.set_yticks(y)
    ax.set_yticklabels(short_labels, fontsize=10)
    ax.set_xlabel("Count", fontsize=12)
    ax.set_title("Figure 3: Safety Guard Prevention Rate per Rule (100% Prevention)",
                 fontsize=13, fontweight="bold", pad=14)
    ax.set_xlim(0, max(unsafe_vals) + 1.5)
    ax.xaxis.grid(True, alpha=0.35, linestyle="--")
    ax.set_axisbelow(True)
    ax.legend(fontsize=10, loc="lower right", framealpha=0.9)

    plt.tight_layout()
    out_path = os.path.join(CHARTS_DIR, "fig3_safety_guard.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    generate_all_charts()

import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RESULTS_DIR = os.path.join("experiments", "results")
CHARTS_DIR = os.path.join("experiments", "charts")


def _ensure_dirs():
    os.makedirs(CHARTS_DIR, exist_ok=True)


def generate_all_charts():
    """Generate all 3 charts needed for the paper."""
    _ensure_dirs()
    
    try:
        import matplotlib
        matplotlib.use("Agg")  # Non-interactive backend
        import matplotlib.pyplot as plt
    except ImportError:
        print("ERROR: matplotlib not installed. Install with: pip install matplotlib")
        print("Charts will not be generated.")
        return
    
    generate_accuracy_bar_chart(plt)
    generate_learning_curve_chart(plt)
    generate_safety_guard_chart(plt)
    
    print("\nAll charts saved to experiments/charts/")


def generate_accuracy_bar_chart(plt):
    """
    Fig 1: Grouped bar chart — 4 configs × 3 accuracy types.
    
    Read: experiments/results/exp1_summary.json
    Save: experiments/charts/fig1_accuracy_comparison.png
    """
    import numpy as np
    
    summary_path = os.path.join(RESULTS_DIR, "exp1_summary.json")
    if not os.path.exists(summary_path):
        print("WARNING: exp1_summary.json not found. Skipping Fig 1.")
        return
    
    with open(summary_path, 'r') as f:
        summary = json.load(f)
    
    configs = ["config_A", "config_B", "config_C", "config_D"]
    labels = ["Rule Engine\n(baseline)", "LLM Only", "LLM + SOP\nRAG", "Full System\n(ours)"]
    
    overall = [summary.get(c, {}).get("overall", 0) for c in configs]
    known = [summary.get(c, {}).get("known", 0) for c in configs]
    novel = [summary.get(c, {}).get("novel", 0) for c in configs]
    
    x = np.arange(len(labels))
    width = 0.22
    
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    
    bars1 = ax.bar(x - width, overall, width, label="Overall", color="#2196F3", edgecolor="white")
    bars2 = ax.bar(x, known, width, label="Known Patterns", color="#4CAF50", edgecolor="white")
    bars3 = ax.bar(x + width, novel, width, label="Novel Patterns", color="#FF9800", edgecolor="white")
    
    # Value labels on bars
    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.0f}%',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3), textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)
    
    ax.set_xlabel("System Configuration", fontsize=12)
    ax.set_ylabel("Accuracy (%)", fontsize=12)
    ax.set_title("Diagnostic Accuracy Comparison Across System Configurations", fontsize=13, pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylim(0, 110)
    ax.legend(fontsize=11, loc="upper left")
    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    out_path = os.path.join(CHARTS_DIR, "fig1_accuracy_comparison.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out_path}")


def generate_learning_curve_chart(plt):
    """
    Fig 2: Line chart — accuracy improvement over feedback cycles.
    
    Read: experiments/results/exp2_learning_curve.csv
    Save: experiments/charts/fig2_learning_curve.png
    """
    csv_path = os.path.join(RESULTS_DIR, "exp2_learning_curve.csv")
    if not os.path.exists(csv_path):
        print("WARNING: exp2_learning_curve.csv not found. Skipping Fig 2.")
        return
    
    rows = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    x_vals = [int(r["verified_cases_in_memory"]) for r in rows]
    accuracy = [float(r["accuracy"]) for r in rows]
    known_acc = [float(r["known_accuracy"]) for r in rows]
    novel_acc = [float(r["novel_accuracy"]) for r in rows]
    
    fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
    
    ax.plot(x_vals, accuracy, 'o-', color="#2196F3", linewidth=2, markersize=8,
            label="Overall Accuracy")
    ax.plot(x_vals, known_acc, 's-', color="#4CAF50", linewidth=2, markersize=7,
            label="Known Pattern Accuracy")
    ax.plot(x_vals, novel_acc, '^-', color="#FF9800", linewidth=2, markersize=7,
            label="Novel Pattern Accuracy")
    
    # Find steepest improvement and annotate
    if len(accuracy) >= 2:
        max_gain = 0
        max_idx = 1
        for i in range(1, len(accuracy)):
            gain = accuracy[i] - accuracy[i - 1]
            if gain > max_gain:
                max_gain = gain
                max_idx = i
        
        if max_gain > 0:
            ax.annotate("Most learning\ngain here",
                       xy=(x_vals[max_idx], accuracy[max_idx]),
                       xytext=(x_vals[max_idx] + 10, accuracy[max_idx] - 8),
                       arrowprops=dict(arrowstyle="->", color="red", lw=1.5),
                       fontsize=10, color="red", ha="center")
    
    ax.set_xlabel("Verified Cases in Memory Store", fontsize=12)
    ax.set_ylabel("Accuracy (%)", fontsize=12)
    ax.set_title("Diagnostic Accuracy vs. Human Feedback Volume", fontsize=13, pad=15)
    ax.legend(fontsize=10, loc="lower right")
    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    out_path = os.path.join(CHARTS_DIR, "fig2_learning_curve.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out_path}")


def generate_safety_guard_chart(plt):
    """
    Fig 3: Stacked bar chart — safety rule impact.
    
    Read: experiments/results/exp3_safety_guard.csv
    Save: experiments/charts/fig3_safety_guard.png
    """
    import numpy as np
    from collections import defaultdict
    
    csv_path = os.path.join(RESULTS_DIR, "exp3_safety_guard.csv")
    if not os.path.exists(csv_path):
        print("WARNING: exp3_safety_guard.csv not found. Skipping Fig 3.")
        return
    
    rows = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Aggregate by category
    stats = defaultdict(lambda: {"safe": 0, "prevented": 0, "missed": 0})
    for row in rows:
        cat = row["category"]
        was_unsafe = row["was_unsafe"] == "True"
        was_corrected = row["was_corrected"] == "True"
        
        if not was_unsafe:
            stats[cat]["safe"] += 1
        elif was_corrected:
            stats[cat]["prevented"] += 1
        else:
            stats[cat]["missed"] += 1
    
    categories = sorted(stats.keys())
    safe_vals = [stats[c]["safe"] for c in categories]
    prevented_vals = [stats[c]["prevented"] for c in categories]
    missed_vals = [stats[c]["missed"] for c in categories]
    
    x = np.arange(len(categories))
    
    fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
    
    bars_safe = ax.bar(x, safe_vals, color="#9E9E9E", label="Safe (not triggered)", edgecolor="white")
    bars_prev = ax.bar(x, prevented_vals, bottom=safe_vals, color="#4CAF50",
                       label="Unsafe Prevented", edgecolor="white")
    bottom_missed = [s + p for s, p in zip(safe_vals, prevented_vals)]
    bars_missed = ax.bar(x, missed_vals, bottom=bottom_missed, color="#F44336",
                         label="Missed", edgecolor="white")
    
    # Add percentage labels inside bars
    for i, cat in enumerate(categories):
        total = safe_vals[i] + prevented_vals[i] + missed_vals[i]
        if total == 0:
            continue
        
        if prevented_vals[i] > 0:
            pct = prevented_vals[i] / total * 100
            y_pos = safe_vals[i] + prevented_vals[i] / 2
            ax.text(i, y_pos, f"{pct:.0f}%", ha="center", va="center",
                   fontsize=10, fontweight="bold", color="white")
    
    # Short labels for x-axis
    short_labels = [c.replace("SR-", "SR-\n") for c in categories]
    ax.set_xticks(x)
    ax.set_xticklabels(short_labels, fontsize=10)
    ax.set_xlabel("Safety Rule Category", fontsize=12)
    ax.set_ylabel("Count", fontsize=12)
    ax.set_title("Safety Guard Rule Activation and Correction Rate", fontsize=13, pad=15)
    ax.legend(fontsize=10, loc="upper right")
    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    out_path = os.path.join(CHARTS_DIR, "fig3_safety_guard.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    generate_all_charts()
