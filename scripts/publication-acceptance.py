#!/usr/bin/env python3
"""Runs foundation acceptance, then inventory/publication and durable recovery checks."""
from acceptance import *
import subprocess,time
compose=['docker','compose','--env-file','.env','-f','deployment/compose.yaml']
def current(event_path):return call('GET',event_path,token=a)
def configuration(event_path,ticket_version=0,quotas=(20,10)):
    return {'eventVersion':current(event_path)['version'],'version':ticket_version,'ticketTypes':[
        {'name':name,'quota':quota,'opensAt':(start-datetime.timedelta(days=1)).isoformat(),'closesAt':start.isoformat()}
        for name,quota in zip(['General','Student'],quotas)]}
# Use a distinctive title for public search.
now=current(path)
call('PUT',path,{**body,'title':'Public '+suffix,'version':now['version']},a)
call('GET','/api/v1/events/'+draft['id'],expected=404)
call('POST',path+'/publish',{'version':current(path)['version'],'ticketVersion':1},a,409)
tickets_path=path+'/ticket-types'
call('GET',tickets_path,token=b,expected=404)
call('PUT',tickets_path,configuration(path,quotas=(30,1)),a,409)
config=call('PUT',tickets_path,configuration(path),a)
assert sum(t['quota'] for t in config['ticketTypes'])==30
assert all(t['available']==t['quota'] and t['amount']==0 for t in config['ticketTypes'])
now=current(path)
call('PUT',path,{**body,'capacity':5,'version':now['version']},a,409)
# Two competing edits use one version: exactly one can commit.
conf=configuration(path,config['version'])
def edit_config(n):
    req=urllib.request.Request(BASE+tickets_path,data=json.dumps(conf).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+a},method='PUT')
    try:
        with urllib.request.urlopen(req,timeout=15) as response:return response.status
    except urllib.error.HTTPError as error:return error.code
with concurrent.futures.ThreadPoolExecutor(2) as pool:assert sorted(pool.map(edit_config,[1,2]))==[200,409]
call('POST',path+'/publish',{'version':current(path)['version'],'ticketVersion':config['version']},a,409)
assert current(path)['status']=='DRAFT'
config=call('GET',tickets_path,token=a)
publish_body={'version':current(path)['version'],'ticketVersion':config['version']}
assert call('POST',path+'/publish',publish_body,a)['status']=='PUBLISHED'
assert call('POST',path+'/publish',publish_body,a)['status']=='PUBLISHED'
call('POST',path+'/publish',{**publish_body,'ticketVersion':config['version']+1},a,409)
public_id='/api/v1/events/'+draft['id']
assert call('GET',public_id)['id']==draft['id']
assert any(e['id']==draft['id'] for e in call('GET','/api/v1/events?keyword='+suffix)['items'])
assert call('GET',public_id+'/ticket-types')['state']=='ACTIVE'
call('PUT',tickets_path,configuration(path,config['version']),a,409)
call('GET','/internal/v1/events/'+draft['id']+'/published',expected=404)
print('PASS: ticket allocation, sales windows, owner isolation, configuration race, retry-safe publication and public discovery')
# A separate offering is left pending while Admission is stopped, then recovered after Catalog restarts.
recovery=call('POST','/api/v1/organizer/events',{**body,'title':'Recovery '+suffix},a,201)
recovery_path='/api/v1/organizer/events/'+recovery['id']
config=call('PUT',recovery_path+'/ticket-types',configuration(recovery_path),a)
recovery_body={'version':current(recovery_path)['version'],'ticketVersion':config['version']}
try:
    subprocess.run(compose+['stop','admission'],check=True,stdout=subprocess.DEVNULL)
    assert call('POST',recovery_path+'/publish',recovery_body,a,202)['status']=='PUBLISHING'
    call('GET','/api/v1/events/'+recovery['id'],expected=404)
    subprocess.run(compose+['restart','event-catalog'],check=True,stdout=subprocess.DEVNULL)
finally:
    subprocess.run(compose+['start','admission'],check=True,stdout=subprocess.DEVNULL)
# Container restarts can change IPs; refresh Nginx's service resolution.
subprocess.run(compose+['restart','gateway'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['bash','scripts/smoke.sh'],check=True)
for attempt in range(30):
    if current(recovery_path)['status']=='PUBLISHED':break
    time.sleep(2)
else:raise AssertionError('Pending publication did not recover')
assert call('POST',recovery_path+'/publish',recovery_body,a)['status']=='PUBLISHED'
assert call('GET','/api/v1/events/'+recovery['id'])['id']==recovery['id']
print('PASS: pending events stay private; publication survives Catalog restart and Admission outage')
