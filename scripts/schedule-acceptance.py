#!/usr/bin/env python3
"""Local/CI disposable acceptance for recoverable schedule/capacity revision."""
import runpy
globals().update(runpy.run_path('scripts/workspace-acceptance.py'))
event,ticket=offering('Reschedule '+suffix)
ep='/api/v1/organizer/events/'+event['id'];event=call('GET',ep,token=a)
booking=call('POST','/api/v1/bookings',req(event,ticket,2),attendee)
new_start=start+datetime.timedelta(days=1);new_end=new_start+datetime.timedelta(hours=3)
change={**event,'startsAt':new_start.isoformat(),'endsAt':new_end.isoformat(),'capacity':20}
call('PUT',ep+'/revision',change,b,404)
call('PUT',ep+'/revision',change,attendee,403)
updated=call('PUT',ep+'/revision',change,a)
assert updated['status']=='PUBLISHED' and updated['capacity']==20
assert datetime.datetime.fromisoformat(updated['startsAt'].replace('Z','+00:00'))==new_start
stored=call('GET','/api/v1/bookings/'+booking['id'],token=attendee)
assert stored['startsAt']==updated['startsAt'] and stored['endsAt']==updated['endsAt']
sales=call('GET',ep+'/ticket-types',token=a)['ticketTypes'][0]
assert datetime.datetime.fromisoformat(sales['opensAt'].replace('Z','+00:00'))-datetime.datetime.fromisoformat(ticket['opensAt'].replace('Z','+00:00'))==datetime.timedelta(days=1)
assert sales['available']==8
call('PUT',ep+'/revision',change,a,409)
call('PUT',ep+'/revision',{**updated,'capacity':9},a,409)
after=call('GET',ep,token=a)
assert after['status']=='PUBLISHED' and after['capacity']==20 and after['startsAt']==updated['startsAt']
call('PUT',ep+'/revision',{**after,'registrationRequirements':{'realName':True}},a,409)
# Pending intent survives both Catalog restart and Admission outage. Retry must not shift twice.
change={**after,'startsAt':(new_start+datetime.timedelta(days=1)).isoformat(),'endsAt':(new_end+datetime.timedelta(days=1)).isoformat(),'capacity':25}
try:
 subprocess.run(compose+['stop','admission'],check=True,stdout=subprocess.DEVNULL)
 pending=call('PUT',ep+'/revision',change,a)
 assert pending['status']=='UPDATING'
 call('GET','/api/v1/events/'+event['id'],expected=404)
 assert call('PUT',ep+'/revision',change,a)['status']=='UPDATING'
 subprocess.run(compose+['restart','event-catalog'],check=True,stdout=subprocess.DEVNULL)
finally:
 subprocess.run(compose+['start','admission'],check=True,stdout=subprocess.DEVNULL)
 subprocess.run(compose+['restart','gateway'],check=True,stdout=subprocess.DEVNULL)
 subprocess.run(['bash','scripts/smoke.sh'],check=True)
for _ in range(20):
 final=call('GET',ep,token=a)
 if final['status']=='PUBLISHED':break
 time.sleep(1)
assert final['status']=='PUBLISHED' and final['capacity']==25
final_ticket=call('GET',ep+'/ticket-types',token=a)['ticketTypes'][0]
assert datetime.datetime.fromisoformat(final_ticket['opensAt'].replace('Z','+00:00'))-datetime.datetime.fromisoformat(ticket['opensAt'].replace('Z','+00:00'))==datetime.timedelta(days=2)
assert call('GET','/api/v1/bookings/'+booking['id'],token=attendee)['startsAt']==final['startsAt']
call('POST','/api/v1/bookings',req(final,final_ticket),attendee,409) # shifted opening remains in the future
# Draft with configured tickets uses the same revision path.
draft=call('POST','/api/v1/organizer/events',body,a,201);dp='/api/v1/organizer/events/'+draft['id']
call('PUT',dp+'/ticket-types',{'eventVersion':draft['version'],'version':0,'ticketTypes':[{'name':'General','quota':10,'opensAt':(start-datetime.timedelta(days=1)).isoformat(),'closesAt':start.isoformat()}]},a)
draft=call('GET',dp,token=a)
revised=call('PUT',dp+'/revision',{**draft,'capacity':35,'startsAt':new_start.isoformat(),'endsAt':new_end.isoformat()},a)
assert revised['status']=='DRAFT' and revised['capacity']==35
print('PASS: editable schedule/capacity, unchanged inventory and locked requirements, updated confirmed tickets/sales windows, rejection rollback, owner isolation, retry and restart/outage recovery')
