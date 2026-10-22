"""Resolve club names across sources and write the match table the models read (df.pkl)."""
import paths
import data

df, _ = data.load()
df.to_pickle(str(paths.WORK / "df.pkl"))
print(len(df), "matches;", int(df.main.sum()), "in the three UEFA competitions; last", df.date.max())
