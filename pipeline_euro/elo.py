import numpy as np, pandas as pd, math, collections
def run_elo(df, K0=20.0, HD=60.0, HE=45.0, newK=3.0, gap_reg=0.25, seed=None, stop_date=None, snapshot_dates=(), init_fn=None):
    """Goal-difference Elo. Returns pre-match diff (home - away + hfa) for every row, and rating snapshots."""
    R={}; N=collections.Counter(); last={}
    ccsum=collections.defaultdict(list)
    pre=np.zeros(len(df)); snaps={}
    sd=sorted(snapshot_dates); si=0
    def init(team, cc, elo_hint, date=None):
        if elo_hint is not None and not (isinstance(elo_hint,float) and math.isnan(elo_hint)): return float(elo_hint)
        if init_fn is not None:
            v = init_fn(team, cc, R, N, date)
            if v is not None: return float(v)
        # country mean of established teams minus 75, else 1350
        vals=[R[t] for t in R if t.startswith(cc+":") and N[t]>=10]
        return (np.mean(vals)-75.0) if len(vals)>=3 else 1350.0
    for i,r in enumerate(df.itertuples(index=False)):
        while si<len(sd) and r.date>sd[si]:
            snaps[sd[si]]=dict(R); si+=1
        h,a=r.H,r.A
        for tm,cc,hint in ((h,r.hcc,getattr(r,"helo",None)),(a,r.acc,getattr(r,"aelo",None))):
            if tm not in R: R[tm]=init(tm,cc,hint,r.date)
            elif tm in last and (r.t-last[tm]).days>100:
                vals=[R[t] for t in R if t.startswith(cc+":") and N[t]>=10]
                if len(vals)>=3: R[tm]=R[tm]*(1-gap_reg)+np.mean(vals)*gap_reg
        hfa=HE if r.eur else HD
        d=R[h]-R[a]+hfa; pre[i]=d
        e=1/(1+10**(-d/400)); s=1.0 if r.hg>r.ag else 0.5 if r.hg==r.ag else 0.0
        gd=abs(r.hg-r.ag); mov=1.0 if gd<=1 else 1.5 if gd==2 else (11+gd)/8
        kh=K0*(1+newK/(1+N[h]/8)); ka=K0*(1+newK/(1+N[a]/8))
        if r.eur: kh*=1.25; ka*=1.25
        R[h]+=kh*mov*(s-e); R[a]-=ka*mov*(s-e)
        N[h]+=1; N[a]+=1; last[h]=r.t; last[a]=r.t
    while si<len(sd): snaps[sd[si]]=dict(R); si+=1
    return pre, R, snaps, N
