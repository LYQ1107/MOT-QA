"""Locate supply/constraint conflicts. Never accepts a relaxed candidate set."""
import json
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import eye, hstack, vstack, csr_matrix
import generate_candidates_round2 as g
import readability_v3 as v
import select_readability_v3 as s


def diagnose(objective, integrality, bounds, constraints, options):
    a = constraints.A.tocsr()
    lb, ub = np.array(constraints.lb), np.array(constraints.ub)
    n, m = a.shape[1], a.shape[0]
    names = json.loads((v.D/'selection_constraints_events225.json').read_text())['constraint_names']
    soft = np.array([not name.startswith(("('video'", "('identity'", "('duplicate'")) for name in names])
    weight = np.array([1000. if name.startswith(('operation ', 'dataset ', 'numeric ', 'O7 true', 'O7 false', 'ordinary ', 'O8 same', 'identity challenge', 'confusion')) else 1. for name in names])
    slack = eye(m, format='csr')
    zero = csr_matrix((m, m))
    up, low = np.isfinite(ub), np.isfinite(lb)
    mat = vstack([hstack([a[up], zero[up], -slack[up]]),
                  hstack([-a[low], -slack[low], zero[low]])], format='csr')
    result = linprog(np.r_[np.zeros(n), weight, weight], A_ub=mat,
                     b_ub=np.r_[ub[up], -lb[low]],
                     bounds=[(0, 1)]*n+[(0, None) if flag else (0, 0) for flag in soft]*2,
                     method='highs')
    report = {'diagnostic_only': True, 'success': result.success, 'message': result.message}
    if result.success:
        report['violations'] = [{'name': name, 'lower_shortfall': float(lo), 'upper_excess': float(hi)}
            for name, lo, hi in zip(names, result.x[n:n+m], result.x[n+m:]) if max(lo, hi) > 1e-5]
    g.dump(v.D/'infeasibility_diagnosis.json', report)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    raise SystemExit(0)


if __name__ == '__main__':
    s.milp = diagnose
    s.main()
