#!/usr/bin/env python3
"""Registration/presentation acceptance, including all booking regression checks."""
import runpy
globals().update(runpy.run_path('scripts/booking-acceptance.py'))
rules={'realName':True,'email':True,'phone':True,'studentId':True,'passport':True,'customFieldLabel':'Dietary needs'}
event=call('POST','/api/v1/organizer/events',{**body,'title':'Workshop details '+suffix,'category':'EDUCATION','cardTheme':'SKY','registrationRequirements':rules},a,201)
assert event['category']=='EDUCATION' and event['cardTheme']=='SKY' and event['registrationRequirements']==rules
ep='/api/v1/organizer/events/'+event['id']
call('POST','/api/v1/organizer/events',{**body,'category':'UNKNOWN'},a,400)
call('POST','/api/v1/organizer/events',{**body,'cardTheme':'UNKNOWN'},a,400)
call('POST','/api/v1/organizer/events',{**body,'registrationRequirements':{**rules,'customFieldLabel':'a'*101}},a,400)
now=datetime.datetime.now(datetime.timezone.utc)
cfg=call('PUT',ep+'/ticket-types',{'eventVersion':event['version'],'version':0,'ticketTypes':[{'name':'General','quota':10,'opensAt':(now-datetime.timedelta(hours=1)).isoformat(),'closesAt':start.isoformat()}]},a)
event=call('GET',ep,token=a)
call('POST',ep+'/publish',{'version':event['version'],'ticketVersion':cfg['version']},a)
public=call('GET','/api/v1/events/'+event['id'])
assert public['category']=='EDUCATION' and public['cardTheme']=='SKY' and public['registrationRequirements']==rules
assert any(e['id']==event['id'] for e in call('GET','/api/v1/events?category=EDUCATION&keyword='+suffix)['items'])
assert not any(e['id']==event['id'] for e in call('GET','/api/v1/events?category=TECH&keyword='+suffix)['items'])
call('GET','/api/v1/events?category=UNKNOWN',expected=400)
request=req(event,cfg['ticketTypes'][0])
info={'realName':'Alice Tan','email':'contact@example.com','phone':'+65 8123 4567','studentId':'A123','passportNumber':'TEST123','customAnswer':'Vegetarian'}
call('POST','/api/v1/bookings',request,attendee,400)
call('POST','/api/v1/bookings',{**request,'attendeeInfo':{**info,'email':'not-an-email'}},attendee,400)
assert availability(event)==10
request['attendeeInfo']=info
booking=call('POST','/api/v1/bookings',request,attendee)
assert booking['attendeeInfo']==info and booking['customFieldLabel']=='Dietary needs'
assert call('POST','/api/v1/bookings',request,attendee)['id']==booking['id']
call('POST','/api/v1/bookings',{**request,'attendeeInfo':{**info,'phone':'different'}},attendee,409)
assert availability(event)==9
orders=call('GET',ep+'/bookings',token=a)
assert orders['items'][0]['attendeeInfo']==info and 'tickets' not in orders['items'][0]
call('GET',ep+'/bookings',token=b,expected=404)
call('GET',ep+'/bookings',token=admin,expected=404)
call('GET',ep+'/bookings',token=attendee,expected=403)
call('GET',ep+'/bookings',expected=401)
event=call('GET',ep,token=a)
call('PUT',ep,{**body,'version':event['version'],'registrationRequirements':{}},a,409)
assert call('GET','/api/v1/bookings/'+booking['id'],token=attendee)['customFieldLabel']=='Dietary needs'
print('PASS: category/theme persistence and filtering, registration validation, information-aware idempotency, private owner registration list and immutable published requirements')
