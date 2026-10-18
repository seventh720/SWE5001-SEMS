#!/usr/bin/env python3
"""Organization-scoped event search, pagination and shared organizer permissions."""
from acceptance import *
from urllib.parse import urlencode

def listing(token, org=org_a['id'], **params):
    return call('GET','/api/v1/organizer/events?'+urlencode({'organizationId':org,**params}),token=token)

# A match on a later unfiltered page must be found by server-side search.
created=[]
for n in range(3):
    created.append(call('POST','/api/v1/organizer/events',{**body,'title':f'Directory {suffix} {n}'},a,201))
first=listing(a,keyword='directory '+suffix,page=0,size=2)
second=listing(a,keyword='DIRECTORY '+suffix,page=1,size=2)
assert first['totalElements']==second['totalElements']==3
assert first['totalPages']==2
assert {e['id'] for e in first['items']+second['items']}=={e['id'] for e in created}
assert listing(a,keyword='missing-'+suffix)['totalElements']==0
assert listing(a,keyword='%')['totalElements']==0
assert listing(a,keyword='_')['totalElements']==0
assert listing(b,org_b['id'],keyword=suffix)['totalElements']==0
call('GET','/api/v1/organizer/events?'+urlencode({'organizationId':org_a['id'],'keyword':'x'*201}),token=a,expected=400)
call('GET','/api/v1/organizer/events?'+urlencode({'organizationId':org_a['id'],'keyword':suffix}),token=b,expected=404)
# Two organization organizers share the administrator's events and each other's events.
for user,token in [(users[1],b),(users[2],attendee)]:
    invite=call('POST',f"/api/v1/organizations/{org_a['id']}/invitations",{'email':user['email'],'role':'ORGANIZER'},a)
    call('POST','/api/v1/invitations/accept',{'token':invite['token']},token,204)
shared=call('POST','/api/v1/organizer/events',{**body,'title':'Shared '+suffix},b,201)
shared_path='/api/v1/organizer/events/'+shared['id']
changed=call('PUT',shared_path,{**body,'title':'Shared revised '+suffix,'version':shared['version']},attendee)
assert listing(b,keyword='Shared revised '+suffix)['items'][0]['id']==shared['id']
assert listing(attendee,keyword='Shared revised '+suffix)['items'][0]['id']==shared['id']
call('PUT',shared_path,{**body,'version':shared['version']},b,409)
config=call('PUT',shared_path+'/ticket-types',{'eventVersion':changed['version'],'version':0,'ticketTypes':[{'name':'General','quota':30,'opensAt':(start-datetime.timedelta(days=8)).isoformat(),'closesAt':start.isoformat()}]},attendee)
current=call('GET',shared_path,token=b)
assert call('POST',shared_path+'/publish',{'version':current['version'],'ticketVersion':config['version']},b)['status']=='PUBLISHED'
assert call('GET',shared_path,token=attendee)['status']=='PUBLISHED'
# Demotion takes effect with the same token; membership alone cannot manage events.
member=next(m for m in paged(f"/api/v1/organizations/{org_a['id']}/members",a) if m['userId']==users[2]['id'])
call('PUT',f"/api/v1/organizations/{org_a['id']}/members/{users[2]['id']}",{'role':'MEMBER','status':'ACTIVE','version':member['version']},a,204)
call('GET',shared_path,token=attendee,expected=404)
assert call('GET','/api/v1/events/'+shared['id'],token=attendee)['id']==shared['id']
print('PASS: scoped search, literal keywords, pagination, two collaborating organizers, publication, stale-write rejection and live demotion')
