#!/usr/bin/env python3
"""Invalidate the narrow Spring view/SSE exceptions if those features are introduced."""
from pathlib import Path
import re

features = re.compile(r'XsltView|XsltViewResolver|SseEmitter|ServerSentEvent|text/event-stream|@Controller\b|ModelAndView')
violations = []
for root in Path('services').glob('*/src/main'):
    for path in root.rglob('*'):
        if path.is_file() and path.suffix in {'.java', '.xml', '.yaml', '.yml', '.properties'}:
            if features.search(path.read_text()):
                violations.append(str(path))
if violations:
    raise SystemExit('Reassess Spring CVE exceptions before introducing view/SSE features: ' + ', '.join(violations))
print('Spring exception scope verified: REST API services, no XSLT views or SSE fragments')
