#!/usr/bin/env python3
"""Disposable Compose acceptance. Includes publication regression and creates test data."""
import runpy
# Reuse the same real users and events without relying on another script's process state.
globals().update(runpy.run_path('scripts/publication-acceptance.py'))

def offering(title,quota=10,opens=None,closes=None):
    event=call('POST','/api/v1/organizer/events',{**body,'title':title,'capacity':quota},a,201)
    ep='/api/v1/organizer/events/'+event['id']
    cfg=call('PUT',ep+'/ticket-types',{'eventVersion':event['version'],'version':0,'ticketTypes':[
        {'name':'General','quota':quota,'opensAt':(opens or (datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(hours=1))).isoformat(),'closesAt':(closes or start).isoformat()}]},a)
    event=call('GET',ep,token=a)
    call('POST',ep+'/publish',{'version':event['version'],'ticketVersion':cfg['version']},a)
    return event,cfg['ticketTypes'][0]

def req(event,ticket,quantity=1,key=None):
    return {'eventId':event['id'],'ticketTypeId':ticket['id'],'quantity':quantity,'requestKey':key or str(uuid.uuid4())}
def availability(event):return call('GET','/api/v1/events/'+event['id']+'/ticket-types')['ticketTypes'][0]['available']

event,ticket=offering('Booking acceptance '+suffix)
request=req(event,ticket,2)
call('POST','/api/v1/bookings',request,expected=401)
call('POST','/api/v1/bookings',{**request,'quantity':0},attendee,400)
call('POST','/api/v1/bookings',{**request,'quantity':11},attendee,400)
call('POST','/api/v1/bookings',{**request,'requestKey':None},attendee,400)
booking=call('POST','/api/v1/bookings',request,attendee)
assert booking['quantity']==2 and booking['amount']==0 and booking['status']=='CONFIRMED'
assert len(booking['tickets'])==2 and len({t['credential'] for t in booking['tickets']})==2
assert all(t['state']=='VALID' for t in booking['tickets']) and availability(event)==8
bp='/api/v1/bookings/'+booking['id']
assert call('POST','/api/v1/bookings',request,attendee)==booking
call('POST','/api/v1/bookings',{**request,'quantity':1},attendee,409)
call('GET',bp,token=b,expected=404)
call('POST',bp+'/cancel',token=b,expected=404)
assert call('GET','/api/v1/bookings',token=b)['totalElements']==0
call('GET','/api/v1/bookings?size=51',token=attendee,expected=400)
assert call('GET','/api/v1/bookings',token=attendee)['items'][0]['id']==booking['id']
# A committed request remains retrievable if Catalog is temporarily unavailable.
try:
    subprocess.run(compose+['stop','event-catalog'],check=True,stdout=subprocess.DEVNULL)
    replay=call('POST','/api/v1/bookings',request,attendee)
    assert replay['currentEvent'] is None
    assert {k:v for k,v in replay.items() if k!='currentEvent'}=={k:v for k,v in booking.items() if k!='currentEvent'}
finally:
    subprocess.run(compose+['start','event-catalog'],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(compose+['restart','gateway'],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['bash','scripts/smoke.sh'],check=True)
with concurrent.futures.ThreadPoolExecutor(8) as pool:
    cancelled=list(pool.map(lambda _:call('POST',bp+'/cancel',token=attendee),range(8)))
assert all(x['status']=='CANCELLED' and all(t['state']=='CANCELLED' for t in x['tickets']) for x in cancelled)
assert availability(event)==10
assert call('POST','/api/v1/bookings',request,attendee)['status']=='CANCELLED'
assert availability(event)==10
# Same request submitted concurrently: one booking, one reservation, one credential.
request=req(event,ticket)
with concurrent.futures.ThreadPoolExecutor(10) as pool:
    same=list(pool.map(lambda _:call('POST','/api/v1/bookings',request,attendee),range(20)))
assert len({x['id'] for x in same})==1 and availability(event)==9
call('POST','/api/v1/bookings/'+same[0]['id']+'/cancel',token=attendee)
assert availability(event)==10
print('PASS: ownership, request validation, per-place credentials, safe retries during Catalog outage, concurrent cancellation and same-key submission')
# Different requests contest the final ten places.
requests=[req(event,ticket) for _ in range(100)]
def compete(request):
    r=urllib.request.Request(BASE+'/api/v1/bookings',data=json.dumps(request).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+attendee},method='POST')
    try:
        with urllib.request.urlopen(r,timeout=30) as response:return response.status,json.loads(response.read())
    except urllib.error.HTTPError as e:return e.code,None
with concurrent.futures.ThreadPoolExecutor(20) as pool:results=list(pool.map(compete,requests))
assert [r[0] for r in results].count(200)==10 and [r[0] for r in results].count(409)==90, [r[0] for r in results]
assert availability(event)==0
assert len({r[1]['tickets'][0]['credential'] for r in results if r[0]==200})==10
# Inspect the persisted invariant independently of the API projection.
query=f"SELECT t.reserved, (SELECT COALESCE(sum(b.quantity),0) FROM admission.bookings b WHERE b.ticket_type_id=t.id AND b.status='CONFIRMED'), (SELECT count(*) FROM admission.tickets k JOIN admission.bookings b ON b.id=k.booking_id WHERE b.ticket_type_id=t.id AND k.state='VALID') FROM admission.ticket_types t WHERE t.id='{ticket['id']}'"
persisted=subprocess.check_output(compose+['exec','-T','postgres','psql','-U','postgres','-d','sems','-Atc',query],text=True).strip()
assert persisted=='10|10|10',persisted
future,ft=offering('Future sales '+suffix,opens=start-datetime.timedelta(hours=1))
call('POST','/api/v1/bookings',req(future,ft),attendee,409)
closed,ct=offering('Closed sales '+suffix,closes=datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(minutes=1))
call('POST','/api/v1/bookings',req(closed,ct),attendee,409)
call('POST','/api/v1/bookings',req(future,ticket),attendee,404)
# Seed checked-in/start-time conditions to test cancellation guards before staff UI exists.
win=next(r[1] for r in results if r[0]==200)
subprocess.run(compose+['exec','-T','postgres','psql','-U','postgres','-d','sems','-c',f"UPDATE admission.tickets SET state='CHECKED_IN',checked_in_at=now() WHERE booking_id='{win['id']}'"],check=True,stdout=subprocess.DEVNULL)
call('POST','/api/v1/bookings/'+win['id']+'/cancel',token=attendee,expected=409)
other=next(r[1] for r in results if r[0]==200 and r[1]['id']!=win['id'])
subprocess.run(compose+['exec','-T','postgres','psql','-U','postgres','-d','sems','-c',f"UPDATE admission.bookings SET starts_at=now()-interval '1 minute' WHERE id='{other['id']}'"],check=True,stdout=subprocess.DEVNULL)
call('POST','/api/v1/bookings/'+other['id']+'/cancel',token=attendee,expected=409)
assert availability(event)==0
print('PASS: 100 requests/10 places, database inventory-booking-ticket invariants, sales windows, wrong-event ticket and cancellation guards')

# Status filtering must apply before pagination, including totals and owner scope.
all_rows=call('GET','/api/v1/bookings?size=50',token=attendee)
for status in ('CONFIRMED','CANCELLED'):
    expected=[row for row in all_rows['items'] if row['status']==status]
    filtered=call('GET','/api/v1/bookings?status='+status+'&size=1',token=attendee)
    assert filtered['totalElements']==len(expected) and filtered['totalPages']==len(expected)
    assert all(row['status']==status for row in filtered['items'])
    if len(expected)>1:
        second=call('GET','/api/v1/bookings?status='+status+'&size=1&page=1',token=attendee)
        assert second['items'][0]['id']!=filtered['items'][0]['id']
    assert call('GET','/api/v1/bookings?status='+status,token=b)['totalElements']==0
call('GET','/api/v1/bookings?status=UNKNOWN',token=attendee,expected=400)
print('PASS: booking status filters, pagination totals, separate pages and owner isolation')
