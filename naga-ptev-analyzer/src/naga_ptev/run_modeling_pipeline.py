from __future__ import annotations

import json
from pathlib import Path

from naga_ptev.branch_delta import build_branch_delta
from naga_ptev.modeling_dataset import LOCAL_MODEL_NOTICE, load_base_dataset, split_dataframe_by_state, write_quality_report
from naga_ptev.modeling_eval import evaluate_models, write_evaluation_outputs
from naga_ptev.modeling_plots import write_modeling_plots
from naga_ptev.modeling_train import fit_models, save_model


def run_pipeline(
    *,
    base_csv: str | Path = "naga-ptev-analyzer/out/dataset/base_predictions.csv",
    branch_csv: str | Path = "naga-ptev-analyzer/out/dataset/branch_predictions.csv",
    out_dir: str | Path = "out/modeling",
) -> dict[str, object]:
    out = Path(out_dir)
    reports = out / "reports"
    models_dir = out / "models"
    plots_dir = out / "plots"
    reports.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    base_df = load_base_dataset(base_csv)
    write_quality_report(base_df, reports)
    train_df, test_df = split_dataframe_by_state(base_df, test_size=0.2, random_state=42)
    models = fit_models(train_df)
    metrics, grouped, best_predictions = evaluate_models(models, test_df)
    write_evaluation_outputs(metrics=metrics, grouped=grouped, best_predictions=best_predictions, reports_dir=reports)

    for model in models:
        save_model(model, models_dir / f"{model.name}.pkl")
    best_model_name = str(metrics.iloc[0]["model"])
    best_model = next(model for model in models if model.name == best_model_name)
    save_model(best_model, models_dir / "best_model.pkl")

    write_modeling_plots(best_predictions, plots_dir)
    branch_info = build_branch_delta(base_csv=base_csv, branch_csv=branch_csv, reports_dir=reports)
    (reports / "branch_delta_processing_info.json").write_text(
        json.dumps(branch_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (reports / "modeling_report.md").open("a", encoding="utf-8") as handle:
        handle.write("\n## 学習・評価結果\n\n")
        handle.write(f"**制約:** {LOCAL_MODEL_NOTICE}\n\n")
        handle.write(f"- train rows: {len(train_df)}\n")
        handle.write(f"- test rows: {len(test_df)}\n")
        handle.write(f"- trained models: {', '.join(model.name for model in models)}\n")
        handle.write(f"- best model: {best_model_name}\n")
        handle.write(f"- branch rows read: {branch_info['branch_rows_read']}\n")
        handle.write(f"- branch merged rows: {branch_info['merged_rows']}\n")
        handle.write(f"- branch processing max rows: {branch_info['max_rows']}\n")
        handle.write(f"- branch processing truncated: {branch_info['truncated']}\n")
    return {
        "best_model": best_model_name,
        "model_count": len(models),
        "reports_dir": str(reports),
        "plots_dir": str(plots_dir),
        "models_dir": str(models_dir),
    }


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), ensure_ascii=False, indent=2))

