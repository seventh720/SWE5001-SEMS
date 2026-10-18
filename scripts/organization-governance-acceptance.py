#!/usr/bin/env python3
"""Organization change/closure approvals and soft deletion; disposable stack only."""
from acceptance import *
import time
def await_closed(identity,target):
 for _ in range(45):
  orgs=paged('/api/v1/admin/organizations',admin)
  if target=='DELETED' and not any(o['id']==identity for o in orgs):return
  if any(o['id']==identity and o['status']==target for o in orgs):return
  time.sleep(2)
 raise AssertionError('Closure did not complete')
def org(token=a,identity=None):return next(o for o in call('GET','/api/v1/me/organizations',token=token) if o['id']==(identity or org_a['id']))
def request(kind='UPDATE',**extra):return call('POST',f"/api/v1/organizations/{org_a['id']}/requests",{'kind':kind,'name':'Renamed '+suffix,'slug':'renamed-'+suffix,'reason':'Acceptance check','version':org()['version'],**extra},a)
def review(r,approve=True):return call('POST','/api/v1/admin/organizations/requests/'+r['id']+'/review',{'approve':approve,'note':'Reviewed by platform admin'},admin,204)
profile=f"/api/v1/admin/organizations/{org_a['id']}/profile"
call('PUT',profile,{'name':'Denied','slug':'denied-'+suffix,'version':0},a,403)
call('POST',f"/api/v1/organizations/{org_a['id']}/requests",{'kind':'CLOSE','reason':'No access','version':0},attendee,403)
r=request();assert org()['name']!=r['name']
call('POST',f"/api/v1/organizations/{org_a['id']}/requests",{'kind':'CLOSE','reason':'Duplicate','version':0},a,409)
call('POST','/api/v1/admin/organizations/requests/'+r['id']+'/review',{'approve':True,'note':'Not admin'},a,403)
review(r,False);assert org()['name']!=r['name']
r=request();review(r);assert org()['name']==r['name']
call('POST','/api/v1/admin/organizations/requests/'+r['id']+'/review',{'approve':True,'note':'Again'},admin,409)
# Stale requests cannot overwrite direct platform edits.
r=request(name='Requested '+suffix,slug='requested-'+suffix)
call('PUT',profile,{'name':'Direct '+suffix,'slug':'direct-'+suffix,'version':org()['version']},admin,204)
call('POST','/api/v1/admin/organizations/requests/'+r['id']+'/review',{'approve':True,'note':'Stale'},admin,409)
review(r,False)
# Establish an offering and committed ticket before closure.
event=call('GET',path,token=a)
inventory=call('PUT',path+'/ticket-types',{'eventVersion':event['version'],'version':0,'ticketTypes':[{'name':'General','quota':10,'opensAt':(start-datetime.timedelta(days=8)).isoformat(),'closesAt':start.isoformat()}]},a)
event=call('GET',path,token=a);event=call('POST',path+'/publish',{'version':event['version'],'ticketVersion':inventory['version']},a)
booking=call('POST','/api/v1/bookings',{'eventId':event['id'],'ticketTypeId':inventory['ticketTypes'][0]['id'],'quantity':1,'requestKey':str(uuid.uuid4())},attendee)
assert call('GET','/api/v1/events/'+event['id'])['organizationName']=='Direct '+suffix
r=request('CLOSE');review(r)
await_closed(org_a['id'],'SUSPENDED')
assert call('GET','/api/v1/me/organizations',token=a)==[]
assert next(o for o in paged('/api/v1/admin/organizations',admin) if o['id']==org_a['id'])['status']=='SUSPENDED'
call('GET',path,token=a,expected=404)
call('GET','/api/v1/events/'+event['id'],expected=404)
assert event['id'] not in [e['id'] for e in call('GET','/api/v1/events')['items']]
call('POST','/api/v1/bookings',{'eventId':event['id'],'ticketTypeId':inventory['ticketTypes'][0]['id'],'quantity':1,'requestKey':str(uuid.uuid4())},attendee,404)
closed_booking=call('GET','/api/v1/bookings/'+booking['id'],token=attendee)
assert closed_booking['status']=='CANCELLED' and all(t['state']=='CANCELLED' for t in closed_booking['tickets'])
assert call('GET','/api/v1/me/organizations',token=b)[0]['id']==org_b['id']
# Permanent closure cannot be reactivated (temporary suspension remains reversible).
call('PATCH',f"/api/v1/admin/organizations/{org_a['id']}",{'status':'ACTIVE'},admin,409)
assert call('GET','/api/v1/me/organizations',token=a)==[]
# Soft delete the other organization and preserve the user's login/account.
other=org(b,org_b['id'])
call('DELETE',f"/api/v1/admin/organizations/{org_b['id']}?version={other['version']}",token=b,expected=403)
call('DELETE',f"/api/v1/admin/organizations/{org_b['id']}?version=999",token=admin,expected=409)
call('DELETE',f"/api/v1/admin/organizations/{org_b['id']}?version={other['version']}",token=admin,expected=204)
await_closed(org_b['id'],'DELETED')
assert org_b['id'] not in [o['id'] for o in paged('/api/v1/admin/organizations',admin)]
assert call('GET','/api/v1/me/organizations',token=b)==[]
call('PATCH',f"/api/v1/admin/organizations/{org_b['id']}",{'status':'ACTIVE'},admin,404)
assert call('GET','/api/v1/me/membership-notifications',token=a)['unreadCount']>0
print('PASS: scoped requests, rejection/approval, stale review, direct edits, closure, public event visibility, cancelled tickets with preserved history and isolated soft deletion')
