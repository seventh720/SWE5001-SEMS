#!/usr/bin/env python3
"""Visibility changes after publication. Run only against a disposable stack."""
from acceptance import *
event=call('GET',path,token=a)
inv=call('PUT',path+'/ticket-types',{'eventVersion':event['version'],'version':0,'ticketTypes':[{'name':'General','quota':10,'opensAt':(start-datetime.timedelta(days=8)).isoformat(),'closesAt':start.isoformat()}]},a)
event=call('GET',path,token=a)
event=call('POST',path+'/publish',{'version':event['version'],'ticketVersion':inv['version']},a)
booking={'eventId':event['id'],'ticketTypeId':inv['ticketTypes'][0]['id'],'quantity':1,'requestKey':str(uuid.uuid4())}
booked=call('POST','/api/v1/bookings',booking,attendee)
call('PUT',path+'/revision',{**event,'visibility':'ORGANIZATION_ONLY'},b,404)
old=event
event=call('PUT',path+'/revision',{**event,'title':'Visibility '+suffix,'visibility':'ORGANIZATION_ONLY'},a)
assert event['visibility']=='ORGANIZATION_ONLY' and event['status']=='PUBLISHED'
call('PUT',path+'/revision',{**old,'visibility':'PUBLIC'},a,409)
assert event['id'] not in [e['id'] for e in call('GET','/api/v1/events?keyword='+suffix)['items']]
for outsider in [None,attendee,b]:
 call('GET','/api/v1/events/'+event['id'],token=outsider,expected=404)
 call('GET','/api/v1/events/'+event['id']+'/ticket-types',token=outsider,expected=404)
call('POST','/api/v1/bookings',{**booking,'requestKey':str(uuid.uuid4())},attendee,404)
call('PUT','/api/v1/pre-registrations/'+event['id'],{'ticketTypeId':booking['ticketTypeId'],'quantity':1},attendee,404)
assert call('GET','/api/v1/bookings/'+booked['id'],token=attendee)==booked
assert call('GET','/api/v1/events/'+event['id'],token=a)['visibility']=='ORGANIZATION_ONLY'
event=call('PUT',path+'/revision',{**event,'visibility':'PUBLIC'},a)
assert event['id'] in [e['id'] for e in call('GET','/api/v1/events?keyword='+suffix)['items']]
assert call('GET','/api/v1/events/'+event['id'])['visibility']=='PUBLIC'
call('POST','/api/v1/bookings',{**booking,'requestKey':str(uuid.uuid4())},attendee)
print('PASS: published visibility changes both ways; discovery, detail, inventory and new booking restrictions; existing tickets preserved; outsider and stale edits rejected')
