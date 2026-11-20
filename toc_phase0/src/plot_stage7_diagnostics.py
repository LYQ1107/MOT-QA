"""Standalone scientific figures; existing diagnostics only, no inference."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from stage6_common import ROOT,read


def main():
    directory=ROOT/'results/stage7/figures';directory.mkdir(parents=True,exist_ok=True)
    ds=read(ROOT/'results/stage7_track_information_diagnostics.json')['covered_rule_diagnostics']['test']
    names={'reappear_or_disappear':'R/D','cross_object_order':'X-Order','event_count':'Count'}
    labels={'fully_hidden':'Fully hidden','leaves_frame':'Leaves frame','5 or more':'5+'}
    fig,axes=plt.subplots(1,3,figsize=(13,4.0),gridspec_kw={'width_ratios':[1,1,2.1]})
    for ax,dim in zip(axes,names):
        r=ds[dim];m=r['frozen_rule'];ys=m['truth_rows'];xs=m['prediction_columns']
        matrix=np.array([[m['confusion_matrix'][y][x] for x in xs] for y in ys])
        fraction=matrix/matrix.sum(axis=1,keepdims=True)
        im=ax.imshow(fraction,vmin=0,vmax=1,cmap='Blues',aspect='auto')
        for i in range(len(ys)):
            for j in range(len(xs)):ax.text(j,i,str(matrix[i,j]),ha='center',va='center',color='white' if fraction[i,j]>.55 else 'black',fontsize=11)
        ax.set_xticks(range(len(xs)),[labels.get(x,x) for x in xs],rotation=30,ha='right')
        ax.set_yticks(range(len(ys)),[labels.get(y,y) for y in ys])
        ax.set_xlabel('Frozen rule prediction');ax.set_ylabel('True class')
        ax.set_title(f"{names[dim]}: covered {r['covered']}/{r['total']}\nBalanced accuracy {100*m['balanced_accuracy']:.1f}%\nkappa {m['kappa']:.3f}",fontsize=10)
    fig.suptitle('Frozen v1, held-out test questions covered by the rules',fontsize=13)
    fig.text(.5,.01,'Cell numbers are question counts; color is within-true-class proportion. Count predictions 0/1 remain errors.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.05,.94,.91));fig.colorbar(im,ax=axes.tolist(),fraction=.018,pad=.025,label='Row fraction')
    for suffix in ['png','svg']:fig.savefig(directory/f'test_rule_confusions.{suffix}',dpi=180,bbox_inches='tight')
    plt.close(fig)
    metrics_path=ROOT/'results/stage7_metrics.json'
    if metrics_path.exists():
        metrics=read(metrics_path);recalls=metrics['RD_class_recalls']
        order=['Official A','T-none','T1-original','T1']+[c for c in ('T-ph','T-sh') if c in recalls]+['Majority blind','Frozen rule','Route']
        x=np.arange(len(order));fig,ax=plt.subplots(figsize=(12,4.0))
        for offset,c,name,color in [(-.2,'fully_hidden','Fully hidden (n=68)','#3979ad'),(.2,'leaves_frame','Leaves frame (n=33)','#e59b3b')]:
            ax.bar(x+offset,[100*recalls[k]['per_class_recall'][c] for k in order],width=.38,label=name,color=color)
        ax.set_xticks(x,order,rotation=25,ha='right');ax.set_ylim(0,105);ax.set_ylabel('Within-class recall (%)')
        ax.set_title('R/D: accuracy changes and class preference');ax.legend(loc='upper left',bbox_to_anchor=(0,1.18),ncol=2,frameon=False)
        ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);fig.tight_layout()
        for suffix in ['png','svg']:fig.savefig(directory/f'RD_class_recalls.{suffix}',dpi=180,bbox_inches='tight')
        plt.close(fig)
    print('Saved Stage7 scientific figures to',directory)


if __name__=='__main__':main()
