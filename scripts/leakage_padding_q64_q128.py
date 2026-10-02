import sys, os, numpy as np, pandas as pd
sys.path.insert(0,'.')
from multiprocessing import Pool
from flora.energy import CryptoCost
from flora.sim import run_day
from flora.traffic import generate, link_trace
from flora import policies as P
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
POL={"FLOOR-E":lambda:P.Floor("FLOOR-E"),"FLOOR-L(q16)":lambda:P.Floor("q16",leakage_aware=True,pad="q16"),
     "FLOOR-L(q64)":lambda:P.Floor("q64",leakage_aware=True,pad="q64"),"FLOOR-L(q128)":lambda:P.Floor("q128",leakage_aware=True,pad="q128"),
     "FLOOR-L(pow2)":lambda:P.Floor("pow2",leakage_aware=True,pad="pow2")}
C=None
def job(day):
    global C
    C=C or CryptoCost()
    seed=2026+10000+day; rng=np.random.default_rng(seed)
    recs,tr,b=generate(rng),link_trace(rng,"home"),rng.uniform(10,100)
    sub=np.random.default_rng(seed+1); out={}
    for n,mk in POL.items():
        _,fr=run_day(mk(),"home",seed,C,recs=recs,trace=tr,battery=b,log_frames=True)
        f=pd.DataFrame(fr,columns=["t","len","has_V","has_R","c","a"]); f["day"]=day
        out[n]=f[(f.has_V==1)|(sub.random(len(f))<0.03)][["t","len","has_V","day"]]
    return out
def oof(X,y,g):
    s=np.zeros(len(y))
    for a,b in GroupKFold(5).split(X,y,g):
        m=HistGradientBoostingClassifier(max_iter=300,learning_rate=0.05,max_leaf_nodes=8,min_samples_leaf=100,l2_regularization=1.0,early_stopping=True,validation_fraction=0.2,n_iter_no_change=20,random_state=2026).fit(X[a],y[a]); s[b]=m.predict_proba(X[b])[:,1]
    return s
if __name__=="__main__":
    with Pool(2) as p: parts=p.map(job,range(60))
    for n in POL:
        d=pd.concat([x[n] for x in parts]); y=d.has_V.to_numpy(int); g=d.day.to_numpy()
        H=np.c_[np.sin(2*np.pi*d.t/86400),np.cos(2*np.pi*d.t/86400)]
        a=oof(H,y,g); b=oof(np.c_[H,d.len],y,g); c=oof(d[["len"]].to_numpy(float),y,g)
        rng=np.random.default_rng(0); days=np.unique(g); idx={k:np.where(g==k)[0] for k in days}; D=[]
        for _ in range(500):
            ii=np.concatenate([idx[k] for k in rng.choice(days,len(days))]); D.append(roc_auc_score(y[ii],b[ii])-roc_auc_score(y[ii],a[ii]))
        print(n,"len-only",round(roc_auc_score(y,c),3),"hour",round(roc_auc_score(y,a),3),"hour+len",round(roc_auc_score(y,b),3),"gain",round(roc_auc_score(y,b)-roc_auc_score(y,a),3),np.quantile(D,[.025,.975]).round(3),flush=True)
