#!/usr/bin/env python3
"""Full regression plus organization isolation and activity-scoped admission. Disposable stack only."""
import runpy
globals().update(runpy.run_path('scripts/editor-acceptance.py'))
# Organization creation is platform-only; global role grants confer no membership.
call('POST','/api/v1/admin/organizations',{'name':'Denied','slug':'denied-'+suffix,'adminEmail':users[0]['email']},a,403)
assert call('GET','/api/v1/me/organizations',token=attendee)==[]
call('POST','/api/v1/organizer/events',{**body,'organizationId':org_b['id']},a,404)
call('GET',f"/api/v1/organizations/{org_a['id']}/members",token=b,expected=403)
# Last admin and optimistic membership versions.
members=call('GET',f"/api/v1/organizations/{org_a['id']}/members",token=a)['items']
owner=next(m for m in members if m['userId']==users[0]['id'])
mp=f"/api/v1/organizations/{org_a['id']}/members/{users[0]['id']}"
call('PUT',mp,{**owner,'role':'MEMBER'},a,409)
call('PUT',mp,{**owner,'version':99},a,409)
# Invite is account-bound, revocable, and replay does not restore revoked membership.
ip=f"/api/v1/organizations/{org_a['id']}/invitations"
invite=call('POST',ip,{'email':users[2]['email'],'role':'MEMBER'},a)
call('POST','/api/v1/invitations/accept',{'token':invite['token']},b,403)
call('DELETE',ip+'/'+invite['id'],token=a,expected=204)
call('POST','/api/v1/invitations/accept',{'token':invite['token']},attendee,409)
invite=call('POST',ip,{'email':users[2]['email'],'role':'MEMBER'},a)
call('POST','/api/v1/invitations/accept',{'token':invite['token']},attendee,204)
call('POST','/api/v1/invitations/accept',{'token':invite['token']},attendee,204)
assert call('GET','/api/v1/me/organizations',token=attendee)[0]['role']=='MEMBER'
# A real internal offering: private in discovery, detail, inventory, pre-registration and booking.
private=call('POST','/api/v1/organizer/events',{**body,'title':'Internal '+suffix,'visibility':'ORGANIZATION_ONLY'},a,201)
pp='/api/v1/organizer/events/'+private['id']
inv=call('PUT',pp+'/ticket-types',{'eventVersion':private['version'],'version':0,'ticketTypes':[{'name':'Members','quota':10,'opensAt':(start-datetime.timedelta(days=8)).isoformat(),'closesAt':start.isoformat()}]},a)
private=call('GET',pp,token=a)
private=call('POST',pp+'/publish',{'version':private['version'],'ticketVersion':inv['version']},a)
pt=inv['ticketTypes'][0]
assert private['id'] not in [e['id'] for e in call('GET','/api/v1/events?keyword='+suffix)['items']]
assert private['id'] in [e['id'] for e in call('GET','/api/v1/events?organizationId='+org_a['id']+'&keyword=Internal',token=attendee)['items']]
for outsider in [None,b,admin]:
 call('GET','/api/v1/events/'+private['id'],token=outsider,expected=404)
 call('GET','/api/v1/events/'+private['id']+'/ticket-types',token=outsider,expected=404)
call('POST','/api/v1/bookings',req(private,pt),b,404)
call('PUT','/api/v1/pre-registrations/'+private['id'],{'ticketTypeId':pt['id'],'quantity':1},b,404)
booked=call('POST','/api/v1/bookings',req(private,pt,2),attendee)
private=call('PUT',pp+'/revision',{**private,'visibility':'PUBLIC'},a)
assert call('GET','/api/v1/events/'+private['id'],token=b)['visibility']=='PUBLIC'
private=call('PUT',pp+'/revision',{**private,'visibility':'ORGANIZATION_ONLY'},a)
call('GET','/api/v1/events/'+private['id'],token=b,expected=404)
assert call('GET','/api/v1/bookings/'+booked['id'],token=attendee)['id']==booked['id']
call('PUT',pp+'/revision',{**private,'organizationId':org_b['id']},a,409)
# Activity-scoped assignment, same organization is insufficient without assignment.
sp=pp+'/staff'
call('POST','/api/v1/events/'+private['id']+'/check-ins',{'credential':booked['tickets'][0]['credential']},a,403)
call('PUT',sp,{'userId':users[1]['id'],'active':True},a,404)
call('PUT',sp,{'userId':users[2]['id'],'active':True},a,204)
assert private['id'] in [t['eventId'] for t in call('GET','/api/v1/me/staff-assignments',token=attendee)]
checkpath='/api/v1/events/'+private['id']+'/check-ins'
# Too early: reject without recording attendance. Then reschedule into the opening window.
call('POST',checkpath,{'credential':booked['tickets'][0]['credential']},attendee,409)
assert call('GET',pp+'/summary',token=a)['attendance']==0
near_start=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=10)
private=call('GET',pp,token=a)
private=call('PUT',pp+'/revision',{**private,'startsAt':near_start.isoformat(),'endsAt':(near_start+datetime.timedelta(hours=1)).isoformat()},a)
with concurrent.futures.ThreadPoolExecutor(8) as pool:
 checks=list(pool.map(lambda _:call('POST',checkpath,{'credential':booked['tickets'][0]['credential']},attendee),range(12)))
assert sum(not c['alreadyCheckedIn'] for c in checks)==1
assert call('GET',pp+'/summary',token=a)['attendance']==1
call('POST','/api/v1/bookings/'+booked['id']+'/cancel',token=attendee,expected=409)
# Wrong-event ticket and other assignment cannot grant entry.
other,ot=offering('Other check-in '+suffix)
ob=call('POST','/api/v1/bookings',req(other,ot),attendee)
call('POST',checkpath,{'credential':ob['tickets'][0]['credential']},attendee,404)
call('POST','/api/v1/events/'+other['id']+'/check-ins',{'credential':ob['tickets'][0]['credential']},attendee,403)
# Remove membership with the existing JWT: all organization-specific grants stop.
member=next(m for m in call('GET',f"/api/v1/organizations/{org_a['id']}/members",token=a)['items'] if m['userId']==users[2]['id'])
memberpath=f"/api/v1/organizations/{org_a['id']}/members/{users[2]['id']}"
call('PUT',memberpath,{**member,'status':'REMOVED'},a,204)
call('GET','/api/v1/events/'+private['id'],token=attendee,expected=404)
call('POST',checkpath,{'credential':booked['tickets'][1]['credential']},attendee,404)
assert call('GET','/api/v1/me/staff-assignments',token=attendee)==[]
call('POST','/api/v1/invitations/accept',{'token':invite['token']},attendee,204)
assert call('GET','/api/v1/me/organizations',token=attendee)==[]
assert call('GET','/api/v1/bookings/'+booked['id'],token=attendee)['id']==booked['id']
# Multi-organization roles and existing token updates.
invite=call('POST',ip,{'email':users[1]['email'],'role':'MEMBER'},a)
call('POST','/api/v1/invitations/accept',{'token':invite['token']},b,204)
roles={o['id']:o['role'] for o in call('GET','/api/v1/me/organizations',token=b)}
assert roles=={org_a['id']:'MEMBER',org_b['id']:'ORG_ADMIN'}
call('GET',pp,token=b,expected=404)
call('PATCH','/api/v1/admin/organizations/'+org_a['id'],{'status':'SUSPENDED'},admin,204)
call('GET',pp,token=a,expected=404)
call('PATCH','/api/v1/admin/organizations/'+org_a['id'],{'status':'ACTIVE'},admin,204)
assert call('GET',pp,token=a)['id']==private['id']
print('PASS: organization provisioning, invitations, membership isolation/revocation, internal offerings, scoped staff, concurrent one-time check-in, attendance and preserved tickets')
