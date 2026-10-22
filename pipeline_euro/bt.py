import sys, paths
import pandas as pd, numpy as np, dc, json, warnings, time
warnings.filterwarnings("ignore")
df=pd.read_pickle(str(paths.WORK / "df.pkl"))
half=float(sys.argv[1]); alpha=float(sys.argv[2]); cs=float(sys.argv[3])
ev=df[(df.main==1)&(df.date>="2023-07-01")].copy()
ev["month"]=ev.date.str[:7]
out=[]
t0=time.time()
for mo,g in ev.groupby("month"):
    T=g.date.min()
    m=dc.fit_dc(df,T,half=half,alpha=alpha,cscale=cs)
    for r in g.itertuples():
        lh,la=dc.lam(m,r.H,r.A,eur=True)
        p,o25,btts,_,_=dc.probs(lh,la)
        out.append(dict(idx=r.Index,pH=p[0],pD=p[1],pA=p[2],o25=o25,lh=lh,la=la))
pd.DataFrame(out).to_pickle(str(paths.WORK / f"bt_dc_{half}_{alpha}_{cs}.pkl")); print("done",time.time()-t0)
