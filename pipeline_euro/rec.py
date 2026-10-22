import sys, paths
import pandas as pd, numpy as np, json, dc, math
df=pd.read_pickle(str(paths.WORK / "df.pkl")); y=np.where(df.hg>df.ag,0,np.where(df.hg==df.ag,1,2))
b=pd.read_pickle(str(paths.WORK / "bt_dc_365.0_0.0003_3.0.pkl")).set_index("idx").sort_index()
idx=b.index.values; Pel=np.load(str(paths.WORK / "pel_bt.npy")); w=0.2
sel=df.comp.values[idx]; keep=np.isin(sel,["UEL","UECL"])
EV={"H":lambda i,j:i>j,"D":lambda i,j:i==j,"A":lambda i,j:i<j,"1X":lambda i,j:i>=j,"X2":lambda i,j:i<=j,"12":lambda i,j:i!=j,
    "EH+2H":lambda i,j:i+2>j,"EH+2A":lambda i,j:j+2>i,"EH-1H":lambda i,j:i-j>=2,"EH-1A":lambda i,j:j-i>=2,
    "G>1.5":lambda i,j:i+j>=2,"G<1.5":lambda i,j:i+j<=1,"G>2.5":lambda i,j:i+j>=3,"G<2.5":lambda i,j:i+j<=2,"G>3.5":lambda i,j:i+j>=4,"G<3.5":lambda i,j:i+j<=3,
    "BTTS":lambda i,j:i>0 and j>0,"NoBTTS":lambda i,j:not(i>0 and j>0)}
FAM={"H":"result","D":"result","A":"result","1X":"dc","X2":"dc","12":"dc","EH+2H":"eh","EH+2A":"eh","EH-1H":"eh","EH-1A":"eh","BTTS":"btts","NoBTTS":"btts"}
i=np.arange(11); I,J=np.meshgrid(i,i,indexing="ij")
masks={k:np.vectorize(f)(I,J) for k,f in EV.items()}
rec={}; P3=[]; Y3=[]
for n,(ix,row) in enumerate(b.iterrows()):
    if not keep[n]: continue
    pe=Pel[n]; pdc=np.array([row.pH,row.pD,row.pA]); pb=w*pe+(1-w)*pdc
    _,_,_,M,_=dc.probs(row.lh,row.la,rho=-0.05); M=dc.reshape(M, pb)
    hg,ag=int(df.hg[ix]),int(df.ag[ix])
    P3.append(pb); Y3.append(y[ix])
    for k,mk in masks.items():
        p=float(M[mk].sum()); won=bool(EV[k](hg,ag)); fam=FAM.get(k,"goals")
        bb=min(int(p*20),19)/20; rec.setdefault(fam,{}).setdefault(bb,[0,0]); rec[fam][bb][0]+=1; rec[fam][bb][1]+=won
    # draw no bet: chance among non-draws
    for side,kk in ((0,"H"),(2,"A")):
        if hg==ag: continue
        q=pb[side]/(pb[0]+pb[2]); bb=min(int(q*20),19)/20; won=(hg>ag) if side==0 else (ag>hg)
        rec.setdefault("dnb",{}).setdefault(bb,[0,0]); rec["dnb"][bb][0]+=1; rec["dnb"][bb][1]+=won
def wilson_lo(k,n,z=1.645):
    if n==0: return float("nan")
    p=k/n; d=1+z*z/n; c=p+z*z/(2*n); s=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)); return (c-s)/d
record={f:[[bb,v[0],v[1]] for bb,v in sorted(d.items())] for f,d in rec.items()}
safety={f:[[bb,v[0],v[1],round(wilson_lo(v[1],v[0]),4)] for bb,v in sorted(d.items()) if v[0]>=20] for f,d in rec.items()}
P3=np.array(P3); Y3=np.array(Y3)
ll=float(-np.log(np.clip(P3[np.arange(len(Y3)),Y3],1e-9,1)).mean())
# base: always the usual split from European matches before the test window
tr=df[(df.main==1)&(df.date<"2023-07-01")]; yt=np.where(tr.hg>tr.ag,0,np.where(tr.hg==tr.ag,1,2)); fr=np.bincount(yt,minlength=3)/len(yt)
base=float(-np.log(fr[Y3]).mean()); fav=float((P3.argmax(1)==Y3).mean())
dates=df.date.values[idx][keep]
test=dict(n=int(len(Y3)),span=str(dates.min())[:7].replace("-","/")+" to "+str(dates.max())[:7].replace("-","/"),ll=round(ll,4),base=round(base,4),fav=round(fav,4))
print(test); print({f:len(v) for f,v in safety.items()})
json.dump(dict(record=record,safety=safety,test=test),open(str(paths.OUT / "eurrec.json"),"w"))
