#!/usr/bin/env python3
"""Terminal cancellation, real PostgreSQL races and outage recovery; disposable stack only."""
from acceptance import *
import subprocess,time
compose=['docker','compose','--env-file',os.environ.get('SEMS_ENV_FILE','.env'),'-f',os.environ.get('SEMS_COMPOSE_FILE','deployment/compose.yaml')]
def sql(query):
 return subprocess.check_output(compose+['exec','-T','postgres','psql','-U','postgres','-d','sems','-At','-c',query],text=True).strip()
def make(paused=False):
 begin=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=10)
 e=call('POST','/api/v1/organizer/events',{**body,'startsAt':begin.isoformat(),'endsAt':(begin+datetime.timedelta(hours=2)).isoformat(),'capacity':200},a,201)
 p='/api/v1/organizer/events/'+e['id']
 inv=call('PUT',p+'/ticket-types',{'eventVersion':e['version'],'version':0,'ticketTypes':[{'name':'General','quota':180,'opensAt':(begin-datetime.timedelta(days=1)).isoformat(),'closesAt':begin.isoformat()},{'name':'Later','quota':20,'opensAt':(begin-datetime.timedelta(minutes=2)).isoformat(),'closesAt':begin.isoformat()}]},a)
 e=call('GET',p,token=a);e=call('POST',p+'/publish',{'version':e['version'],'ticketVersion':inv['version']},a)
 call('PUT',p+'/staff',{'userId':users[0]['id'],'active':True},a,204)
 if paused:e=call('PUT',p+'/revision',{**e,'publicationStatus':'PAUSED'},a)
 return e,p,inv

def book(e,inv,quantity=1):
 return call('POST','/api/v1/bookings',{'eventId':e['id'],'ticketTypeId':inv['ticketTypes'][0]['id'],'quantity':quantity,'requestKey':str(uuid.uuid4())},attendee)
def status(method,path,body=None,token=attendee):
 req=urllib.request.Request(BASE+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token},method=method)
 try:
  with urllib.request.urlopen(req,timeout=30) as r:return r.status
 except urllib.error.HTTPError as r:return r.code

e,p,inv=make();eid=e['id'];mixed=book(e,inv,2);ordinary=book(e,inv)
call('PUT','/api/v1/pre-registrations/'+eid,{'ticketTypeId':inv['ticketTypes'][1]['id'],'quantity':1},b)
call('POST',f'/api/v1/events/{eid}/check-ins',{'credential':mixed['tickets'][0]['credential']},a)
request={'version':e['version'],'reason':'Venue unavailable'}
call('POST',p+'/cancel',request,b,404);call('POST',p+'/cancel',request,attendee,404)
call('POST',p+'/cancel',{**request,'version':e['version']+100},a,409)
call('POST',p+'/cancel',{**request,'reason':'   '},a,400)
# Different instances compete for the same sales row. A reservation/check-in can win
# before cancellation, but cancellation must leave no active booking or valid ticket.
jobs=[('POST','/api/v1/bookings',{'eventId':eid,'ticketTypeId':inv['ticketTypes'][0]['id'],'quantity':1,'requestKey':str(uuid.uuid4())},attendee) for _ in range(100)]
jobs += [('POST',f'/api/v1/events/{eid}/check-ins',{'credential':mixed['tickets'][1]['credential']},a),('POST','/api/v1/bookings/'+ordinary['id']+'/cancel',None,attendee)]
jobs += [('POST',p+'/cancel',request,a)]*6
with concurrent.futures.ThreadPoolExecutor(16) as pool:codes=list(pool.map(lambda j:status(*j),jobs))
assert all(code in [200,202,404,409] for code in codes),codes
for _ in range(30):
 if call('GET',p,token=a)['status']=='CANCELLED':break
 time.sleep(1)
else:raise AssertionError('Cancellation did not complete')
assert sql(f"SELECT state FROM admission.sales WHERE event_id='{eid}'")=='CANCELLED'
assert sql(f"SELECT count(*) FROM admission.bookings WHERE event_id='{eid}' AND status='CONFIRMED'")=='0'
assert sql(f"SELECT count(*) FROM admission.tickets t JOIN admission.bookings b ON b.id=t.booking_id WHERE b.event_id='{eid}' AND t.state='VALID'")=='0'
assert sql(f"SELECT sum(reserved) FROM admission.ticket_types WHERE event_id='{eid}'")=='0'
assert sql(f"SELECT count(*) FROM admission.event_cancellation_receipts WHERE event_id='{eid}'")=='1'
checked=call('GET','/api/v1/bookings/'+mixed['id'],token=attendee)
assert checked['status']=='CANCELLED' and checked['eventCancellationReason']==request['reason']
assert checked['tickets'][0]['state']=='CHECKED_IN'
call('POST',f'/api/v1/events/{eid}/check-ins',{'credential':mixed['tickets'][0]['credential']},a,409)
call('POST',f'/api/v1/events/{eid}/check-ins',{'credential':mixed['tickets'][1]['credential']},a,409)
call('GET','/api/v1/events/'+eid,expected=404)
call('POST','/api/v1/bookings',{'eventId':eid,'ticketTypeId':inv['ticketTypes'][0]['id'],'quantity':1,'requestKey':str(uuid.uuid4())},attendee,404)
assert eid not in [t['eventId'] for t in call('GET','/api/v1/me/staff-assignments',token=a)["items"]]
summary=call('GET',p+'/summary',token=a)
assert summary['salesState']=='CANCELLED' and summary['availableCapacity']==0 and summary['confirmedTickets']==0 and summary['attendance']>=1
assert all(t['available']==0 for t in call('GET',p+'/ticket-types',token=a)['ticketTypes'])
assert call('GET','/api/v1/pre-registrations/'+eid,token=b)['status']=='CLOSED'
call('PUT',p+'/staff',{'userId':users[0]['id'],'active':True},a,409)
terminal=call('GET',p,token=a)
call('PUT',p+'/revision',{**terminal,'publicationStatus':'PUBLISHED'},a,409)
call('POST',p+'/publish',{'version':terminal['version'],'ticketVersion':inv['version']},a,409)
call('POST',p+'/cancel',{**request,'reason':'Different request'},a,409)
notices=sql(f"SELECT count(*) FROM admission.notifications WHERE kind='EVENT_CANCELLED' AND (dedup_key LIKE 'event-cancel:%' AND link IN (SELECT '/bookings/'||id FROM admission.bookings WHERE event_id='{eid}') OR dedup_key='event-cancel-saved:{eid}')")
assert int(notices)>=2
for _ in range(3):call('POST',p+'/cancel',request,a)
assert sql(f"SELECT count(*) FROM admission.notifications WHERE kind='EVENT_CANCELLED' AND (dedup_key LIKE 'event-cancel:%' AND link IN (SELECT '/bookings/'||id FROM admission.bookings WHERE event_id='{eid}') OR dedup_key='event-cancel-saved:{eid}')")==notices
print('PASS: cancellation permissions/version, double-instance booking/check-in/personal-cancel races, ticket invalidation, checked-in history, closed pre-registration, deduplicated notifications and terminal guards')
# Paused event cancellation; a pause alone leaves bookings valid.
paused,pp,pi=make();pb=book(paused,pi);paused=call('PUT',pp+'/revision',{**paused,'publicationStatus':'PAUSED'},a)
assert call('GET','/api/v1/bookings/'+pb['id'],token=attendee)['status']=='CONFIRMED'
assert call('POST',pp+'/cancel',{'version':paused['version'],'reason':'Paused event cancelled'},a)['status']=='CANCELLED'
print('PASS: pause preserves tickets; whole-event cancellation invalidates them')
# Inject a late transaction failure after ticket/order/notice writes. No partial
# Admission effect may escape; durable Catalog intent must complete after repair.
fault,fp,fi=make();fb=book(fault,fi);fid=fault['id']
sql(f"""CREATE FUNCTION admission.reject_test_cancellation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.event_id='{fid}'::uuid THEN RAISE EXCEPTION 'Injected cancellation failure'; END IF; RETURN NEW; END $$;
CREATE TRIGGER reject_test_cancellation BEFORE INSERT ON admission.event_cancellation_receipts FOR EACH ROW EXECUTE FUNCTION admission.reject_test_cancellation();""")
try:
 assert call('POST',fp+'/cancel',{'version':fault['version'],'reason':'Atomic rollback test'},a,202)['status']=='CANCELLING'
 assert sql(f"SELECT state FROM admission.sales WHERE event_id='{fid}'")=='ACTIVE'
 assert call('GET','/api/v1/bookings/'+fb['id'],token=attendee)['status']=='CONFIRMED'
 assert sql(f"SELECT count(*) FROM admission.notifications WHERE dedup_key='event-cancel:{fb['id']}'")=='0'
finally:
 sql("DROP TRIGGER reject_test_cancellation ON admission.event_cancellation_receipts; DROP FUNCTION admission.reject_test_cancellation();")
for _ in range(20):
 if call('GET',fp,token=a)['status']=='CANCELLED':break
 time.sleep(1)
else:raise AssertionError('Transaction failure did not recover')
assert call('GET','/api/v1/bookings/'+fb['id'],token=attendee)['status']=='CANCELLED'
print('PASS: late transaction failure rolls back all effects and recovers after repair')
# Durable request survives unavailable Admission AND a Catalog process restart.
recovery,rp,ri=make();rb=book(recovery,ri);rr={'version':recovery['version'],'reason':'Recovery scenario'}
try:
 subprocess.run(compose+['stop','admission'],check=True,stdout=subprocess.DEVNULL)
 assert call('POST',p+'/cancel',request,a)['status']=='CANCELLED'
 assert call('POST',rp+'/cancel',rr,a,202)['status']=='CANCELLING'
 call('GET','/api/v1/events/'+recovery['id'],expected=404)
 subprocess.run(compose+['restart','event-catalog'],check=True,stdout=subprocess.DEVNULL)
finally:
 subprocess.run(compose+['start','admission'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(compose+['restart','gateway'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['bash','scripts/smoke.sh'],check=True)
for _ in range(45):
 try:
  if call('GET',rp,token=a)['status']=='CANCELLED':break
 except (AssertionError,urllib.error.URLError):pass
 time.sleep(2)
else:raise AssertionError('Durable cancellation did not recover')
assert call('GET','/api/v1/bookings/'+rb['id'],token=attendee)['status']=='CANCELLED'
# Simulate crash AFTER Admission commits but BEFORE Catalog acknowledges.
# Only the disposable fixture rewinds the Catalog acknowledgement; the Admission
# receipt remains intact, proving replay does not recreate tickets or notifications.
sql(f"UPDATE catalog.events SET status='CANCELLING' WHERE id='{recovery['id']}'; UPDATE catalog.event_cancellations SET completed_at=NULL WHERE event_id='{recovery['id']}';")
for _ in range(20):
 if call('GET',rp,token=a)['status']=='CANCELLED':break
 time.sleep(1)
else:raise AssertionError('Lost acknowledgement did not recover')
assert sql(f"SELECT count(*) FROM admission.notifications WHERE dedup_key='event-cancel:{rb['id']}'")=='1'
assert sql(f"SELECT sum(reserved) FROM admission.ticket_types WHERE event_id='{recovery['id']}'")=='0'
print('PASS: Admission outage, Catalog restart, automatic recovery, lost acknowledgement and replay without duplicate effects')
