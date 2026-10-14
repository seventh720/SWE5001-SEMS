#!/usr/bin/env python3
"""Disposable acceptance: prior workflows plus named contacts and username changes."""
import runpy
globals().update(runpy.run_path('scripts/schedule-acceptance.py'))
cp='/api/v1/profile/contacts'
call('GET',cp,expected=401)
assert call('GET',cp,token=attendee)==[]
first=call('POST',cp,{'label':'Myself','realName':'Alex Tan','email':'contact@example.com','studentId':'MUST-NOT-PERSIST'},attendee)
second=call('POST',cp,{'label':'Family','realName':'Sam Tan','phone':'+65 8123 4567'},attendee)
assert first['id']!=second['id'] and 'studentId' not in first
assert len(call('GET',cp,token=attendee))==2
assert call('GET',cp,token=b)==[]
call('PUT',cp+'/'+first['id'],first,b,404)
call('DELETE',cp+'/'+first['id']+'?version=0',token=b,expected=404)
call('POST',cp,{'label':'   '},attendee,400)
call('POST',cp,{'label':'Invalid','email':'bad email'},attendee,400)
changed=call('PUT',cp+'/'+first['id'],{**first,'realName':'New Alex'},attendee)
assert changed['version']==1
call('PUT',cp+'/'+first['id'],first,attendee,409)
call('DELETE',cp+'/'+first['id']+'?version=0',token=attendee,expected=409)
call('DELETE',cp+'/'+first['id']+'?version=1',token=attendee,expected=204)
assert [x['id'] for x in call('GET',cp,token=attendee)]==[second['id']]
# Legacy clients cannot retain student ID; their default contact appears in the new list.
legacy=call('PUT','/api/v1/profile',{'realName':'Legacy','studentId':'NOT-STORED'},attendee)
assert legacy['studentId'] is None
assert any(x['label']=='My details' for x in call('GET',cp,token=attendee))
up='/api/v1/profile/username'
old=call('GET','/api/v1/auth/me',token=attendee)
new='renamed.'+suffix
assert call('GET',up+'?value='+new.upper(),token=attendee)['available']
renamed=call('PUT',up,{'username':new.upper()},attendee)
assert renamed['username']==new and renamed['id']==old['id'] and renamed['email']==old['email']
assert call('GET','/api/v1/auth/me',token=attendee)['username']==new
assert call('POST','/api/v1/auth/login',{'email':old['email'],'password':password})['user']['username']==new
assert not call('GET',up+'?value='+new,token=b)['available']
call('PUT',up,{'username':new},b,409)
for name in ['a','bad name','...','Admin','support','x'*51]:
 call('PUT',up,{'username':name},attendee,400)
call('GET',up+'?value=validname',expected=401)
call('PUT',up,{'username':'validname'},expected=401)
# Two different accounts racing for a name: the database grants exactly one.
race='race.'+suffix
def rename_race(token):
 request=urllib.request.Request(BASE+up,data=json.dumps({'username':race}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token},method='PUT')
 try:
  with urllib.request.urlopen(request,timeout=15) as response:return response.status
 except urllib.error.HTTPError as e:return e.code
with concurrent.futures.ThreadPoolExecutor(2) as pool:assert sorted(pool.map(rename_race,[a,b]))==[200,409]
print('PASS: multiple contacts, student ID not retained, ownership/version/delete validation, username rules/normalization/availability, login continuity and uniqueness race')
