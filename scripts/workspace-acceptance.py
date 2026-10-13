#!/usr/bin/env python3
import runpy
globals().update(runpy.run_path('scripts/pre-registration-acceptance.py'))
# A published offering can change presentation without changing the admission contract.
event,ticket=offering('Editable offering '+suffix)
ep='/api/v1/organizer/events/'+event['id']
event=call('GET',ep,token=a)
old_booking=call('POST','/api/v1/bookings',req(event,ticket),attendee)
change={'title':'Updated offering '+suffix,'description':'Updated public details','location':'New training venue','category':'EDUCATION','cardTheme':'SKY','version':event['version']}
call('PATCH',ep+'/presentation',change,b,404)
call('PATCH',ep+'/presentation',change,attendee,403)
updated=call('PATCH',ep+'/presentation',change,a)
assert updated['status']=='PUBLISHED' and updated['startsAt']==event['startsAt'] and updated['capacity']==event['capacity']
assert updated['registrationRequirements']==event['registrationRequirements']
call('PATCH',ep+'/presentation',change,a,409)
assert call('GET','/api/v1/events/'+event['id'])['location']=='New training venue'
assert call('GET','/api/v1/bookings/'+old_booking['id'],token=attendee)['eventLocation']==event['location']
new_booking=call('POST','/api/v1/bookings',req(event,ticket),attendee)
assert new_booking['eventLocation']=='New training venue'
upcoming=call('GET','/api/v1/bookings/upcoming',token=attendee)
assert all(b['status']=='CONFIRMED' for b in upcoming['items'])
assert [b['startsAt'] for b in upcoming['items']]==sorted(b['startsAt'] for b in upcoming['items'])
assert call('GET','/api/v1/bookings/upcoming',token=b)['totalElements']==0
call('GET','/api/v1/bookings/upcoming',expected=401)
# Template reuse sends reviewed content to the normal draft API, never reuses sales or bookings.
template=call('POST','/api/v1/organizer/events',{**body,'title':updated['title']+' copy','description':updated['description'],'location':updated['location'],'category':updated['category'],'cardTheme':updated['cardTheme'],'registrationRequirements':updated['registrationRequirements']},a,201)
assert template['status']=='DRAFT' and template['id']!=event['id'] and not template['salesConfigured']
call('GET','/api/v1/events/'+template['id'],expected=404)
print('PASS: published presentation ownership/version checks, unchanged ticket contract and historical snapshots, upcoming dashboard privacy/order, independent draft template reuse')
