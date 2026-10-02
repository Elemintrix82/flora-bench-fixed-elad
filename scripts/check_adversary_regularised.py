import pandas as pd, numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import SplineTransformer, StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
d=pd.read_csv('reference_results/04_leakage_oof.csv')
def oof(make, X, y, g):
    s=np.zeros(len(y))
    for tr,te in GroupKFold(5).split(X,y,g):
        m=make().fit(X[tr],y[tr]); s[te]=m.predict_proba(X[te])[:,1]
    return s
def boot(y,a,b,g,n=500):
    rng=np.random.default_rng(0); days=np.unique(g); idx={k:np.where(g==k)[0] for k in days}; D=[]
    for _ in range(n):
        ii=np.concatenate([idx[k] for k in rng.choice(days,len(days))]); D.append(roc_auc_score(y[ii],b[ii])-roc_auc_score(y[ii],a[ii]))
    return np.quantile(D,[.025,.975]).round(3)
models={
 'hgb_default': lambda: HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, random_state=2026),
 'hgb_reg': lambda: HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=8, min_samples_leaf=100, l2_regularization=1.0, early_stopping=True, validation_fraction=0.2, n_iter_no_change=20, random_state=2026),
 'hgb_balanced': lambda: HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=8, min_samples_leaf=50, class_weight='balanced', early_stopping=True, random_state=2026),
 'logit_spline': lambda: make_pipeline(SplineTransformer(n_knots=12, degree=3), LogisticRegression(C=1.0, max_iter=2000)),
}
for pol in ['FLOOR-E','FLOOR-L(q16)','FLOOR-L(pow2)','Static-Ascon']:
    x=d[d.policy==pol]; y=x.has_V.to_numpy(int); g=x.day.to_numpy()
    tod=(x.t.to_numpy()%86400)/3600.0
    H=np.c_[np.sin(2*np.pi*tod/24),np.cos(2*np.pi*tod/24)]
    L=x.len.to_numpy(float)
    for name,mk in models.items():
        if name=='logit_spline':
            Xh=tod[:,None]; Xhl=np.c_[tod, np.log(L)]
        else:
            Xh=H; Xhl=np.c_[H,L]
        a=oof(mk,Xh,y,g); b=oof(mk,Xhl,y,g)
        print(pol,name,'hour',round(roc_auc_score(y,a),3),'hour+len',round(roc_auc_score(y,b),3),'gain',round(roc_auc_score(y,b)-roc_auc_score(y,a),3),boot(y,a,b,g),flush=True)
