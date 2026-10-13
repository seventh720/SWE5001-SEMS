#!/usr/bin/env python3
"""Profile and pre-registration lifecycle against disposable PostgreSQL containers."""
import runpy
globals().update(runpy.run_path('scripts/registration-acceptance.py'))
profile={'realName':'Saved Person','email':'saved@example.com','phone':'+65 1234 5678','studentId':'TEST','passportNumber':'SYNTHETIC'}
call('GET','/api/v1/profile',expected=401)
assert call('PUT','/api/v1/profile',profile,attendee)==profile
assert call('GET','/api/v1/profile',token=attendee)==profile
assert all(v is None for v in call('GET','/api/v1/profile',token=b).values())
call('PUT','/api/v1/profile',{**profile,'email':'invalid'},attendee,400)
call('PUT','/api/v1/profile',{**profile,'realName':'x'*101},attendee,400)
future,ft=offering('Pre-registration '+suffix,quota=3,opens=start-datetime.timedelta(hours=1))
pp='/api/v1/pre-registrations/'+future['id']
payload={'ticketTypeId':ft['id'],'quantity':2,'attendeeInfo':{}}
call('PUT',pp,payload,expected=401)
call('PUT',pp,{**payload,'quantity':4},attendee,400)
call('PUT',pp,{**payload,'ticketTypeId':ticket['id']},attendee,404)
call('PUT',pp,{**payload,'attendeeInfo':profile},attendee,400)
saved=call('PUT',pp,payload,attendee)
assert saved['status']=='WAITING' and saved['quantity']==2 and availability(future)==3
assert call('PUT',pp,payload,attendee)['eventId']==future['id']
call('GET',pp,token=b,expected=404)
assert call('GET','/api/v1/pre-registrations',token=b)['totalElements']==0
call('DELETE',pp,token=b,expected=204)
assert call('GET',pp,token=attendee)['quantity']==2
call('GET','/api/v1/pre-registrations?size=51',token=attendee,expected=400)
# Test clock transition through the database in this disposable stack only.
subprocess.run(compose+['exec','-T','postgres','psql','-U','postgres','-d','sems','-c',f"UPDATE admission.ticket_types SET opens_at=now()-interval '1 second' WHERE id='{ft['id']}'"],check=True,stdout=subprocess.DEVNULL)
assert call('GET',pp,token=attendee)['status']=='READY'
assert availability(future)==3 # opening never creates a booking automatically
call('PUT',pp,payload,attendee,409)
confirmed=call('POST','/api/v1/bookings',req(future,ft,2),attendee)
assert confirmed['quantity']==2 and availability(future)==1
call('GET',pp,token=attendee,expected=404)
assert call('GET','/api/v1/pre-registrations',token=attendee)['totalElements']==0
call('DELETE','/api/v1/profile',token=attendee,expected=204)
assert all(v is None for v in call('GET','/api/v1/profile',token=attendee).values())
print('PASS: profile persistence/privacy/validation, pre-registration upsert and ownership, unchanged inventory, opening transition, explicit confirmation and atomic cleanup')
