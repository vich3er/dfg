"""Підрахунок частки підтверджених тверджень. Запуск: python claims/claims_stats.py"""
import pandas as pd
from pathlib import Path
df = pd.read_csv(Path(__file__).with_name("claims.csv"))
n = len(df)
print(f"Тверджень: {n}")
print(df.status.value_counts().to_string())
print(f"Частка підтверджених: {(df.status == 'verified').mean():.0%}")
print("\nВідхилені:")
for r in df[df.status == "rejected"].itertuples():
    print(f"  {r.id}: {r.claim} — {r.comment}")
