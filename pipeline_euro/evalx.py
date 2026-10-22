import sys, paths
import pandas as pd, numpy as np, json, dc, link, math
df=pd.read_pickle(str(paths.WORK / "df.pkl")); y=np.where(df.hg>df.ag,0,np.where(df.hg==df.ag,1,2))
b=pd.read_pickle(str(paths.WORK / "bt_dc_365.0_0.0003_3.0.pkl")).set_index("idx").sort_index()
idx=b.index.values; Pel=np.load(str(paths.WORK / "pel_bt.npy")); assert (np.load(str(paths.WORK / "idx_bt.npy"))==idx).all()
Pdc=b[["pH","pD","pA"]].values; yy=y[idx]
# thin-data flag at prediction time: fewer than 15 matches in previous 365 days for either team
t=df.t.values; H=df.H.values; A=df.A.values
from collections import defaultdict
pos=defaultdict(list)
for i in range(len(df)): pos[H[i]].append(t[i]); pos[A[i]].append(t[i])
for k in pos: pos[k]=np.array(pos[k])
def cnt(team,T): a=pos[team]; return ((a<T)&(a>=T-np.timedelta64(365,'D'))).sum()
thin=np.array([min(cnt(H[i],t[i]),cnt(A[i],t[i]))<15 for i in idx])
for w in (0.0,0.2):
    P=w*Pel+(1-w)*Pdc
    print("w",w,"thin",link.metrics(P[thin],yy[thin]),"thick",link.metrics(P[~thin],yy[~thin]))
w=np.where(thin,0.0,0.2)[:,None]; P=w*Pel+(1-w)*Pdc
print("mixed",link.metrics(P,yy)); P2=0.2*Pel+0.8*Pdc; print("flat",link.metrics(P2,yy))
json.dump(dict(thin_n=int(thin.sum())),open(str(paths.OUT / "thin.json"),"w"))
np.save(str(paths.WORK / "thin_bt.npy"),thin)
