#!/usr/bin/env python3
"""Exercise explicit legacy mapping and its replay on a disposable stack only."""
import os,json,uuid,subprocess,urllib.request,datetime,tempfile
from pathlib import Path
base=os.environ.get('SEMS_BASE_URL','http://localhost:18080')
compose_file=os.environ.get('SEMS_COMPOSE_FILE','deployment/compose.yaml')
env_file=os.environ.get('SEMS_ENV_FILE','.env')
compose=['docker','compose','--env-file',env_file,'-f',compose_file]
def call(method,path,body=None,token=None):
 req=urllib.request.Request(base+path,method=method,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
 with urllib.request.urlopen(req,timeout=15) as response:
  raw=response.read();return json.loads(raw) if raw else None
suffix=uuid.uuid4().hex[:10];password='Migration-'+uuid.uuid4().hex;email='migration-'+suffix+'@example.com'
u=call('POST','/api/v1/auth/register',{'username':'migration'+suffix,'email':email,'password':password})
admin=call('POST','/api/v1/auth/login',{'email':os.environ['SEMS_BOOTSTRAP_ADMIN_EMAIL'],'password':os.environ['SEMS_BOOTSTRAP_ADMIN_PASSWORD']})['accessToken']
token=call('POST','/api/v1/auth/login',{'email':email,'password':password})['accessToken']
org=call('POST','/api/v1/admin/organizations',{'name':'Migration fixture','slug':'migration-'+suffix,'adminEmail':email},admin)
start=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=3)
event=call('POST','/api/v1/organizer/events',{'organizationId':org['id'],'title':'Preserved migration offering','description':'Fixture','location':'Campus','startsAt':start.isoformat(),'endsAt':(start+datetime.timedelta(hours=1)).isoformat(),'capacity':5},token)
ep='/api/v1/organizer/events/'+event['id']
inv=call('PUT',ep+'/ticket-types',{'eventVersion':event['version'],'version':0,'ticketTypes':[{'name':'General','quota':5,'opensAt':(start-datetime.timedelta(days=4)).isoformat(),'closesAt':start.isoformat()}]},token)
event=call('GET',ep,token=token)
call('POST',ep+'/publish',{'version':event['version'],'ticketVersion':inv['version']},token)
booking=call('POST','/api/v1/bookings',{'eventId':event['id'],'ticketTypeId':inv['ticketTypes'][0]['id'],'quantity':2,'requestKey':str(uuid.uuid4())},token)
# Emulate the pre-upgrade ownership shape without changing booking/ticket records.
sql=f"UPDATE catalog.events SET organization_id=NULL WHERE id='{event['id']}'; UPDATE admission.sales SET organization_id=NULL WHERE event_id='{event['id']}';"
subprocess.run(compose+['exec','-T','postgres','psql','-X','-v','ON_ERROR_STOP=1','-U','postgres','-d','sems','-c',sql],check=True,stdout=subprocess.DEVNULL)
with tempfile.TemporaryDirectory(prefix='sems-migration-') as d:
 plan=str(Path(d)/'plan.json')
 cmd=['python3','scripts/migrate-organizations.py','--compose-file',compose_file,'--env-file',env_file,'--plan',plan]
 subprocess.run(cmd,check=True)
 data=json.loads(Path(plan).read_text());mapping=next(m for m in data['mapping'] if m['ownerId']==u['id'])
 subprocess.run(cmd+['--apply','--maintenance-confirmed'],check=True)
 subprocess.run(cmd+['--apply','--maintenance-confirmed'],check=True)
 migrated=call('GET',ep,token=token)
 assert migrated['organizationId']==mapping['organizationId'] and migrated['createdBy']==u['id']
 assert call('GET','/api/v1/bookings/'+booking['id'],token=token)==booking
 assert call('GET',ep+'/ticket-types',token=token)['ticketTypes'][0]['available']==3
print('PASS: reviewed legacy organization mapping, preserved bookings/ticket credentials/inventory, idempotent migration replay and new organization authorization')
