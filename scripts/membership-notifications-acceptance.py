#!/usr/bin/env python3
"""Organization role notification acceptance; disposable stack only."""
from acceptance import *
base='/api/v1/me/membership-notifications'
def inbox(token): return call('GET',base,token=token)
# Provisioning assigns the initial organization admin in the same transaction.
first=inbox(a)
assert first['unreadCount']==1 and 'Organization administrator' in first['items'][0]['message']
assert first['items'][0]['link'].endswith(org_a['id'])
call('GET',base,expected=401)
call('GET',base+'?page=-1',token=a,expected=400)
call('POST',base+'/'+first['items'][0]['id']+'/read',token=b,expected=404)
# No duplicate on repeated platform appointment with unchanged role/status.
call('PATCH','/api/v1/admin/organizations/'+org_a['id'],{'adminEmail':users[0]['email']},admin,204)
assert len(inbox(a)['items'])==1
ip='/api/v1/organizations/'+org_a['id']+'/invitations'
i=call('POST',ip,{'email':users[2]['email'],'role':'MEMBER'},a)
call('POST','/api/v1/invitations/accept',{'token':i['token']},attendee,204)
call('POST','/api/v1/invitations/accept',{'token':i['token']},attendee,204)
assert len(inbox(attendee)['items'])==1
mp='/api/v1/organizations/'+org_a['id']+'/members'
def member():return next(m for m in call('GET',mp,token=a)['items'] if m['userId']==users[2]['id'])
m=member()
call('PUT',mp+'/'+m['userId'],{**m,'role':'ORGANIZER'},a,204)
notices=inbox(attendee)
assert notices['unreadCount']==2 and 'Event organizer' in notices['items'][0]['message']
# Stale writes and no-op saves produce no additional notifications.
call('PUT',mp+'/'+m['userId'],{**m,'role':'ORG_ADMIN'},a,409)
m=member();call('PUT',mp+'/'+m['userId'],m,a,204)
assert len(inbox(attendee)['items'])==2
m=member();call('PUT',mp+'/'+m['userId'],{**m,'status':'REMOVED'},a,204)
assert 'removed' in inbox(attendee)['items'][0]['message']
assert call('GET','/api/v1/me/organizations',token=attendee)==[]
# Historical notices remain owned by the user after removal.
notice=inbox(attendee)['items'][0]
call('POST',base+'/'+notice['id']+'/read',token=attendee,expected=204)
call('POST',base+'/'+notice['id']+'/read',token=attendee,expected=204)
assert inbox(attendee)['unreadCount']==2
call('POST',base+'/read-all',token=attendee,expected=204)
assert call('GET',base+'/unread-count',token=attendee)==0
assert inbox(a)['unreadCount']==1
# Reappointment after removal creates one new administrator notification.
call('PATCH','/api/v1/admin/organizations/'+org_a['id'],{'adminEmail':users[2]['email']},admin,204)
assert inbox(attendee)['unreadCount']==1 and 'Organization administrator' in inbox(attendee)['items'][0]['message']
assert inbox(attendee)['items'][0]['id']!=notice['id']
print('PASS: initial appointment, invitation acceptance, role/status changes, no-op/stale suppression, recipient isolation and read state')
