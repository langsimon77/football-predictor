import numpy as np, pandas as pd, scipy.sparse as sp
from sklearn.linear_model import PoissonRegressor
def fit_dc(df, T, half=365.0, alpha=1e-4, cscale=3.0, window_days=1100, dom2_w=0.5):
    """Poisson attack/defence with country effects (weakly penalised) + team deviations, time-decayed."""
    d=df[(df.date<T)].copy()
    age=(pd.Timestamp(T)-d.t).dt.days.values
    d=d[age<=window_days]; age=age[age<=window_days]
    w=np.power(0.5,age/half)*np.where(d.comp.values=="DOM2",dom2_w,1.0)
    teams=sorted(set(d.H)|set(d.A)); ti={t:i for i,t in enumerate(teams)}
    ccs=sorted(set(t.split(":")[0] for t in teams)); ci={c:i for i,c in enumerate(ccs)}
    nT,nC=len(teams),len(ccs)
    # columns: [att team nT][def team nT][att cc nC][def cc nC][home_dom, home_eur]
    n=len(d); rows=np.arange(2*n)
    H=np.array([ti[x] for x in d.H]); A=np.array([ti[x] for x in d.A])
    Hc=np.array([ci[x.split(":")[0]] for x in d.H]); Ac=np.array([ci[x.split(":")[0]] for x in d.A])
    att=np.r_[H,A]; de=np.r_[A,H]; attc=np.r_[Hc,Ac]; dec=np.r_[Ac,Hc]
    eur=d.eur.values; ishome=np.r_[np.ones(n),np.zeros(n)]
    hd=ishome*(1-np.r_[eur,eur]); he=ishome*np.r_[eur,eur]
    data=np.r_[np.ones(2*n),np.ones(2*n),np.full(2*n,cscale),np.full(2*n,cscale),hd*10,he*10]
    ri=np.r_[rows,rows,rows,rows,rows,rows]
    cj=np.r_[att, nT+de, 2*nT+attc, 2*nT+nC+dec, np.full(2*n,2*nT+2*nC), np.full(2*n,2*nT+2*nC+1)]
    X=sp.csr_matrix((data,(ri,cj)),shape=(2*n,2*nT+2*nC+2))
    yv=np.r_[d.hg.values,d.ag.values].astype(float); ww=np.r_[w,w]
    m=PoissonRegressor(alpha=alpha,max_iter=3000,tol=1e-7); m.fit(X,yv,sample_weight=ww/ww.mean())
    co=m.coef_
    model=dict(ti=ti,ci=ci,nT=nT,nC=nC,att=co[:nT],de=co[nT:2*nT],attc=co[2*nT:2*nT+nC]*cscale,dec=co[2*nT+nC:2*nT+2*nC]*cscale,hd=co[-2]*10,he=co[-1]*10,b0=m.intercept_)
    return model
def lam(model,h,a,eur=True,home=True):
    def parts(t):
        c=t.split(":")[0]
        ta=model["att"][model["ti"][t]] if t in model["ti"] else 0.0
        td=model["de"][model["ti"][t]] if t in model["ti"] else 0.0
        ca=model["attc"][model["ci"][c]] if c in model["ci"] else 0.0
        cd=model["dec"][model["ci"][c]] if c in model["ci"] else 0.0
        return ta+ca, td+cd
    ha,hdf=parts(h); aa,adf=parts(a)
    hfa=(model["he"] if eur else model["hd"]) if home else 0.0
    return np.exp(model["b0"]+ha+adf+hfa), np.exp(model["b0"]+aa+hdf)
def probs(lh,la,rho=-0.05,maxg=10):
    from scipy.stats import poisson
    i=np.arange(maxg+1); ph=poisson.pmf(i,lh); pa=poisson.pmf(i,la); M=np.outer(ph,pa)
    # Dixon-Coles low-score correction
    M[0,0]*=1-lh*la*rho; M[0,1]*=1+lh*rho; M[1,0]*=1+la*rho; M[1,1]*=1-rho
    M/=M.sum()
    pH=np.tril(M,-1).sum(); pD=np.trace(M); pA=np.triu(M,1).sum()
    tot=np.add.outer(i,i); o25=M[tot>=3].sum(); btts=M[1:,1:].sum()
    k=np.unravel_index(M.argmax(),M.shape)
    return np.array([pH,pD,pA]), o25, btts, M, k


def reshape(M, target):
    """Rescale a score grid so its home, draw and away totals equal target (a blend of models),
    keeping each region's shape; the grid still sums to 1."""
    i = np.arange(M.shape[0]); I, J = np.meshgrid(i, i, indexing="ij")
    M = M.copy(); cur = (M[I > J].sum(), np.trace(M), M[I < J].sum())
    M[I > J] *= target[0] / cur[0]; M[I == J] *= target[1] / cur[1]; M[I < J] *= target[2] / cur[2]
    return M / M.sum()
