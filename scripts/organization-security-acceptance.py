#!/usr/bin/env python3
"""Focused invitation expiry, revoked assignment, live role and task-title checks."""
from acceptance import *
import subprocess
compose=['docker','compose','--env-file',os.environ.get('SEMS_ENV_FILE','.env'),'-f',os.environ.get('SEMS_COMPOSE_FILE','deployment/compose.yaml')]
ip=f"/api/v1/organizations/{org_a['id']}/invitations"
invite=call('POST',ip,{'email':users[2]['email'],'role':'MEMBER'},a)
subprocess.run(compose+['exec','-T','postgres','psql','-U','postgres','-d','sems','-c',f"UPDATE identity.organization_invitations SET expires_at=now()-interval '1 second' WHERE id='{invite['id']}'"],check=True,stdout=subprocess.DEVNULL)
call('POST','/api/v1/invitations/accept',{'token':invite['token']},attendee,409)
invite=call('POST',ip,{'email':users[2]['email'],'role':'ORGANIZER'},a)
call('POST','/api/v1/invitations/accept',{'token':invite['token']},attendee,204)
# Existing attendee token gains organization role without a fresh login.
assert call('GET',path,token=attendee)['id']==draft['id']
event=call('GET',path,token=a)
inv=call('PUT',path+'/ticket-types',{'eventVersion':event['version'],'version':0,'ticketTypes':[{'name':'General','quota':10,'opensAt':(start-datetime.timedelta(days=8)).isoformat(),'closesAt':start.isoformat()}]},a)
call('PUT',path+'/staff',{'userId':users[2]['id'],'active':True},a,204)
# Assigned draft with zero bookings still has a meaningful current title.
tasks=call('GET','/api/v1/me/staff-assignments',token=attendee)["items"]
matching=[t for t in tasks if t['eventId']==event['id']]
assert len(matching)==1, f'Assigned draft must remain visible before publication: {tasks}'
assert matching[0]['title']==event['title']
event=call('GET',path,token=a)
event=call('POST',path+'/publish',{'version':event['version'],'ticketVersion':inv['version']},a)
call('PATCH',path+'/presentation',{'title':'Current staff task title','description':event['description'],'location':event['location'],'category':event['category'],'cardTheme':event['cardTheme'],'version':event['version']},a)
assert call('GET','/api/v1/me/staff-assignments',token=attendee)["items"][0]['title']=='Current staff task title'
booked=call('POST','/api/v1/bookings',{'eventId':event['id'],'ticketTypeId':inv['ticketTypes'][0]['id'],'quantity':1,'requestKey':str(uuid.uuid4())},attendee)
call('PUT',path+'/staff',{'userId':users[2]['id'],'active':False},a,204)
assert call('GET','/api/v1/me/staff-assignments',token=attendee)["items"]==[]
call('POST','/api/v1/events/'+event['id']+'/check-ins',{'credential':booked['tickets'][0]['credential']},attendee,403)
mp=f"/api/v1/organizations/{org_a['id']}/members/{users[2]['id']}"
member=next(m for m in call('GET',f"/api/v1/organizations/{org_a['id']}/members",token=a)['items'] if m['userId']==users[2]['id'])
call('PUT',mp,{**member,'role':'MEMBER'},a,204)
call('GET',path,token=attendee,expected=404)
assert call('GET','/api/v1/bookings/'+booked['id'],token=attendee)['id']==booked['id']
# Platform admin has no implicit business privileges, despite ability to appoint admins.
call('GET',path+'/bookings',token=admin,expected=404)
print('PASS: invitation expiry, live promotion/demotion, assigned task title before bookings and after edits, staff revocation and platform-admin isolation')
