"""Read-only elastic-LP diagnosis. Never emits or accepts a relaxed dataset."""
import json
from collections import Counter,defaultdict
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import eye,hstack,vstack,csr_matrix
import select_candidates_round2 as s
import generate_candidates_round2 as g

def diagnose(c,integrality,bounds,constraints,options):
 A=constraints.A.tocsr();lb=np.array(constraints.lb);ub=np.array(constraints.ub);n=A.shape[1];m=A.shape[0]
 names=json.loads((g.RES/'selection_constraints.json').read_text())['constraint_names']
 soft=np.array([not name.startswith("('video'") and not name.startswith("('identity'") and not name.startswith("('duplicate'") for name in names])
 weight=np.array([100. if name.startswith(('operation ','dataset ','event references','position references','numeric ','O7 premise','ordinary never','O8 same','identity challenge','confusion')) else 1. for name in names])
 sl=eye(m,format='csr');zero=csr_matrix((m,m));upper=np.isfinite(ub);lower=np.isfinite(lb)
 mat=vstack([hstack([A[upper],zero[upper],-sl[upper]]),hstack([-A[lower],-sl[lower],zero[lower]])],format='csr');rhs=np.r_[ub[upper],-lb[lower]]
 opts=[(0,1)]*n+[(0,None) if x else (0,0) for x in soft]*2
 z=linprog(np.r_[np.zeros(n),weight,weight],A_ub=mat,b_ub=rhs,bounds=opts,method='highs')
 report={'diagnostic_only':True,'success':z.success,'message':z.message,'violations':[]}
 if z.success:
  low=z.x[n:n+m];up=z.x[n+m:]
  report['violations']=[{'name':name,'lower_shortfall':float(lo),'upper_excess':float(hi)} for name,lo,hi in zip(names,low,up) if max(lo,hi)>1e-5]
 g.dump(g.RES/'infeasibility_diagnosis.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
 raise SystemExit(0)
s.milp=diagnose
if __name__=='__main__':s.main()
