#!/usr/bin/env python3
"""Verify Docker DNS refresh without restarting gateway. Disposable stack only."""
import json,os,subprocess,time,urllib.request,urllib.error
compose=['docker','compose','--env-file',os.environ.get('SEMS_ENV_FILE','.env'),'-f',os.environ.get('SEMS_COMPOSE_FILE','deployment/compose.yaml')]
base=os.environ.get('SEMS_BASE_URL','http://localhost:18080')
def output(*args):return subprocess.check_output(compose+list(args),text=True).strip()
def requests(n):
 for _ in range(n):
  try:
   with urllib.request.urlopen(base+'/api/v1/bookings',timeout=5) as r:code=r.status
  except urllib.error.HTTPError as e:code=e.code
  assert code==401,code
  time.sleep(.05)
def gateway_id():return output('ps','-q','gateway')
def count():return output('exec','-T','postgres','psql','-U','postgres','-d','sems','-Atq','-c','SELECT count(*) FROM admission.bookings')
gateway=gateway_id();bookings=count();since=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
subprocess.run(compose+['up','-d','--no-deps','--scale','admission=3','admission'],check=True,stdout=subprocess.DEVNULL)
time.sleep(12)
requests(30)
logs=output('logs','--no-log-prefix','--since',since,'gateway')
upstreams=set()
for line in logs.splitlines():
 try:r=json.loads(line)
 except ValueError:continue
 if r.get('path')=='/api/v1/bookings' and r.get('status')==401:upstreams.add(r['upstream'])
assert len(upstreams)==3,upstreams
assert gateway_id()==gateway and count()==bookings
print('PASS: 3 Admission replicas receive traffic; gateway unchanged; persisted booking count unchanged')
subprocess.run(compose+['up','-d','--no-deps','--scale','admission=2','admission'],check=True,stdout=subprocess.DEVNULL)
time.sleep(7);requests(30)
assert gateway_id()==gateway and count()==bookings
print('PASS: scale-down DNS refresh without gateway restart; 30/30 requests routed successfully')
