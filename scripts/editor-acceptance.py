#!/usr/bin/env python3
"""Disposable acceptance for unified editing, mutable ticket types and publication management."""
import runpy
globals().update(runpy.run_path('scripts/contacts-acceptance.py'))
event,ticket=offering('Unified editor '+suffix)
ep='/api/v1/organizer/events/'+event['id']
booked=call('POST','/api/v1/bookings',req(event,ticket,3),attendee)
current=call('GET',ep,token=a);inv=call('GET',ep+'/ticket-types',token=a)
changed_ticket={**inv['ticketTypes'][0],'name':'Updated general','quota':12}
change={**current,'title':'Saved details and tickets '+suffix,'capacity':15,'ticketConfiguration':{'version':inv['version'],'ticketTypes':[changed_ticket,{'name':'New option','quota':3,'opensAt':changed_ticket['opensAt'],'closesAt':changed_ticket['closesAt']}]}}
call('PUT',ep+'/revision',change,b,404)
saved=call('PUT',ep+'/revision',change,a)
assert saved['status']=='PUBLISHED' and call('GET','/api/v1/events/'+event['id'])['title']==change['title']
updated=call('GET',ep+'/ticket-types',token=a)
existing=next(t for t in updated['ticketTypes'] if t['id']==ticket['id'])
assert existing['name']=='Updated general' and existing['available']==9
assert call('GET','/api/v1/bookings/'+booked['id'],token=attendee)['tickets']==booked['tickets']
# Rejected quota must not partially update the event or any ticket.
bad={**saved,'title':'Must not be saved','ticketConfiguration':{'version':updated['version'],'ticketTypes':[{**t,'quota':2} if t['id']==ticket['id'] else t for t in updated['ticketTypes']]}}
call('PUT',ep+'/revision',bad,a,409)
assert call('GET',ep,token=a)['title']==saved['title']
assert call('GET',ep+'/ticket-types',token=a)==updated
# Existing references prevent removing a ticket type; unreferenced types may be removed.
current=call('GET',ep,token=a)
call('PUT',ep+'/revision',{**current,'ticketConfiguration':{'version':updated['version'],'ticketTypes':[t for t in updated['ticketTypes'] if t['id']!=ticket['id']]}},a,409)
current=call('GET',ep,token=a)
call('PUT',ep+'/revision',{**current,'ticketConfiguration':{'version':updated['version']-1,'ticketTypes':updated['ticketTypes']}},a,409)
current=call('GET',ep,token=a)
# Swapping two names is valid as a single atomic edit (deferred unique constraint).
rows=updated['ticketTypes'];names=[t['name'] for t in rows]
current=call('PUT',ep+'/revision',{**current,'ticketConfiguration':{'version':updated['version'],'ticketTypes':[{**t,'name':names[1-i]} for i,t in enumerate(rows)]}},a)
updated=call('GET',ep+'/ticket-types',token=a)
current=call('PUT',ep+'/revision',{**current,'ticketConfiguration':{'version':updated['version'],'ticketTypes':[t for t in updated['ticketTypes'] if t['id']==ticket['id']]}},a)
assert len(call('GET',ep+'/ticket-types',token=a)['ticketTypes'])==1
# Pausing withdraws public discovery and blocks new bookings, preserving existing tickets.
paused=call('PUT',ep+'/revision',{**current,'publicationStatus':'PAUSED'},a)
assert paused['status']=='PAUSED'
call('POST',ep+'/publish',{'version':event['version'],'ticketVersion':1},a,409)
call('GET','/api/v1/events/'+event['id'],expected=404)
call('POST','/api/v1/bookings',req(event,ticket),attendee,404)
assert call('GET','/api/v1/bookings/'+booked['id'],token=attendee)['tickets']==booked['tickets']
inv=call('GET',ep+'/ticket-types',token=a)
paused=call('PUT',ep+'/revision',{**paused,'description':'Edited while paused','ticketConfiguration':{'version':inv['version'],'ticketTypes':[{**t,'quota':14} for t in inv['ticketTypes']]}},a)
assert paused['status']=='PAUSED'
# A resume command survives service outage and retry without losing the intended state.
try:
 subprocess.run(compose+['stop','admission'],check=True,stdout=subprocess.DEVNULL)
 resume={**paused,'publicationStatus':'PUBLISHED'}
 assert call('PUT',ep+'/revision',resume,a)['status']=='UPDATING'
 assert call('PUT',ep+'/revision',resume,a)['status']=='UPDATING'
finally:
 subprocess.run(compose+['start','admission'],check=True,stdout=subprocess.DEVNULL)
 subprocess.run(compose+['restart','gateway'],check=True,stdout=subprocess.DEVNULL)
 subprocess.run(['bash','scripts/smoke.sh'],check=True)
for _ in range(30):
 final=call('GET',ep,token=a)
 if final['status']=='PUBLISHED':break
 time.sleep(1)
assert final['status']=='PUBLISHED'
assert call('GET','/api/v1/events/'+event['id'])['description']=='Edited while paused'
call('POST','/api/v1/bookings',req(event,ticket),attendee)
# First save can configure a new draft through the same combined update.
draft=call('POST','/api/v1/organizer/events',{**body,'title':'Unified draft '+suffix},a,201)
dp='/api/v1/organizer/events/'+draft['id']
draft=call('PUT',dp+'/revision',{**draft,'ticketConfiguration':{'version':0,'ticketTypes':[{'name':'First option','quota':10,'opensAt':ticket['opensAt'],'closesAt':ticket['closesAt']}]}},a)
assert draft['status']=='DRAFT' and draft['salesConfigured']
assert len(call('GET',dp+'/ticket-types',token=a)['ticketTypes'])==1
call('PUT',dp+'/revision',{**draft,'publicationStatus':'PUBLISHED'},a,409)
print('PASS: combined event/ticket updates, stable IDs and credentials, quota/version/owner rejection with rollback, name swaps and reference-safe removal, pause/resume outage recovery, existing tickets preserved, new draft setup')
