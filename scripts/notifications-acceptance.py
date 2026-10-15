#!/usr/bin/env python3
"""In-app notifications acceptance. Disposable environment only."""
from acceptance import *
import subprocess,time
compose=['docker','compose','--env-file',os.environ.get('SEMS_ENV_FILE','.env'),'-f',os.environ.get('SEMS_COMPOSE_FILE','deployment/compose.yaml')]
def sql(statement):
 return subprocess.check_output(compose+['exec','-T','postgres','psql','-U','postgres','-d','sems','-At','-v','ON_ERROR_STOP=1'],input=statement,text=True).strip()
def notices(token=attendee):return call('GET','/api/v1/me/notifications',token=token)['items']
def wait_for(predicate,seconds=25):
 until=time.monotonic()+seconds
 while time.monotonic()<until:
  if predicate():return
  time.sleep(.5)
 raise AssertionError('Timed out waiting for notification')
ip='/api/v1/organizations/'+org_a['id']+'/invitations'
invite=call('POST',ip,{'email':users[2]['email'],'role':'MEMBER'},a)
call('POST',ip,{'email':users[2]['email'],'role':'MEMBER'},a,409)
inbox=call('GET','/api/v1/me/invitations',token=attendee)
assert inbox['pendingCount']==1 and inbox['items'][0]['id']==invite['id']
call('POST','/api/v1/me/invitations/'+invite['id']+'/accept',token=b,expected=404)
call('POST','/api/v1/me/invitations/'+invite['id']+'/decline',token=attendee,expected=204)
assert call('GET','/api/v1/me/invitations/pending-count',token=attendee)==0
invite=call('POST',ip,{'email':users[2]['email'],'role':'MEMBER'},a)
call('POST','/api/v1/me/invitations/'+invite['id']+'/accept',token=attendee,expected=204)
call('POST','/api/v1/invitations/accept',{'token':invite['token']},attendee,204)
assert call('GET','/api/v1/me/invitations/pending-count',token=attendee)==0
event=call('GET',path,token=a)
inv=call('PUT',path+'/ticket-types',{'eventVersion':event['version'],'version':0,'ticketTypes':[{'name':'General','quota':10,'opensAt':(start-datetime.timedelta(days=8)).isoformat(),'closesAt':start.isoformat()}]},a)
event=call('GET',path,token=a)
event=call('POST',path+'/publish',{'version':event['version'],'ticketVersion':inv['version']},a)
request={'eventId':event['id'],'ticketTypeId':inv['ticketTypes'][0]['id'],'quantity':1,'requestKey':str(uuid.uuid4())}
booked=call('POST','/api/v1/bookings',request,attendee)
call('POST','/api/v1/bookings',request,attendee)
assert len([n for n in notices() if n['kind']=='BOOKING_CONFIRMED'])==1
notice=notices()[0]
call('POST','/api/v1/me/notifications/'+notice['id']+'/read',token=b,expected=404)
call('POST','/api/v1/me/notifications/'+notice['id']+'/read',token=attendee,expected=204)
assert call('GET','/api/v1/me/notifications/unread-count',token=attendee)==0
event=call('PATCH',path+'/presentation',{'title':'Updated presentation '+suffix,'description':event['description'],'location':'New hall','category':event['category'],'cardTheme':event['cardTheme'],'version':event['version']},a)
wait_for(lambda:any(n['kind']=='EVENT_UPDATED' and 'New hall' in n['message'] for n in notices()))
event=call('PUT',path+'/revision',{**event,'startsAt':(start+datetime.timedelta(hours=1)).isoformat(),'endsAt':(start+datetime.timedelta(hours=3)).isoformat()},a)
wait_for(lambda:len([n for n in notices() if n['kind']=='EVENT_UPDATED'])==2)
# A failed revision must not enqueue a notification.
call('PUT',path+'/revision',{**event,'capacity':1},a,409)
time.sleep(4)
assert len([n for n in notices() if n['kind']=='EVENT_UPDATED'])==2
# Force delivery retry, as if sender crashed after the recipient committed.
sql("UPDATE catalog.event_notification_outbox SET delivered_at=NULL WHERE payload->>'eventId'='"+event['id']+"'")
time.sleep(4)
assert len([n for n in notices() if n['kind']=='EVENT_UPDATED'])==2
call('POST','/api/v1/bookings/'+booked['id']+'/cancel',token=attendee)
call('POST','/api/v1/bookings/'+booked['id']+'/cancel',token=attendee)
assert len([n for n in notices() if n['kind']=='BOOKING_CANCELLED'])==1
# Saved tickets: enter the five-minute window without waiting five real minutes.
rem=call('POST','/api/v1/organizer/events',{**body,'title':'Reminder '+suffix},a,201)
rp='/api/v1/organizer/events/'+rem['id']
opens=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=30)
inventory=call('PUT',rp+'/ticket-types',{'eventVersion':rem['version'],'version':0,'ticketTypes':[{'name':'Early ticket','quota':10,'opensAt':opens.isoformat(),'closesAt':start.isoformat()}]},a)
rem=call('GET',rp,token=a)
call('POST',rp+'/publish',{'version':rem['version'],'ticketVersion':inventory['version']},a)
ticket=inventory['ticketTypes'][0]
call('PUT','/api/v1/pre-registrations/'+rem['id'],{'ticketTypeId':ticket['id'],'quantity':1},attendee)
assert not any(n['kind']=='REGISTRATION_OPENING' for n in notices())
sql("UPDATE admission.ticket_types SET opens_at=now()+interval '4 minutes' WHERE id='"+ticket['id']+"'")
wait_for(lambda:any(n['kind']=='REGISTRATION_OPENING' for n in notices()))
time.sleep(16)
assert len([n for n in notices() if n['kind']=='REGISTRATION_OPENING'])==1
assert not notices(b)
call('POST','/api/v1/me/notifications/read-all',token=attendee,expected=204)
assert call('GET','/api/v1/me/notifications/unread-count',token=attendee)==0
print('PASS: invitation inbox accept/decline/isolation, duplicate invitations, booking replay/cancel dedup, event edits/outbox retry/rejected changes, five-minute reminder with two replicas, read state and user isolation')
