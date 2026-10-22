import sys, json, math, warnings, paths; warnings.filterwarnings("ignore")
import pandas as pd, numpy as np, collections
import elo, link, dc, names, euro2627
cfg=json.load(open(str(paths.HERE / "final_cfg.json")))
df=pd.read_pickle(str(paths.WORK / "df.pkl")); y=np.where(df.hg>df.ag,0,np.where(df.hg==df.ag,1,2))
ep=json.load(open(str(paths.HERE / "elo_params.json")))
pre,RT,_,N=elo.run_elo(df,K0=ep["K0"],HE=ep["HE"],newK=ep["newK"],HD=ep["HD"],gap_reg=0.0)
mm=(df.main==1).values
lp=link.ol_fit(pre[mm],y[mm])
M=dc.fit_dc(df,paths.RUN_ISO,half=cfg["half"],alpha=cfg["alpha"],cscale=cfg["cs"])
raw=pd.read_pickle(str(paths.WORK / "raw.pkl")); raw=raw[raw.date<=paths.CUTOFF].copy()
for c in ("hcc","acc"): raw[c]=raw[c].replace({"MCO":"FRA"})
R=names.resolve(raw)
rec=df[df.date>="2025-07-01"]; rc=collections.Counter(list(rec.H)+list(rec.A))
w=cfg["w"]; rho=cfg.get("rho",-0.05)
EV={"H":lambda i,j:i>j,"D":lambda i,j:i==j,"A":lambda i,j:i<j,"1X":lambda i,j:i>=j,"X2":lambda i,j:i<=j,"12":lambda i,j:i!=j,
    "EH+2H":lambda i,j:i+2>j,"EH+2A":lambda i,j:j+2>i,"EH-1H":lambda i,j:i-j>=2,"EH-1A":lambda i,j:j-i>=2,
    "G>1.5":lambda i,j:i+j>=2,"G<1.5":lambda i,j:i+j<=1,"G>2.5":lambda i,j:i+j>=3,"G<2.5":lambda i,j:i+j<=2,"G>3.5":lambda i,j:i+j>=4,"G<3.5":lambda i,j:i+j<=3,
    "BTTS":lambda i,j:i>0 and j>0,"NoBTTS":lambda i,j:not(i>0 and j>0)}
FAM={"H":"result","D":"result","A":"result","1X":"dc","X2":"dc","12":"dc","EH+2H":"eh","EH+2A":"eh","EH-1H":"eh","EH-1A":"eh","BTTS":"btts","NoBTTS":"btts"}
def label(k,h,a):
    return {"H":h+" win","D":"Draw","A":a+" win","1X":h+" or draw","X2":"Draw or "+a,"12":h+" or "+a,"EH+2H":h+" +2 handicap","EH+2A":a+" +2 handicap",
            "EH-1H":h+" to win by 2 or more","EH-1A":a+" to win by 2 or more","G>1.5":"2 or more goals","G<1.5":"1 goal or fewer","G>2.5":"3 or more goals","G<2.5":"2 goals or fewer",
            "G>3.5":"4 or more goals","G<3.5":"3 goals or fewer","BTTS":"Both teams score","NoBTTS":"Not both teams score"}[k]
def forecast(hk,ak):
    d=RT.get(hk,1350)-RT.get(ak,1350)+ep["HE"]
    pe=link.ol_pred(lp,np.array([d]))[0]
    lh,la=dc.lam(M,hk,ak,eur=True)
    pd_,o25,btts,Mx,_=dc.probs(lh,la,rho=rho)
    pb=w*pe+(1-w)*pd_
    # reshape the score grid so its home/draw/away totals match the blend
    i=np.arange(Mx.shape[0]); I,J=np.meshgrid(i,i,indexing="ij")
    Mx=Mx.copy(); Mx[I>J]*=pb[0]/pd_[0]; Mx[I==J]*=pb[1]/pd_[1]; Mx[I<J]*=pb[2]/pd_[2]; Mx/=Mx.sum()
    return pe,pd_,pb,Mx,lh,la
out={"uel":[],"uecl":[]}; pairs={}; hist=[]
NAMES={"Ararat-Armenia":"Ararat-Armenia","Union Saint-Gilloise":"Union SG","Hapoel Beer Sheva":"Hapoel Be'er Sheva","Viktoria Plzen":"Viktoria Plzeň","Lillestrom":"Lillestrøm","Lech Poznan":"Lech Poznań",
       "Ferencvaros":"Ferencváros","Besiktas":"Beşiktaş","Mjallby":"Mjällby","Nordsjaelland":"Nordsjælland","Kauno Zalgiris":"Kauno Žalgiris","Inter Club d'Escaldes":"Inter Escaldes","Universitatea Craiova":"U Craiova",
       "Crvena Zvezda":"Crvena Zvezda","FC Copenhagen":"Copenhagen","Iberia 1999":"Iberia 1999","Jagiellonia":"Jagiellonia"}
# Fixtures cross-checked against Wikipedia (fixtures.py, written by prepare.py).
FIX = json.load(open(str(paths.WORK / "fixtures.json")))
for f in FIX:
    hk=R(f["home"],f["hcc"]); ak=R(f["away"],f["acc"])
    h=NAMES.get(f["home"],f["home"]); a=NAMES.get(f["away"],f["away"])
    pe,pdc,pb,Mx,lh,la=forecast(hk,ak)
    i=np.arange(Mx.shape[0]); I,J=np.meshgrid(i,i,indexing="ij")
    ev={k:float(Mx[np.vectorize(fn)(I,J)].sum()) for k,fn in EV.items()}
    k=np.unravel_index(Mx.argmax(),Mx.shape)
    comp=f["comp"].lower(); lgname="Europa League" if comp=="uel" else "Conference League"
    mid=("UEL" if comp=="uel" else "UECL")+"_2627_"+names.norm(f["home"]).replace(" ","_")+"_"+names.norm(f["away"]).replace(" ","_")+"_2026-10-22"
    eo=[nm for nm,kk in ((h,hk),(a,ak)) if rc[kk]<15]
    xs=(lh*1.0,la*1.0)
    # expected goals consistent with reshaped grid
    xg=(float((Mx*I).sum()),float((Mx*J).sum()))
    out[comp].append(dict(id=mid,lg=lgname,h=h,a=a,kickoff=f["kickoff"],round=f["round"],locked=True,p=[int(round(v*1000)) for v in pb],
        xg=[round(xg[0],2),round(xg[1],2)],goals=round(xg[0]+xg[1],2),o25=round(ev["G>2.5"],4),btts=round(ev["BTTS"],4),score=f"{k[0]}-{k[1]}",score_p=round(float(Mx[k]),4),verified=bool(f.get("verified")),time_confirmed=bool(f.get("time_confirmed",True)),sources=f.get("sources",[]),
        methods=dict(elo=[round(float(v),3) for v in pe],dc=[round(float(v),3) for v in pdc]),eo=eo))
    picks=[]
    for kk in ["H","D","A","1X","X2","12","EH+2H","EH+2A","EH-1H","EH-1A","G>1.5","G<1.5","G>2.5","G<2.5","G>3.5","G<3.5","BTTS","NoBTTS"]:
        picks.append(dict(k=kk,fam=FAM.get(kk,"goals"),label=label(kk,h,a),p=round(ev[kk],5),g=comp))
    picks.append(dict(k="DNB-H",fam="dnb",label="Draw no bet: "+h,p=round(ev["H"],5),refund=round(ev["D"],6),nopair=True,g=comp))
    picks.append(dict(k="DNB-A",fam="dnb",label="Draw no bet: "+a,p=round(ev["A"],5),refund=round(ev["D"],6),nopair=True,g=comp))
    joint={}
    for x in range(len(picks)):
        for z in range(x+1,len(picks)):
            if picks[x].get("nopair") or picks[z].get("nopair"): continue
            fx=EV[picks[x]["k"]]; fz=EV[picks[z]["k"]]
            jp=float(Mx[np.vectorize(lambda u,v: fx(u,v) and fz(u,v))(I,J)].sum())
            if 0.0005<jp<min(picks[x]["p"],picks[z]["p"])-0.0005 or True:
                if jp>0.0005: joint[f"{x},{z}"]=round(jp,5)
    pairs[mid]=dict(picks=picks,joint=joint,h=h,a=a,lg=lgname,kickoff=f["kickoff"],locked=True,odds={},g=comp)
    # history calls: result, goals 2.5, both score
    res_k=max(["H","D","A"],key=lambda q:ev[q])
    calls=[dict(mkt="result",k=res_k,label=label(res_k,h,a),p=round(ev[res_k],4),result=None)]
    gk="G>2.5" if ev["G>2.5"]>=ev["G<2.5"] else "G<2.5"; calls.append(dict(mkt="goals",k=gk,label="Over 2.5 goals" if gk=="G>2.5" else "Under 2.5 goals",p=round(ev[gk],4),result=None))
    bk="BTTS" if ev["BTTS"]>=ev["NoBTTS"] else "NoBTTS"; calls.append(dict(mkt="btts",k=bk,label="Both score: yes" if bk=="BTTS" else "Both score: no",p=round(ev[bk],4),result=None))
    hist.append(dict(match_id=mid,lg=lgname,h=h,a=a,kickoff=f["kickoff"],round=f["round"],locked_at="2026-10-22T12:00Z",model_version="eur-1",calls=calls,score=None,settled_utc=None))
json.dump(dict(out=out,pairs=pairs,hist=hist),open(str(paths.OUT / "pred.json"),"w"),indent=0)
for comp in out:
    for r in out[comp]: print(f"{r['h']:22s} {r['a']:22s} {r['p']} xg={r['xg']} o25={r['o25']:.2f} {r['score']} elo={r['methods']['elo']} dc={r['methods']['dc']} eo={r['eo']}")
