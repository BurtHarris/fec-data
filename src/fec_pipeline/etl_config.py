"""Load suite-level ETL metadata from the dbt schema YAML."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


DEFAULT_ETL_CONFIG_PATH = Path("models") / "raw_fec" / "schema.yml"


@dataclass(frozen=True)
class EtlModelConfig:
    """Configuration metadata for one ETL model target."""

    name: str
    source_entry: str
    zip_columns: tuple[str, ...]


def repo_root() -> Path:
    """Return the repository root from this module location."""

    return Path(__file__).resolve().parents[2]


def normalize_str_list(raw_value: Any, context: str) -> tuple[str, ...]:
    """Normalize a YAML list of strings."""

    if raw_value is None:
        return ()
    if not isinstance(raw_value, list):
        raise SystemExit(f"{context} must be a list of strings")

    values: list[str] = []
    for value in raw_value:
        if not isinstance(value, str):
            raise SystemExit(f"{context} entries must be strings")
        cleaned = value.strip()
        if cleaned:
            values.append(cleaned)

    return tuple(values)


def resolve_source_entry(meta: dict[str, Any], model_name: str, cycle_suffix: str | None) -> str:
    """Resolve the source ZIP entry name for one model."""

    source_entry = meta.get("source_entry")
    source_entry_template = meta.get("source_entry_template")

    if source_entry_template is not None:
        if not isinstance(source_entry_template, str):
            raise SystemExit(f"meta.source_entry_template for {model_name} must be a string")
        if cycle_suffix is None:
            raise SystemExit(f"meta.source_entry_template for {model_name} requires a cycle suffix")
        return source_entry_template.replace("{{cycle_suffix}}", cycle_suffix)

    if not isinstance(source_entry, str):
        raise SystemExit(f"meta.source_entry for {model_name} must be a string")

    return source_entry.strip()


def load_etl_model_config(config_path: Path, cycle_suffix: str | None = None) -> list[EtlModelConfig]:
    """Read ETL model metadata from the suite YAML config."""

    if not config_path.exists():
        raise SystemExit(f"ETL config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}

    if not isinstance(loaded, dict):
        raise SystemExit(f"ETL config must be a mapping: {config_path}")

    models = loaded.get("models")
    if not isinstance(models, list):
        raise SystemExit(f"ETL config must define a models list: {config_path}")

    configs: list[EtlModelConfig] = []
    for model in models:
        if not isinstance(model, dict):
            raise SystemExit(f"Each ETL model entry must be a mapping: {config_path}")

        name = model.get("name")
        if not isinstance(name, str) or not name.strip():
            raise SystemExit(f"Each ETL model entry must define a name: {config_path}")

        meta = model.get("meta") or {}
        if not isinstance(meta, dict):
            raise SystemExit(f"meta for {name} must be a mapping")

        source_entry = resolve_source_entry(meta, name, cycle_suffix)
        zip_columns = normalize_str_list(meta.get("zip_columns"), f"meta.zip_columns for {name}")
        configs.append(EtlModelConfig(name=name, source_entry=source_entry, zip_columns=zip_columns))

    return configs


def main() -> None:
    """Emit the ETL model config as JSON."""

    parser = argparse.ArgumentParser(description="Read suite ETL model config.")
    parser.add_argument("--config", default=str(DEFAULT_ETL_CONFIG_PATH), help="Path to suite YAML config")
    parser.add_argument("--cycle-suffix", help="Two-digit cycle suffix used by cycle-specific filenames.")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = repo_root() / config_path

    configs = load_etl_model_config(config_path, args.cycle_suffix)
    print(json.dumps([asdict(config) for config in configs], indent=2))


if __name__ == "__main__":
    main()