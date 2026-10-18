#!/usr/bin/env python3
"""P1/P2 business regressions. Use only an isolated disposable Compose stack."""
from acceptance import *
import base64, subprocess, time
compose=['docker','compose','--env-file',os.environ.get('SEMS_ENV_FILE','.env'),'-f',os.environ.get('SEMS_COMPOSE_FILE','deployment/compose.yaml')]
def sql(query):
 r=subprocess.run(compose+['exec','-T','postgres','psql','-v','ON_ERROR_STOP=1','-U','postgres','-d','sems','-Atq','-c',query],capture_output=True,text=True)
 assert r.returncode==0, 'Fixture SQL failed: '+r.stderr
 return r.stdout.strip()
def status(method,path,body,token=None):
 req=urllib.request.Request(BASE+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})},method=method)
 try:
  with urllib.request.urlopen(req,timeout=20) as r:return r.status
 except urllib.error.HTTPError as e:return e.code
session=call('POST','/api/v1/auth/login',{'email':users[2]['email'],'password':password})
claims=json.loads(base64.urlsafe_b64decode(session['accessToken'].split('.')[1]+'=='))
assert session['expiresIn']==3600 and claims['exp']-claims['iat']==3600
bootstrap=call('GET','/api/v1/auth/me',token=admin)
call('PUT',f"/api/v1/admin/users/{bootstrap['id']}/roles",{'roles':['ATTENDEE']},admin,409)
call('PUT',f"/api/v1/admin/users/{users[1]['id']}/roles",{'roles':['ATTENDEE','ADMIN']},admin)
second=login(users[1]['email'])
with concurrent.futures.ThreadPoolExecutor(2) as pool:
 results=list(pool.map(lambda u:status('PUT',f"/api/v1/admin/users/{u}/roles",{'roles':['ATTENDEE']},admin),[bootstrap['id'],users[1]['id']]))
assert results.count(200)==1 and any(x in (409,403) for x in results),results
survivor=admin if results[0]!=200 else second
call('PUT',f"/api/v1/admin/users/{bootstrap['id']}/roles",{'roles':['ATTENDEE','ADMIN']},survivor)
admin=login(os.environ['SEMS_BOOTSTRAP_ADMIN_EMAIL'],os.environ['SEMS_BOOTSTRAP_ADMIN_PASSWORD'])
call('PUT',f"/api/v1/admin/users/{users[1]['id']}/roles",{'roles':['ATTENDEE','ORGANIZER']},admin)
print('PASS: JWT exactly 3600 seconds; last administrator protected under concurrent demotions')
sql(f"INSERT INTO identity.users(id,username,email,password_hash) SELECT gen_random_uuid(),'bulk{suffix}'||n,'bulk{suffix}'||n||'@example.com','unusable' FROM generate_series(1,67) n")
u=call('GET','/api/v1/admin/users?size=10&search=bulk'+suffix,token=admin)
assert len(u['items'])==10 and u['totalElements']==67 and u['totalPages']==7
assert len(paged('/api/v1/admin/users?search=bulk'+suffix,admin))==67
for endpoint in ['/api/v1/admin/users','/api/v1/admin/organizations','/api/v1/admin/organizations/requests','/api/v1/me/staff-assignments',f"/api/v1/organizations/{org_a['id']}/requests"]:
 t=a if '/organizations/'+org_a['id'] in endpoint else admin
 for query in ['size=51','page=-1','page=100001']:
  call('GET',endpoint+'?'+query,token=t,expected=400)
print('PASS: bounded user pages/search and admin/governance/staff pagination validation')
begin=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=10)
e=call('POST','/api/v1/organizer/events',{**body,'startsAt':begin.isoformat(),'endsAt':(begin+datetime.timedelta(hours=1)).isoformat()},a,201)
p='/api/v1/organizer/events/'+e['id']
inv=call('PUT',p+'/ticket-types',{'eventVersion':e['version'],'version':0,'ticketTypes':[{'name':'General','quota':20,'opensAt':(begin-datetime.timedelta(days=1)).isoformat(),'closesAt':begin.isoformat()},{'name':'Later','quota':5,'opensAt':(begin-datetime.timedelta(minutes=5)).isoformat(),'closesAt':begin.isoformat()}]},a)
e=call('GET',p,token=a);e=call('POST',p+'/publish',{'version':e['version'],'ticketVersion':inv['version']},a)
t=inv['ticketTypes'][0];later=inv['ticketTypes'][1]
book=call('POST','/api/v1/bookings',{'eventId':e['id'],'ticketTypeId':t['id'],'quantity':2,'requestKey':str(uuid.uuid4())},attendee)
call('PUT','/api/v1/pre-registrations/'+e['id'],{'ticketTypeId':later['id'],'quantity':1},attendee)
e=call('PUT',p+'/revision',{**e,'title':'Current '+suffix,'location':'New Hall','publicationStatus':'PAUSED'},a)
call('GET','/api/v1/events/'+e['id'],expected=404)
current=call('GET','/api/v1/bookings/'+book['id'],token=attendee)
assert current['eventLocation']=='Campus' and current['currentEvent']['location']=='New Hall' and current['currentEvent']['status']=='PAUSED'
pre=call('GET','/api/v1/pre-registrations',token=attendee)
assert next(x for x in pre['items'] if x['eventId']==e['id'])['currentEvent']['location']=='New Hall'
call('GET','/api/v1/bookings/'+book['id'],token=b,expected=404)
call('PUT',p+'/staff',{'userId':users[0]['id'],'active':True},a,204)
assert call('GET','/api/v1/me/staff-assignments?size=1',token=a)['items'][0]['title']=='Current '+suffix
check='/api/v1/events/'+e['id']+'/check-ins'
first=call('POST',check,{'credential':book['tickets'][0]['credential']},a)
sql(f"UPDATE admission.sales SET starts_at=now()-interval '16 minutes',ends_at=now()+interval '44 minutes' WHERE event_id='{e['id']}'")
call('POST',check,{'credential':book['tickets'][1]['credential']},a,409)
repeat=call('POST',check,{'credential':book['tickets'][0]['credential']},a)
assert repeat['alreadyCheckedIn'] and repeat['checkedInAt']==first['checkedInAt']
print('PASS: paused-event live venue, original snapshot, private ownership, pre-registration and start+15-minute cutoff with idempotent replay')
try:
 subprocess.run(compose+['stop','event-catalog'],check=True,stdout=subprocess.DEVNULL)
 degraded=call('GET','/api/v1/bookings/'+book['id'],token=attendee)
 assert degraded['currentEvent'] is None and degraded['tickets'][0]['credential']==book['tickets'][0]['credential']
finally:subprocess.run(compose+['start','event-catalog'],check=True,stdout=subprocess.DEVNULL)
for _ in range(30):
 time.sleep(1)
 if call('GET','/api/v1/bookings/'+book['id'],token=attendee)['currentEvent'] is not None:break
else:raise AssertionError('Catalog did not recover')
print('PASS: Catalog outage preserves ticket access; live details recover')
with concurrent.futures.ThreadPoolExecutor(25) as pool:
 rates=list(pool.map(lambda _:status('POST','/api/v1/auth/login',{'email':'missing@example.com','password':'wrong-password'}),range(40)))
assert 429 in rates and all(x in (401,429) for x in rates),rates
assert call('GET','/api/v1/bookings/'+book['id'],token=attendee)['id']==book['id']
time.sleep(5);login(users[2]['email'])
print('PASS: authentication bursts return 429; booking reads unaffected; normal login recovers')
