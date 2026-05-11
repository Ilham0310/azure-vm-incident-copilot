# How to Run Experiments

## Prerequisites

```bash
pip install -r requirements.txt
pip install matplotlib
python main.py --setup
```

Set `GROQ_API_KEY` in `.env` (required for LLM-based configs B, C, D).

Config A (rule engine baseline) runs without any API keys.

## Generate Expanded Benchmark (100 cases)

```bash
python setup/generate_benchmark_v2.py
```

Writes to `data/benchmark_cases_v2.csv` (does not overwrite original).

## Run All Experiments

```bash
python experiments/evaluation_runner.py
```

This runs:
- Experiment 1: Accuracy comparison (4 configs × 100 cases)
- Experiment 2: Self-learning curve (6 cycles)
- Experiment 3: Safety guard impact (20 adversarial cases)

Results are written to `experiments/results/`.

## Generate Charts

```bash
python experiments/generate_charts.py
```

Produces 3 publication-quality PNG charts in `experiments/charts/`:
- `fig1_accuracy_comparison.png` — grouped bar chart
- `fig2_learning_curve.png` — line chart with annotations
- `fig3_safety_guard.png` — stacked bar chart

## View Results

```bash
cat experiments/results/PAPER_RESULTS_SUMMARY.md
```

## Estimated Runtime

| Experiment | Description | Estimated Time |
|---|---|---|
| Experiment 1 | 100 cases × 4 configs | ~15 min with Groq API |
| Experiment 2 | 6 cycles × ~50 cases avg | ~10 min |
| Experiment 3 | 20 adversarial cases | ~5 min |
| **Total** | | **~30 min** |

Config A (rule engine) runs in seconds. LLM configs depend on API latency.

## Output Files

```
experiments/
├── results/
│   ├── exp1_accuracy_comparison.csv   # Per-case results for all 4 configs
│   ├── exp1_summary.json              # Aggregated accuracy metrics
│   ├── exp2_learning_curve.csv        # Accuracy per feedback cycle
│   ├── exp3_safety_guard.csv          # Safety rule activation details
│   └── PAPER_RESULTS_SUMMARY.md       # Combined tables for paper
├── charts/
│   ├── fig1_accuracy_comparison.png   # Fig 1 for paper
│   ├── fig2_learning_curve.png        # Fig 2 for paper
│   └── fig3_safety_guard.png          # Fig 3 for paper
└── README.md                          # This file
```
