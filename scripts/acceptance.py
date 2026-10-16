#!/usr/bin/env python3
"""Real HTTP/PostgreSQL acceptance against the Compose stack; creates unique test accounts."""
import concurrent.futures, datetime, json, os, urllib.request, urllib.error, uuid
BASE=os.environ.get('SEMS_BASE_URL','http://localhost:18080')
def call(method,path,body=None,token=None,expected=200):
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    req=urllib.request.Request(BASE+path, data=None if body is None else json.dumps(body).encode(),headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=15) as response: status=response.status; raw=response.read()
    except urllib.error.HTTPError as error: status=error.code; raw=error.read()
    assert status==expected, f'{method} {path}: expected {expected}, got {status}'
    if not raw: return None
    try: return json.loads(raw)
    except json.JSONDecodeError:
        if status < 400: raise
        return None
suffix=uuid.uuid4().hex[:10]
password='Test-'+uuid.uuid4().hex
users=[]
for n in range(3):
    email=f'accept-{suffix}-{n}@example.com'
    user=call('POST','/api/v1/auth/register',{'username':f'u{suffix}{n}','email':email,'password':password},expected=201)
    assert user['roles']==['ATTENDEE']; users.append(user)
call('POST','/api/v1/auth/register',{'username':users[0]['username'],'email':'other-'+suffix+'@example.com','password':password},expected=409)
call('POST','/api/v1/auth/register',{'username':'unicode'+suffix,'email':'unicode'+suffix+'@example.com','password':'密'*30},expected=400)
call('POST','/api/v1/auth/login',{'email':users[0]['email'],'password':'wrong-password'},expected=401)
def login(email,pw=password):return call('POST','/api/v1/auth/login',{'email':email,'password':pw})['accessToken']
admin=login(os.environ['SEMS_BOOTSTRAP_ADMIN_EMAIL'],os.environ['SEMS_BOOTSTRAP_ADMIN_PASSWORD'])
attendee=login(users[2]['email'])
call('GET','/api/v1/admin/users',token=attendee,expected=403)
call('GET','/api/v1/organizer/events',expected=401)

for user in users[:2]:call('PUT',f"/api/v1/admin/users/{user['id']}/roles",{'roles':['ATTENDEE','ORGANIZER']},admin)
call('PUT',f"/api/v1/admin/users/{users[0]['id']}/roles",{'roles':[None]},admin,expected=400)
a,b=[login(u['email']) for u in users[:2]]
org_a=call('POST','/api/v1/admin/organizations',{'name':'Society '+suffix,'slug':'society-'+suffix,'adminEmail':users[0]['email']},admin)
org_b=call('POST','/api/v1/admin/organizations',{'name':'Training '+suffix,'slug':'training-'+suffix,'adminEmail':users[1]['email']},admin)
call('GET','/api/v1/organizer/events?organizationId='+org_a['id'],token=attendee,expected=404)
assert call('GET','/api/v1/auth/me',token=a)['id']==users[0]['id']
# Verify signed tokens cannot be altered.
parts=a.split('.');parts[2]=('A' if parts[2][0]!='A' else 'B')+parts[2][1:]
call('GET','/api/v1/organizer/events',token='.'.join(parts),expected=401)
start=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=7)
body={'organizationId':org_a['id'],'visibility':'PUBLIC','title':'Acceptance seminar '+suffix,'description':'Draft isolation acceptance','location':'Campus','startsAt':start.isoformat(),'endsAt':(start+datetime.timedelta(hours=2)).isoformat(),'capacity':30}
draft=call('POST','/api/v1/organizer/events',body,a,201);path='/api/v1/organizer/events/'+draft['id']
assert draft['status']=='DRAFT'
assert call('GET',path,token=a)['title']==body['title']
assert call('GET','/api/v1/organizer/events?organizationId='+org_b['id'],token=b)['totalElements']==0
call('GET',path,token=b,expected=404)
call('GET',path,token=admin,expected=404)
call('PUT',path,{**body,'version':draft['version']},b,404)
call('PUT',path,{**body,'version':draft['version']},attendee,404)
call('GET','/api/v1/organizer/events?size=51&organizationId='+org_a['id'],token=a,expected=400)
call('GET','/api/v1/organizer/events/not-a-uuid',token=a,expected=400)
call('POST','/api/v1/organizer/events',{**body,'endsAt':body['startsAt']},a,400)
call('POST','/api/v1/organizer/events',{**body,'capacity':0},a,400)
call('PUT',path,body,a,400)
updated=call('PUT',path,{**body,'title':'Updated '+suffix,'version':draft['version']},a)
assert updated['version']>draft['version']
call('PUT',path,{**body,'version':draft['version']},a,409)
# Two writers sharing a version: exactly one wins; another gets conflict.
def competing(n):
    req=urllib.request.Request(BASE+path,data=json.dumps({**body,'title':f'Concurrent {n}','version':updated['version']}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+a},method='PUT')
    try:
        with urllib.request.urlopen(req,timeout=15) as response:return response.status
    except urllib.error.HTTPError as error:return error.code
with concurrent.futures.ThreadPoolExecutor(2) as pool: assert sorted(pool.map(competing,[1,2]))==[200,409]
assert call('GET',path,token=a)['version']>updated['version']
call('POST',path+'/publish',{},a,400)
print('PASS: registration, login, RSA signature, role grants, draft persistence, validation, owner isolation and concurrent edits')
