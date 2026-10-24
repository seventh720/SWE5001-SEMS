#!/usr/bin/env python3
"""Render an application-only K3s release from this run's immutable image lock."""
import argparse
import copy
import json
from pathlib import Path
import re
import subprocess

APPLICATIONS = ('identity', 'event-catalog', 'admission', 'web', 'gateway')
NAMESPACE = 'sems-test'
REGISTRY = 'ghcr.io/seventh720/swe5001-sems/'
COMMIT_ANNOTATION = 'sems.seventh720.com/source-commit'


def allowed(resource):
    kind = resource.get('kind')
    name = resource.get('metadata', {}).get('name', '')
    return ((kind == 'Deployment' and name in APPLICATIONS) or
            (kind == 'Service' and name in (*APPLICATIONS, 'event-catalog-pods')) or
            (kind == 'Ingress' and name == 'sems') or
            (kind == 'ConfigMap' and (name in ('sems-runtime', 'sems-database') or
                                     re.fullmatch(r'gateway-config-[a-z0-9]+', name))))


def validate_resources(resources, images=None):
    seen, deployed = set(), {}
    for resource in resources:
        if not allowed(resource) or resource['metadata'].get('namespace') != NAMESPACE:
            raise ValueError('Release contains a resource outside the application deployment scope')
        key = (resource['kind'], resource['metadata']['name'])
        if key in seen:
            raise ValueError('Duplicate application resource')
        seen.add(key)
        if resource['kind'] == 'Deployment':
            name = key[1]
            containers = resource['spec']['template']['spec']['containers']
            if len(containers) != 1 or containers[0]['name'] != name:
                raise ValueError('Unexpected application container layout')
            ref = containers[0]['image']
            if not re.fullmatch(re.escape(REGISTRY + name) + r'@sha256:[0-9a-f]{64}', ref):
                raise ValueError(name + ': immutable project image required')
            if images is not None and ref != images.get(name):
                raise ValueError(name + ': deployment/image lock mismatch')
            if resource['spec']['replicas'] != 2:
                raise ValueError('Test applications must retain two replicas')
            deployed[name] = ref
        if resource['kind'] == 'Ingress':
            if [r['host'] for r in resource['spec']['rules']] != ['sems-test.seventh720.com']:
                raise ValueError('Unexpected ingress host')
    if set(deployed) != set(APPLICATIONS):
        raise ValueError('Release must contain the five application Deployments')
    return deployed


def validate_release(release):
    if release.get('operation') == 'rollback':
        if release.get('databaseCompatibilityConfirmed') is not True:
            raise ValueError('Application rollback requires database compatibility confirmation')
    elif release.get('operation') == 'deploy':
        if not re.fullmatch(r'[0-9a-f]{40}', release.get('sourceCommit', '')):
            raise ValueError('Full source commit required')
        if set(release['images']) != set(APPLICATIONS):
            raise ValueError('Five application image references required')
        validate_resources(release['resources'], release['images'])
    else:
        raise ValueError('Unsupported release operation')
    if not re.fullmatch(r'[0-9a-f]{40}-[0-9]+-[0-9]+', release.get('releaseId', '')):
        raise ValueError('Expected commit-run-attempt release ID')
    if release['operation'] == 'deploy' and not release['releaseId'].startswith(release['sourceCommit'] + '-'):
        raise ValueError('Release ID/source commit mismatch')
    return release


def render(lock, commit, release_id, documents):
    if lock.get('x-release-commit') != commit:
        raise ValueError('Source/image lock commit mismatch')
    if set(lock.get('services', {})) != {*APPLICATIONS, 'postgres', 'caddy'}:
        raise ValueError('Incomplete published image lock')
    images = {name: lock['services'][name]['image'] for name in APPLICATIONS}
    resources = []
    for document in documents:
        if not document or not allowed(document):
            continue
        resource = copy.deepcopy(document)
        if resource['kind'] == 'Deployment':
            name = resource['metadata']['name']
            resource['spec']['template']['spec']['containers'][0]['image'] = images[name]
            resource['metadata'].setdefault('annotations', {})[COMMIT_ANNOTATION] = commit
            resource['spec']['template']['metadata'].setdefault('annotations', {})[COMMIT_ANNOTATION] = commit
        resources.append(resource)
    return validate_release({'operation': 'deploy', 'releaseId': release_id,
                             'sourceCommit': commit, 'images': images, 'resources': resources})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image-lock', required=True, type=Path)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--release-id', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    import yaml
    manifests = subprocess.check_output(['kubectl', 'kustomize', 'deployment/k8s/overlays/k3s'], text=True)
    result = render(json.loads(args.image_lock.read_text()), args.commit, args.release_id, yaml.safe_load_all(manifests))
    args.output.write_text(json.dumps(result, separators=(',', ':')) + '\n')
    print('Rendered five application digests; database, credentials, storage and Traefik are managed separately')


if __name__ == '__main__':
    main()
