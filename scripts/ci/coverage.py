"""Summarize real reports; never treat a missing report as passing coverage."""
import json, os, sys, xml.etree.ElementTree as ET
from pathlib import Path
kind=sys.argv[1]
values={'line':'N/A','branch':'N/A'}
rows=[]
def pct(covered,total):return f'{100*covered/total:.1f}%' if total else 'N/A'
if kind=='backend':
    totals={'line':[0,0],'branch':[0,0]};complete=True
    for service in ['identity','event-catalog','admission']:
        path=Path(f'services/{service}/target/site/jacoco/jacoco.xml');row={'line':'N/A','branch':'N/A'}
        if path.exists():
            for c in ET.parse(path).getroot().findall('counter'):
                key=c.attrib['type'].lower()
                if key in totals:
                    covered=int(c.attrib['covered']);total=covered+int(c.attrib['missed'])
                    totals[key][0]+=covered;totals[key][1]+=total;row[key]=pct(covered,total)
        else:complete=False
        rows.append(f"| {service} | {row['line']} | {row['branch']} |")
    if complete:values={k:pct(*v) for k,v in totals.items()}
    rows.append(f"| All services (weighted) | {values['line']} | {values['branch']} |")
else:
    path=Path('apps/web/coverage/coverage-summary.json')
    if path.exists():
        data=json.loads(path.read_text())['total']
        values={key:pct(data[name]['covered'],data[name]['total']) for key,name in [('line','lines'),('branch','branches')]}
    rows.append(f"| Web | {values['line']} | {values['branch']} |")
summary=f"### {kind.title()} unit/component coverage\n\n| Component | Lines | Branches |\n|---|---|---|\n"+'\n'.join(rows)+'\n\nMissing reports are N/A. HTTP acceptance is reported separately; these are not combined integration coverage figures.\n'
print(summary)
if os.environ.get('GITHUB_STEP_SUMMARY'):
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write(summary)
if os.environ.get('GITHUB_OUTPUT'):
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:
        for key,value in values.items():f.write(f'{key}={value}\n')
