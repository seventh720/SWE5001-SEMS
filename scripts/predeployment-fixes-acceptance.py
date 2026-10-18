#!/usr/bin/env python3
"""Live role revocation, bounded member queries and recoverable org closure. Disposable stack only."""
from acceptance import *
import subprocess,time
compose=['docker','compose','--env-file',os.environ.get('SEMS_ENV_FILE','.env'),'-f',os.environ.get('SEMS_COMPOSE_FILE','deployment/compose.yaml')]
def sql(query,ok=True):
 result=subprocess.run(compose+['exec','-T','postgres','psql','-v','ON_ERROR_STOP=1','-U','postgres','-d','sems','-Atq','-c',('SET search_path TO catalog;' if 'catalog.events' in query else 'SET search_path TO identity;')+query],text=True,capture_output=True)
 if ok:assert result.returncode==0,'Test fixture SQL failed'
 else:assert result.returncode!=0 and 'Organization is closing or closed' in result.stderr,'Closed organization did not reject the stale mutation for the expected reason'
 return result.stdout.strip()
def wait_for(check,message):
 for _ in range(60):
  if check():return
  time.sleep(1)
 raise AssertionError(message)
def admin_org(oid):return next((o for o in paged('/api/v1/admin/organizations',admin) if o['id']==oid),None)
# The same signed administrator JWT loses platform authority after role revocation.
call('PUT',f"/api/v1/admin/users/{users[1]['id']}/roles",{'roles':['ATTENDEE','ADMIN']},admin)
old_admin=login(users[1]['email']);call('GET','/api/v1/admin/users',token=old_admin)
call('PUT',f"/api/v1/admin/users/{users[1]['id']}/roles",{'roles':['ATTENDEE']},admin)
for endpoint in ['/api/v1/admin/users','/api/v1/admin/organizations','/api/v1/admin/organizations/requests']:call('GET',endpoint,token=old_admin,expected=403)
call('PUT',f"/api/v1/admin/organizations/{org_a['id']}/profile",{'name':'Denied','slug':'denied-'+suffix,'version':0},old_admin,403)
call('DELETE',f"/api/v1/admin/organizations/{org_b['id']}?version=0",token=old_admin,expected=403)
assert call('GET','/api/v1/me/organizations',token=b)[0]['id']==org_b['id']
print('PASS: the original admin JWT is immediately denied after demotion; independent organization membership still works')
# Bulk fixture avoids password hashing cost. No test accounts can log in with this hash.
sql(f"""WITH created AS (INSERT INTO identity.users(id,username,email,password_hash)
 SELECT gen_random_uuid(),'p{suffix}_'||lpad(n::text,3,'0'),'page-{suffix}-'||lpad(n::text,3,'0')||'@example.com','unusable-test-hash' FROM generate_series(1,37) n RETURNING id)
 INSERT INTO identity.organization_memberships(organization_id,user_id,role,status) SELECT '{org_a['id']}',id,'MEMBER','ACTIVE' FROM created;""")
mp=f"/api/v1/organizations/{org_a['id']}/members"
pages=[call('GET',mp+f'?page={n}&size=12',token=a) for n in range(4)]
assert [len(p['items']) for p in pages]==[12,12,12,2]
assert len({m['userId'] for p in pages for m in p['items']})==38
assert all(p['totalElements']==38 and p['totalMembers']==38 for p in pages)
search=call('GET',mp+f'?search=PAGE-{suffix}-025%40&size=12',token=a)
assert search['totalElements']==1 and search['items'][0]['email']==f'page-{suffix}-025@example.com'
assert call('GET',mp+'?search=%25',token=a)['totalElements']==0
assert call('GET',mp+'?page=100&size=12',token=a)['items']==[]
for query in ['page=-1','size=0','size=51','page=2147483647&size=50','search='+'x'*201]:call('GET',mp+'?'+query,token=a,expected=400)
call('GET',mp+'?page=1&size=12',token=b,expected=403)
print('PASS: stable bounded SQL pages, whole-directory username/email search, literal wildcards, limits and organization isolation')
# Create public bookings held by an attendee outside the closing organization.
def offering(org,owner,paused=False):
 begin=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=10)
 event=call('POST','/api/v1/organizer/events',{**body,'organizationId':org['id'],'startsAt':begin.isoformat(),'endsAt':(begin+datetime.timedelta(hours=1)).isoformat()},owner,201)
 path='/api/v1/organizer/events/'+event['id']
 inv=call('PUT',path+'/ticket-types',{'eventVersion':event['version'],'version':0,'ticketTypes':[{'name':'General','quota':20,'opensAt':(begin-datetime.timedelta(days=1)).isoformat(),'closesAt':begin.isoformat()}]},owner)
 event=call('GET',path,token=owner);event=call('POST',path+'/publish',{'version':event['version'],'ticketVersion':inv['version']},owner)
 booking=call('POST','/api/v1/bookings',{'eventId':event['id'],'ticketTypeId':inv['ticketTypes'][0]['id'],'quantity':2,'requestKey':str(uuid.uuid4())},attendee)
 if paused:event=call('PUT',path+'/revision',{**event,'publicationStatus':'PAUSED'},owner)
 return event,path,inv,booking
published,pp,pi,pb=offering(org_a,a)
paused,sp,si,sb=offering(org_a,a,True)
# Preserve a historical check-in while invalidating its unused sibling ticket.
call('PUT',pp+'/staff',{'userId':users[0]['id'],'active':True},a,204)
call('POST',f"/api/v1/events/{published['id']}/check-ins",{'credential':pb['tickets'][0]['credential']},a)
# Both existing pending work and fresh requests must not escape closure.
request=call('POST',f"/api/v1/organizations/{org_a['id']}/requests",{'kind':'CLOSE','reason':'Closing society','version':admin_org(org_a['id'])['version']},a)
try:
 subprocess.run(compose+['stop','admission'],check=True,stdout=subprocess.DEVNULL)
 # Revision persists while Admission is unavailable; closure waits for it to settle.
 assert call('PUT',sp+'/revision',{**paused,'title':'Pending close '+suffix},a)['status']=='UPDATING'
 call('POST','/api/v1/admin/organizations/requests/'+request['id']+'/review',{'approve':True,'note':'Approved closure'},admin,204)
 assert admin_org(org_a['id'])['status']=='CLOSING'
 assert call('GET','/api/v1/me/organizations',token=a)==[]
 wait_for(lambda:sql(f"SELECT count(*) FROM catalog.organization_closures WHERE organization_id='{org_a['id']}'")=='1','Catalog fence not persisted')
 call('POST','/api/v1/organizer/events',{**body},a,404)
 call('PATCH',f"/api/v1/admin/organizations/{org_a['id']}",{'status':'ACTIVE'},admin,409)
 # Direct SQL models a stale pre-authorized writer reaching the local transaction.
 sql(f"UPDATE catalog.events SET status='PUBLISHING' WHERE id='{draft['id']}'",False)
 assert sql(f"SELECT count(*) FROM admission.bookings WHERE id='{pb['id']}' AND status='CONFIRMED'")=='1'
 assert admin_org(org_a['id'])['status']=='CLOSING'
 subprocess.run(compose+['restart','identity','event-catalog'],check=True,stdout=subprocess.DEVNULL)
finally:
 subprocess.run(compose+['start','admission'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(compose+['restart','gateway'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['bash','scripts/smoke.sh'],check=True)
wait_for(lambda:admin_org(org_a['id'])['status']=='SUSPENDED','Approved closure did not recover')
for original in [pb,sb]:
 booking=call('GET','/api/v1/bookings/'+original['id'],token=attendee)
 assert booking['status']=='CANCELLED' and booking['eventCancellationReason']
 assert all(t['state']!='VALID' for t in booking['tickets'])
 assert sql(f"SELECT count(*) FROM admission.notifications WHERE user_id='{users[2]['id']}' AND dedup_key='event-cancel:{original['id']}'")=='1'
assert call('GET','/api/v1/bookings/'+pb['id'],token=attendee)['tickets'][0]['state']=='CHECKED_IN'
assert sql(f"SELECT count(*) FROM catalog.events WHERE organization_id='{org_a['id']}' AND status IN ('PUBLISHING','UPDATING','PUBLISHED','PAUSED','CANCELLING')")=='0'
assert sql(f"SELECT count(*) FROM identity.organization_memberships WHERE organization_id='{org_a['id']}' AND status<>'REMOVED'")=='0'
call('PATCH',f"/api/v1/admin/organizations/{org_a['id']}",{'status':'ACTIVE'},admin,409)
# Lost Identity acknowledgement is safely replayed through Catalog and Admission receipts.
sql(f"UPDATE identity.organization_closures SET completed_at=NULL WHERE organization_id='{org_a['id']}'; UPDATE identity.organizations SET status='CLOSING' WHERE id='{org_a['id']}';")
wait_for(lambda:admin_org(org_a['id'])['status']=='SUSPENDED','Acknowledgement replay failed')
assert sql(f"SELECT count(*) FROM admission.notifications WHERE dedup_key='event-cancel:{pb['id']}'")=='1'
print('PASS: approval closure waits for pending revisions, fences stale publication, survives Identity/Catalog restart and Admission outage, cancels outsiders tickets once and preserves check-in history')
# Direct deletion follows the same protocol and preserves personal accounts and records.
e2,p2,i2,b2=offering(org_b,b)
call('DELETE',f"/api/v1/admin/organizations/{org_b['id']}?version={admin_org(org_b['id'])['version']}",token=admin,expected=204)
wait_for(lambda:admin_org(org_b['id']) is None,'Soft deletion did not finish')
assert call('GET','/api/v1/bookings/'+b2['id'],token=attendee)['status']=='CANCELLED'
assert call('GET','/api/v1/auth/me',token=b)['id']==users[1]['id']
print('PASS: platform soft deletion uses the same cancellation protocol and retains personal accounts/history')
