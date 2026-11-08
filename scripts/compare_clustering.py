"""Benchmark diagnóstico de clustering con las mismas características y el mismo corte."""
import argparse, json, random, statistics
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from break_ia.agent import BreakAgent
from break_ia.clustering import user_features,kmeans,silhouette,_dist2
from break_ia.data_loader import group_orders
from break_ia.utility import parse_time_slot

DATA=ROOT/"data"/"raw"
OUT=ROOT/"data"/"reports"/"clustering_comparison.json"

def distance_matrix(points):
    return [[_dist2(a,b)**0.5 for b in points] for a in points]

def kmedoids(dist,k=3,seed=7,max_iter=40):
    rng=random.Random(seed); n=len(dist)
    medoids=rng.sample(range(n),k)
    def cost(ms):
        return sum(min(dist[i][m] for m in ms) for i in range(n))
    best=cost(medoids)
    for _ in range(max_iter):
        improved=False; choice=None; choice_cost=best
        for pos in range(k):
            for candidate in range(n):
                if candidate in medoids: continue
                trial=medoids[:];trial[pos]=candidate
                value=cost(trial)
                if value+1e-12<choice_cost:
                    choice,choice_cost=trial,value
        if choice is None: break
        medoids,best=choice,choice_cost;improved=True
        if not improved: break
    labels=[min(range(k),key=lambda c:dist[i][medoids[c]]) for i in range(n)]
    return labels

def agglomerative_average(dist,k=3):
    clusters=[[i] for i in range(len(dist))]
    while len(clusters)>k:
        best=None; best_d=float("inf")
        for i in range(len(clusters)):
            for j in range(i+1,len(clusters)):
                vals=[dist[a][b] for a in clusters[i] for b in clusters[j]]
                d=sum(vals)/len(vals)
                if d<best_d:best,best_d=(i,j),d
        i,j=best
        clusters[i]=clusters[i]+clusters[j]
        del clusters[j]
    labels=[0]*len(dist)
    for cid,members in enumerate(clusters):
        for idx in members:labels[idx]=cid
    return labels

def dbscan(dist,min_samples=4):
    n=len(dist)
    kth=sorted(sorted(row)[min_samples-1] for row in dist)
    eps=kth[int(.40*(n-1))]
    labels=[-1]*n;cid=0
    def neighbors(i):return [j for j,d in enumerate(dist[i]) if d<=eps]
    for i in range(n):
        if labels[i]!=-1:continue
        near=neighbors(i)
        if len(near)<min_samples:continue
        labels[i]=cid;queue=list(near);seen=set(queue)
        while queue:
            j=queue.pop()
            if labels[j]==-1:labels[j]=cid
            near_j=neighbors(j)
            if len(near_j)>=min_samples:
                for q in near_j:
                    if q not in seen:seen.add(q);queue.append(q)
        cid+=1
    return labels,eps

def describe(labels):
    return {str(c):n for c,n in sorted(Counter(labels).items())}

def safe_silhouette(points,labels):
    keep=[i for i,l in enumerate(labels) if l!=-1]
    labs=[labels[i] for i in keep]
    if len(set(labs))<2:return None
    return round(silhouette([points[i] for i in keep],labs),4)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--as-of", default=None, help="Corte exclusivo YYYY-MM-DD HH:MM:SS")
    args=parser.parse_args()
    cutoff=args.as_of or datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M:%S")
    agent=BreakAgent(DATA,until=cutoff,use_clusters=False,use_hybrid=False)
    users=sorted(u for u,ls in agent.user_orders.items() if ls)
    raw=[user_features(agent.user_orders[u],agent.user_order_groups.get(u,[])) for u in users]
    mins=[min(c) for c in zip(*raw)];maxs=[max(c) for c in zip(*raw)]
    points=[[((v-lo)/(hi-lo) if hi>lo else 0.0) for v,lo,hi in zip(row,mins,maxs)] for row in raw]
    dist=distance_matrix(points)
    _,km_labels,_=kmeans(points,3,seed=7)
    med_labels=kmedoids(dist,3)
    hier_labels=agglomerative_average(dist,3)
    db_labels,eps=dbscan(dist)
    results={
      "cutoff_exclusive":cutoff,"users":len(users),"features":"same 10-dimensional vector as production K-Means",
      "kmeans":{"silhouette":round(silhouette(points,km_labels),4),"cluster_sizes":describe(km_labels)},
      "kmedoids":{"silhouette":safe_silhouette(points,med_labels),"cluster_sizes":describe(med_labels)},
      "hierarchical_average":{"silhouette":safe_silhouette(points,hier_labels),"cluster_sizes":describe(hier_labels)},
      "dbscan":{"epsilon":round(eps,5),"min_samples":4,"silhouette_non_noise":safe_silhouette(points,db_labels),
                "cluster_sizes_including_noise":describe(db_labels),"noise_users":sum(1 for x in db_labels if x==-1)}
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(results,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
