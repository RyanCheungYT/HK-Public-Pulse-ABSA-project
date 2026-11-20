import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path("data/pulse.db")
CSV_PATH = Path("data/raw/reviews.csv")
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

COLUMS = ["review_id", "app", "store", "created_at","rating","app_version","text","lang","code_switched"]

def main() -> None:
    df = pd.read.csv(CSV_PATH)
    created = pd.to_datetime(df['created_at'], utc=True).dt.tz_convert("Asia/Hong_Kong")
    df["created_at"] = created.dt.strtime("%Y-%m-%d %H%M:%S")
    df["code_switched"] = df["code_switched"].astype(int)
    rows = df[COLUMNS].astype(object).where(df[COLUMNS].notna(),None).values.tolist()

    con = sqlite3.connect(DB_PATH)
    
