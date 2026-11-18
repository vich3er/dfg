"""Спільні шляхи та підключення до DuckDB."""
from pathlib import Path
import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "warehouse.duckdb"
DATA_DIR = ROOT / "data"


def connect(read_only: bool = True):
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def parquet(name: str) -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / f"{name}.parquet")
