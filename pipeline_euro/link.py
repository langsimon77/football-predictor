import numpy as np
from scipy.optimize import minimize
def ol_fit(x,y):
    # ordered logit: P(away)=σ(c1 - b x), P(away or draw)=σ(c2 - b x)
    def nll(p):
        b,c1,lc=p; c2=c1+np.exp(lc)
        pa=1/(1+np.exp(-(c1-b*x))); pad=1/(1+np.exp(-(c2-b*x)))
        P=np.stack([1-pad,pad-pa,pa],1); P=np.clip(P,1e-9,1)
        return -np.log(P[np.arange(len(y)),y]).sum()
    r=minimize(nll,[0.005,-0.5,0.0],method="Nelder-Mead",options=dict(maxiter=4000,xatol=1e-7,fatol=1e-7))
    return r.x
def ol_pred(p,x):
    b,c1,lc=p; c2=c1+np.exp(lc)
    pa=1/(1+np.exp(-(c1-b*x))); pad=1/(1+np.exp(-(c2-b*x)))
    return np.stack([1-pad,pad-pa,pa],1)
def metrics(P,y):
    P=np.clip(P,1e-9,1); ll=-np.log(P[np.arange(len(y)),y]).mean()
    Y=np.zeros_like(P); Y[np.arange(len(y)),y]=1
    br=((P-Y)**2).sum(1).mean()
    cp=np.cumsum(P,1)[:,:2]; cy=np.cumsum(Y,1)[:,:2]; rps=((cp-cy)**2).sum(1).mean()/2
    return dict(ll=round(ll,4),rps=round(rps,4),brier=round(br,4),n=len(y))
