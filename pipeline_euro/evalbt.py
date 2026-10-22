import sys, paths
import pandas as pd, numpy as np, json, elo, link
df=pd.read_pickle(str(paths.WORK / "df.pkl")); y=np.where(df.hg>df.ag,0,np.where(df.hg==df.ag,1,2))
ep=json.load(open(str(paths.HERE / "elo_params.json")))
pre,_,_,_=elo.run_elo(df,K0=ep["K0"],HE=ep["HE"],newK=ep["newK"],HD=ep["HD"],gap_reg=0.0)
tr=((df.main==1)&(df.date<"2023-07-01")).values
lp=link.ol_fit(pre[tr],y[tr])
for f in ["bt_dc_365.0_0.0001_3.0.pkl","bt_dc_240.0_0.0001_3.0.pkl","bt_dc_365.0_0.0003_3.0.pkl"]:
    b=pd.read_pickle(str(paths.WORK / f)).set_index("idx").sort_index()
    idx=b.index.values; yy=y[idx]; dates=df.date.values[idx]
    Pdc=b[["pH","pD","pA"]].values; Pel=link.ol_pred(lp,pre[idx])
    tune=dates<"2025-07-01"; ho=~tune
    print(f, "DC tune",link.metrics(Pdc[tune],yy[tune]),"hold",link.metrics(Pdc[ho],yy[ho]))
    print("   ELO tune",link.metrics(Pel[tune],yy[tune]),"hold",link.metrics(Pel[ho],yy[ho]))
    for w in [0.2,0.35,0.5,0.65]:
        P=w*Pel+(1-w)*Pdc; print("   w",w,"tune",link.metrics(P[tune],yy[tune])["ll"],"hold",link.metrics(P[ho],yy[ho])["ll"], "all",link.metrics(P,yy))
    tot=(df.hg+df.ag).values[idx]; o=b.o25.values
    print("   o25 mean pred",o.mean().round(3),"actual",(tot>=3).mean().round(3), "ll", -np.mean(np.log(np.where(tot>=3,o,1-o))).round(4), "base", -np.mean(np.log(np.where(tot>=3,(tot>=3).mean(),1-(tot>=3).mean()))).round(4))
    np.save(str(paths.WORK / "pel_bt.npy"),Pel); np.save(str(paths.WORK / "idx_bt.npy"),idx)
