from __future__ import annotations

import asyncio
import getpass
from pathlib import Path
import subprocess
import sys
from typing import Any

from rich.console import Console
from rich.table import Table
import typer

from naga_ptev.analysis import branch_summaries_to_dataframe, compare_current_and_kyotaku_plus_one
from naga_ptev.client import (
    NagaPtevClient,
    _clear_niconico_credentials_in_keyring,
    _keyring_available,
    _load_niconico_credentials_from_keyring,
    _store_niconico_credentials_in_keyring,
)
from naga_ptev.collector import CollectorStop, collect_dataset as run_collect_dataset
from naga_ptev.evaluation import evaluate_model as run_evaluate_model
from naga_ptev.featurize import build_dataset_from_collector
from naga_ptev.modeling import train_model as run_train_model
from naga_ptev.models import KyokuState, PointConfig
from naga_ptev.parser import parse_analyzer_response
from naga_ptev.plots import build_plots
from naga_ptev.sampler import sample_states, write_samples_csv
from naga_ptev.scenarios import (
    summarize_baseline,
    summarize_ron_branches,
    summarize_ryukyoku_branches,
    summarize_tsumo_branches,
)
from naga_ptev.storage import append_jsonl, save_dataframe_csv, save_raw_json, timestamped_artifact_path

app = typer.Typer(add_completion=False)
console = Console()


def _parse_scores(raw_scores: str) -> list[int]:
    values = [part.strip() for part in raw_scores.split(",") if part.strip()]
    if len(values) != 4:
        raise typer.BadParameter("scores must contain 4 comma-separated integers")
    try:
        return [int(value) for value in values]
    except ValueError as exc:
        raise typer.BadParameter("scores must contain only integers") from exc


def _parse_rank_points(raw_points: str | None) -> PointConfig:
    if not raw_points:
        return PointConfig()
    values = [part.strip() for part in raw_points.split(",") if part.strip()]
    if len(values) != 4:
        raise typer.BadParameter("rank points must contain 4 comma-separated numbers")
    try:
        return PointConfig(rank_points=[float(value) for value in values])
    except ValueError as exc:
        raise typer.BadParameter("rank points must contain only numbers") from exc


def _build_state(kyoku: int, honba: int, kyotaku: int, scores: str) -> KyokuState:
    return KyokuState(kyoku=kyoku, honba=honba, kyotaku=kyotaku, scores=_parse_scores(scores))


async def _open_client(storage: str) -> NagaPtevClient:
    client = NagaPtevClient()
    await client.open_with_state(storage)
    return client


def _exit_with_user_error(exc: Exception) -> typer.Exit:
    console.print(f"[red]{exc}[/red]")
    return typer.Exit(code=1)


def _render_baseline_table(parsed_response: Any) -> None:
    table = Table(title="Baseline ptEV")
    table.add_column("Seat")
    table.add_column("ptEV", justify="right")
    table.add_column("P1", justify="right")
    table.add_column("P2", justify="right")
    table.add_column("P3", justify="right")
    table.add_column("P4", justify="right")
    for seat in parsed_response.base:
        table.add_row(
            str(seat.seat),
            f"{seat.ptev:.3f}",
            f"{seat.rank_prob.p1:.4f}",
            f"{seat.rank_prob.p2:.4f}",
            f"{seat.rank_prob.p3:.4f}",
            f"{seat.rank_prob.p4:.4f}",
        )
    console.print(table)


@app.command()
def login(
    storage: str = typer.Option(".secrets/naga_state.json", help="Playwright storage state path."),
) -> None:
    async def _run() -> None:
        client = NagaPtevClient()
        try:
            await client.login_and_save_state(storage)
        finally:
            await client.close()

    asyncio.run(_run())
    console.print(f"Saved storage state: {storage}")


@app.command("store-login")
def store_login() -> None:
    if not _keyring_available():
        raise _exit_with_user_error(
            RuntimeError(
                "Secure credential storage is unavailable because `keyring` is not installed. "
                "Run `pip install -e naga-ptev-analyzer` or `pip install keyring` first."
            )
        )
    login_id = typer.prompt("NicoNico mail address or telephone number").strip()
    password = getpass.getpass("NicoNico password: ").strip()
    if not login_id or not password:
        raise _exit_with_user_error(RuntimeError("Both NicoNico login ID and password are required."))
    try:
        _store_niconico_credentials_in_keyring(login_id, password)
    except RuntimeError as exc:
        raise _exit_with_user_error(exc) from None
    console.print("Stored NAGA login credentials in the OS credential store.")


@app.command("clear-login")
def clear_login() -> None:
    if not _keyring_available():
        raise _exit_with_user_error(
            RuntimeError(
                "Secure credential storage is unavailable because `keyring` is not installed. "
                "Run `pip install -e naga-ptev-analyzer` or `pip install keyring` first."
            )
        )
    try:
        removed_any = _clear_niconico_credentials_in_keyring()
    except RuntimeError as exc:
        raise _exit_with_user_error(exc) from None
    if removed_any:
        console.print("Cleared stored NAGA login credentials from the OS credential store.")
    else:
        console.print("No stored NAGA login credentials were found in the OS credential store.")


@app.command("login-status")
def login_status(
    storage: str = typer.Option(".secrets/naga_state.json", help="Playwright storage state path."),
) -> None:
    storage_path = Path(storage)
    state_exists = storage_path.exists()
    keyring_ready = _keyring_available()
    keyring_credentials = _load_niconico_credentials_from_keyring() if keyring_ready else None
    table = Table(title="NAGA Login Status")
    table.add_column("Item")
    table.add_column("Value")
    table.add_row("Storage state", str(storage_path))
    table.add_row("Storage exists", "yes" if state_exists else "no")
    table.add_row("OS credential store", "available" if keyring_ready else "unavailable")
    table.add_row("Stored credentials", "yes" if keyring_credentials is not None else "no")
    console.print(table)


@app.command()
def probe(
    storage: str = typer.Option(..., help="Playwright storage state path."),
    kyoku: int = typer.Option(...),
    honba: int = typer.Option(...),
    kyotaku: int = typer.Option(...),
    scores: str = typer.Option(..., help="Comma-separated score quartet, ex. 250,250,250,250"),
    out: str | None = typer.Option(None, help="Optional JSON path for sanitized probe output."),
) -> None:
    state = _build_state(kyoku, honba, kyotaku, scores)

    async def _run() -> dict[str, Any]:
        client = await _open_client(storage)
        try:
            return await client.probe_endpoint(state)
        finally:
            await client.close()

    try:
        result = asyncio.run(_run())
    except (FileNotFoundError, RuntimeError) as exc:
        raise _exit_with_user_error(exc) from None
    sanitized = {
        "page_url": result.get("page_url"),
        "endpoint": result.get("endpoint"),
        "csrf_found": bool(result.get("csrf_token")),
        "auth_redirected": bool(result.get("auth_redirected")),
        "captured_call_count": len(result.get("captured_calls", [])),
        "sample_json_found": result.get("sample_json") is not None,
        "captured_calls": result.get("captured_calls", []),
        "sample_json": result.get("sample_json"),
    }
    console.print_json(data=sanitized)
    append_jsonl(
        sanitized,
        Path("out/logs") / "probe.jsonl",
    )
    if out:
        save_raw_json(sanitized, out)


@app.command()
def query(
    storage: str = typer.Option(..., help="Playwright storage state path."),
    kyoku: int = typer.Option(...),
    honba: int = typer.Option(...),
    kyotaku: int = typer.Option(...),
    scores: str = typer.Option(..., help="Comma-separated score quartet, ex. 250,250,250,250"),
    out: str | None = typer.Option(None, help="Optional JSON output path."),
) -> None:
    state = _build_state(kyoku, honba, kyotaku, scores)

    async def _run() -> tuple[dict[str, Any], Path | None]:
        client = await _open_client(storage)
        try:
            raw = await client.query(state)
            return raw, client.last_raw_path
        finally:
            await client.close()

    try:
        raw, auto_path = asyncio.run(_run())
    except (FileNotFoundError, RuntimeError) as exc:
        raise _exit_with_user_error(exc) from None
    if out:
        save_raw_json(raw, out)
        console.print(f"Saved query response: {out}")
    elif auto_path is not None:
        console.print(f"Saved query response: {auto_path}")
    console.print(f"JSON status: {raw.get('status')}")


@app.command()
def analyze(
    storage: str = typer.Option(..., help="Playwright storage state path."),
    kyoku: int = typer.Option(...),
    honba: int = typer.Option(...),
    kyotaku: int = typer.Option(...),
    scores: str = typer.Option(..., help="Comma-separated score quartet, ex. 250,250,250,250"),
    out: str = typer.Option("out/csv/analysis.csv", help="CSV output path."),
    rank_points: str | None = typer.Option(None, help="Optional rank-point vector, ex. 75,30,0,-105"),
) -> None:
    state = _build_state(kyoku, honba, kyotaku, scores)
    point_config = _parse_rank_points(rank_points)

    async def _run() -> tuple[Any, Path | None]:
        client = await _open_client(storage)
        try:
            raw = await client.query(state)
            parsed = parse_analyzer_response(raw, state, point_config=point_config)
            return parsed, client.last_raw_path
        finally:
            await client.close()

    try:
        parsed_response, raw_path = asyncio.run(_run())
    except (FileNotFoundError, RuntimeError) as exc:
        raise _exit_with_user_error(exc) from None
    summaries = [
        *summarize_baseline(parsed_response),
        *summarize_ron_branches(parsed_response),
        *summarize_tsumo_branches(parsed_response),
        *summarize_ryukyoku_branches(parsed_response),
    ]
    df = branch_summaries_to_dataframe(summaries)
    save_dataframe_csv(df, out)
    _render_baseline_table(parsed_response)
    console.print(
        f"Saved analysis CSV: {out}\n"
        f"Saved raw artifact: {raw_path}\n"
        f"Ron branches: {len(parsed_response.ron_branches)} | "
        f"Tsumo branches: {len(parsed_response.tsumo_branches)} | "
        f"Ryukyoku branches: {len(parsed_response.ryukyoku_branches)}"
    )


@app.command("compare-kyotaku")
def compare_kyotaku(
    storage: str = typer.Option(..., help="Playwright storage state path."),
    kyoku: int = typer.Option(...),
    honba: int = typer.Option(...),
    kyotaku: int = typer.Option(...),
    scores: str = typer.Option(..., help="Comma-separated score quartet, ex. 250,250,250,250"),
    add: int = typer.Option(1, help="Kyotaku increment."),
    out: str = typer.Option("out/csv/compare_kyotaku.csv", help="CSV output path."),
    rank_points: str | None = typer.Option(None, help="Optional rank-point vector, ex. 75,30,0,-105"),
) -> None:
    current_state = _build_state(kyoku, honba, kyotaku, scores)
    point_config = _parse_rank_points(rank_points)
    _, plus_state = compare_current_and_kyotaku_plus_one(current_state, add=add)

    async def _run() -> tuple[Any, Any]:
        client = await _open_client(storage)
        try:
            current_raw = await client.query(current_state)
            plus_raw = await client.query(plus_state)
            return (
                parse_analyzer_response(current_raw, current_state, point_config=point_config),
                parse_analyzer_response(plus_raw, plus_state, point_config=point_config),
            )
        finally:
            await client.close()

    try:
        current_response, plus_response = asyncio.run(_run())
    except (FileNotFoundError, RuntimeError) as exc:
        raise _exit_with_user_error(exc) from None
    import pandas as pd

    rows: list[dict[str, Any]] = []
    for base_seat, plus_seat in zip(current_response.base, plus_response.base, strict=True):
        rows.append(
            {
                "seat": base_seat.seat,
                "current_ptev": base_seat.ptev,
                "kyotaku_plus_ptev": plus_seat.ptev,
                "delta_ptev": plus_seat.ptev - base_seat.ptev,
                "current_p1": base_seat.rank_prob.p1,
                "current_p2": base_seat.rank_prob.p2,
                "current_p3": base_seat.rank_prob.p3,
                "current_p4": base_seat.rank_prob.p4,
                "kyotaku_plus_p1": plus_seat.rank_prob.p1,
                "kyotaku_plus_p2": plus_seat.rank_prob.p2,
                "kyotaku_plus_p3": plus_seat.rank_prob.p3,
                "kyotaku_plus_p4": plus_seat.rank_prob.p4,
            }
        )
    save_dataframe_csv(pd.DataFrame(rows), out)

    table = Table(title="Kyotaku comparison")
    table.add_column("Seat")
    table.add_column("Current ptEV", justify="right")
    table.add_column("Kyotaku+ ptEV", justify="right")
    table.add_column("Delta", justify="right")
    for row in rows:
        table.add_row(
            str(row["seat"]),
            f"{row['current_ptev']:.3f}",
            f"{row['kyotaku_plus_ptev']:.3f}",
            f"{row['delta_ptev']:.3f}",
        )
    console.print(table)
    console.print(f"Saved kyotaku comparison CSV: {out}")


@app.command("generate-samples")
def generate_samples(
    method: str = typer.Option("boundary", help="Sampler: grid/random/boundary/south_round_boundary/kyotaku_comparison."),
    limit: int | None = typer.Option(None, help="Maximum number of unique states."),
    out: str = typer.Option("out/samples/boundary.csv", help="Output CSV path."),
    seed: int = typer.Option(1, help="Random sampler seed."),
) -> None:
    try:
        states = sample_states(method, limit=limit, seed=seed)
    except ValueError as exc:
        raise _exit_with_user_error(exc) from None
    output_path = write_samples_csv(states, out)
    console.print(f"Saved {len(states)} samples: {output_path}")


@app.command("collect-dataset")
def collect_dataset(
    samples: str = typer.Option(..., help="Sample CSV created by generate-samples."),
    storage: str = typer.Option(".secrets/naga_state.json", help="Playwright storage state path."),
    db: str = typer.Option("out/collector.sqlite", help="Collector SQLite path."),
    raw_dir: str = typer.Option("out/raw", help="Raw JSON output directory."),
    sleep_sec: float = typer.Option(1.0, help="Request interval. Values below 1.0 are raised to 1.0."),
    limit: int | None = typer.Option(None, help="Maximum states to collect this run."),
    resume: bool = typer.Option(False, help="Resume pending/failed states from the collector DB."),
) -> None:
    try:
        counts = run_collect_dataset(
            samples=samples,
            storage=storage,
            db=db,
            raw_dir=raw_dir,
            sleep_sec=sleep_sec,
            limit=limit,
            resume=resume,
        )
    except CollectorStop as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from None
    except (FileNotFoundError, RuntimeError) as exc:
        raise _exit_with_user_error(exc) from None
    console.print(f"Collection finished: {counts}")


@app.command("build-dataset")
def build_dataset(
    db: str = typer.Option("out/collector.sqlite", help="Collector SQLite path."),
    out: str = typer.Option("out/dataset/base_predictions.csv", help="Base prediction CSV output."),
    branch_out: str | None = typer.Option(None, help="Branch prediction CSV output."),
) -> None:
    base_path, branch_path = build_dataset_from_collector(db=db, out=out, branch_out=branch_out)
    console.print(f"Saved base dataset: {base_path}")
    console.print(f"Saved branch dataset: {branch_path}")


@app.command("train-model")
def train_model(
    dataset: str = typer.Option("out/dataset/base_predictions.csv", help="Training dataset CSV."),
    model: str = typer.Option("histgb", help="Model: histgb/rf/ridge/lightgbm."),
    out: str = typer.Option("artifacts/models", help="Model output directory."),
) -> None:
    try:
        trained = run_train_model(dataset=dataset, model_name=model, out=out)
    except Exception as exc:
        raise _exit_with_user_error(exc) from None
    console.print(f"Saved model: {Path(out) / 'model.pkl'}")
    console.print(f"Saved feature columns: {Path(out) / 'feature_columns.json'}")
    console.print(f"Model: {trained.model_name} | features: {len(trained.feature_columns)}")


@app.command("evaluate-model")
def evaluate_model(
    dataset: str = typer.Option("out/dataset/base_predictions.csv", help="Dataset CSV."),
    model: str = typer.Option("artifacts/models/model.pkl", help="Trained model pickle."),
    out: str = typer.Option("out/eval", help="Evaluation output directory."),
    split: str = typer.Option("random", help="Split: random/kyoku_holdout/south_round_holdout."),
) -> None:
    try:
        metrics_path, errors_path = run_evaluate_model(dataset=dataset, model=model, out=out, split=split)
    except Exception as exc:
        raise _exit_with_user_error(exc) from None
    console.print(f"Saved metrics: {metrics_path}")
    console.print(f"Saved errors: {errors_path}")


@app.command("plot-model")
def plot_model(
    dataset: str = typer.Option("out/dataset/base_predictions.csv", help="Dataset CSV."),
    pred: str = typer.Option("out/eval/errors.csv", help="Prediction/error CSV from evaluate-model."),
    out: str = typer.Option("out/plots", help="Plot output directory."),
) -> None:
    try:
        output_dir = build_plots(dataset=dataset, pred=pred, out=out)
    except Exception as exc:
        raise _exit_with_user_error(exc) from None
    console.print(f"Saved plots under: {output_dir}")


@app.command()
def ui(
    port: int = typer.Option(8501, help="Streamlit port."),
    address: str = typer.Option("127.0.0.1", help="Streamlit bind address."),
) -> None:
    ui_path = Path(__file__).with_name("ui_streamlit.py")
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(ui_path),
        "--server.port",
        str(int(port)),
        "--server.address",
        address,
    ]
    console.print(f"Starting Streamlit UI: {ui_path}")
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise typer.Exit(code=completed.returncode)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
