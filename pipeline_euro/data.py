import paths
import pandas as pd, numpy as np, names
def load():
    df=pd.read_pickle(str(paths.WORK / "raw.pkl")); df=df[df.date<=paths.CUTOFF].copy()
    for c in ("hcc","acc"): df[c]=df[c].replace({"MCO":"FRA"})
    R=names.resolve(df)
    df["H"]=[R(n,c) for n,c in zip(df.home,df.hcc)]; df["A"]=[R(n,c) for n,c in zip(df.away,df.acc)]
    df=df[df.H!=df.A].drop_duplicates(["date","H","A"]).sort_values(["date"]).reset_index(drop=True)
    df["eur"]=(~df.comp.isin(["DOM","DOM2"])).astype(int)
    df["main"]=df.comp.isin(["UCL","UEL","UECL"]).astype(int)
    df["t"]=pd.to_datetime(df.date)
    return df,R
