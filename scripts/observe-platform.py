#!/usr/bin/env python3
"""Print a credential-free local observation snapshot; this is not continuous monitoring."""
import collections,datetime,json,math,os,subprocess,sys
compose=['docker','compose','--env-file',os.environ.get('SEMS_ENV_FILE','.env'),'-f',os.environ.get('SEMS_COMPOSE_FILE','deployment/compose.yaml')]
def output(args):return subprocess.check_output(args,text=True,stderr=subprocess.DEVNULL).strip()
window=sys.argv[1] if len(sys.argv)>1 else '10m'
rows=[]
for line in output(compose+['logs','--no-log-prefix','--since',window,'gateway']).splitlines():
 try:r=json.loads(line)
 except ValueError:continue
 if isinstance(r,dict) and 'duration' in r and 'status' in r:rows.append(r)
durations=sorted(float(r['duration']) for r in rows)
ids=output(compose+['ps','-q']).split()
resources=[]
if ids:
 for line in output(['docker','stats','--no-stream','--format','{{json .}}',*ids]).splitlines():
  r=json.loads(line);resources.append({k:r[k] for k in ['Name','CPUPerc','MemUsage','MemPerc','NetIO','BlockIO']})
db=output(compose+['exec','-T','postgres','psql','-U','postgres','-d','sems','-Atq','-c',"SELECT json_build_object('connections',count(*),'active',count(*) FILTER(WHERE state='active'),'waiting',count(*) FILTER(WHERE wait_event_type='Lock')) FROM pg_stat_activity WHERE datname=current_database()"])
print(json.dumps({'observedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'logWindow':window,'requests':len(rows),'statusCounts':dict(collections.Counter(str(r['status']) for r in rows)),'serverErrorRate':sum(r['status']>=500 for r in rows)/len(rows) if rows else None,'p95Seconds':durations[math.ceil(len(durations)*.95)-1] if durations else None,'containers':resources,'database':json.loads(db),'note':'Gateway completed requests only; resource and DB samples are instantaneous. Not proof of load targets or high availability.'},indent=2))
