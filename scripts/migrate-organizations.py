#!/usr/bin/env python3
"""Plan/apply the one-time owner -> organization mapping during a maintenance window.
Uses a maintenance PostgreSQL login, with separate transactions per service schema.
No application runtime cross-schema access is introduced. Does not delete business data.
"""
import argparse, json, subprocess, uuid
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--compose-file',default='deployment/compose.yaml')
p.add_argument('--env-file',default='.env')
p.add_argument('--plan',required=True,type=Path)
p.add_argument('--apply',action='store_true')
p.add_argument('--maintenance-confirmed',action='store_true')
a=p.parse_args()
compose=['docker','compose','--env-file',a.env_file,'-f',a.compose_file]
def sql(statement):
 return subprocess.check_output(compose+['exec','-T','postgres','psql','-X','-v','ON_ERROR_STOP=1','-U','postgres','-d','sems','-At'],input=statement,text=True).strip()
def query(statement):
 result=sql('SELECT COALESCE(json_agg(row_to_json(q)),\'[]\') FROM ('+statement+') q;')
 return json.loads(result)
def quote(value):return "'"+str(value).replace("'","''")+"'"
def fingerprint():
 return query("SELECT (SELECT count(*) FROM admission.bookings) bookings,(SELECT count(*) FROM admission.tickets) tickets,(SELECT COALESCE(sum(reserved),0) FROM admission.ticket_types) reserved,(SELECT md5(COALESCE(string_agg(id::text||credential||state,',' ORDER BY id),'')) FROM admission.tickets) ticket_digest,(SELECT md5(COALESCE(string_agg(id::text||user_id::text||request_key::text||quantity::text||status,',' ORDER BY id),'')) FROM admission.bookings) booking_digest")[0]
def pending():
 return int(sql("SELECT (SELECT count(*) FROM catalog.events WHERE status IN ('PUBLISHING','UPDATING'))+(SELECT count(*) FROM catalog.event_revisions WHERE status='PENDING');"))
if not a.apply:
 if a.plan.exists():raise SystemExit('Plan already exists; use a new path to avoid overwriting a reviewed mapping.')
 owners=query('SELECT DISTINCT organizer_id AS id FROM catalog.events WHERE organization_id IS NULL')
 accounts={u['id']:u for u in query('SELECT id,username,status FROM identity.users')}
 legacy=query("SELECT DISTINCT user_id AS id FROM identity.user_roles r WHERE role_code='ORGANIZER' AND NOT EXISTS(SELECT 1 FROM identity.organization_memberships m WHERE m.user_id=r.user_id)")
 ids={u['id'] for u in owners}|{u['id'] for u in legacy}
 rows=[]
 for owner in sorted(ids):
  if owner not in accounts or accounts[owner]['status']!='ACTIVE':raise SystemExit('An owner is missing/inactive; resolve ownership before migration: '+owner)
  rows.append({'ownerId':owner,'organizationId':str(uuid.uuid5(uuid.NAMESPACE_URL,'sems:legacy-organization:'+owner)),'name':accounts[owner]['username']+"'s organization",'slug':'legacy-'+owner})
 a.plan.parent.mkdir(parents=True,exist_ok=True)
 a.plan.write_text(json.dumps({'version':1,'mapping':rows,'fingerprint':fingerprint(),'pendingOperations':pending()},indent=2)+'\n')
 print(f'Wrote {len(rows)} owner mappings to {a.plan}. Review names/IDs, back up the database and drain writes before applying.')
else:
 if not a.maintenance_confirmed:raise SystemExit('Apply requires --maintenance-confirmed: stop external writes, drain pending operations and take a database backup first.')
 data=json.loads(a.plan.read_text())
 if data['version']!=1:raise SystemExit('Unsupported plan version')
 if pending():raise SystemExit('Pending publication/revision operations must finish before migration.')
 if fingerprint()!=data['fingerprint']:raise SystemExit('Business records changed since planning. Generate and review a new plan during maintenance.')
 for row in data['mapping']:
  owner=str(uuid.UUID(row['ownerId']));org=str(uuid.UUID(row['organizationId']))
  # Conflicting data causes rollback; retries reuse the same stable mapping.
  existing=query('SELECT id,slug FROM identity.organizations WHERE id='+quote(org))
  if existing and existing[0]['slug']!=row['slug']:raise SystemExit('Organization ID conflict: '+org)
  sql("BEGIN; SET LOCAL ROLE identity_app; INSERT INTO identity.organizations(id,name,slug) VALUES("+','.join(map(quote,[org,row['name'],row['slug']]))+") ON CONFLICT(id) DO NOTHING; INSERT INTO identity.organization_memberships(organization_id,user_id,role,status) VALUES("+quote(org)+','+quote(owner)+",'ORG_ADMIN','ACTIVE') ON CONFLICT(organization_id,user_id) DO NOTHING; COMMIT;")
  for schema,table in [('catalog','events'),('admission','sales')]:
   if int(sql(f'SELECT count(*) FROM {schema}.{table} WHERE organizer_id={quote(owner)} AND organization_id IS NOT NULL AND organization_id<>{quote(org)};')):raise SystemExit('Conflicting existing organization mapping in '+schema)
   extra=',organization_name='+quote(row['name']) if schema=='catalog' else ''
   sql(f'BEGIN; SET LOCAL ROLE {schema}_app; UPDATE {schema}.{table} SET organization_id={quote(org)}{extra} WHERE organizer_id={quote(owner)} AND organization_id IS NULL; COMMIT;')
 if int(sql('SELECT (SELECT count(*) FROM catalog.events WHERE organization_id IS NULL)+(SELECT count(*) FROM admission.sales WHERE organization_id IS NULL);')):raise SystemExit('Unmapped records remain. Keep maintenance enabled and resolve the mapping.')
 if int(sql('SELECT count(*) FROM admission.sales s JOIN catalog.events e ON e.id=s.event_id WHERE s.organization_id IS DISTINCT FROM e.organization_id;')):raise SystemExit('Catalog/Admission organization mismatch')
 if fingerprint()!=data['fingerprint']:raise SystemExit('Business record fingerprint changed; investigate before reopening traffic.')
 print('PASS: organization mapping complete; booking IDs/request keys, ticket IDs/credentials/states and inventory unchanged. Safe to rerun this plan.')
