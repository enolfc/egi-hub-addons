import json

from tornado import gen
from tornado.httpclient import HTTPRequest, AsyncHTTPClient, HTTPError


@gen.coroutine
def datahub_args(spawner, pod):
    spawner.log.info("*"* 80)
    spawner.log.info("*"* 80)
    spawner.log.info("*"* 80)
    if spawner.environment.get('DATAHUB_TOKEN', ''):
        http_client = AsyncHTTPClient()
        req = HTTPRequest('https://datahub.egi.eu/api/v3/onezone/user/effective_spaces',
                headers={'content-type': 'application/json',
                         'x-auth-token': '%s' % spawner.environment['DATAHUB_TOKEN']},
                method='GET')
        try:
            resp = yield http_client.fetch(req)
            datahub_response = json.loads(resp.body.decode('utf8', 'replace'))
            spawner.log.info("RESPONSE: %s", datahub_response)
        except HTTPError as e:
            spawner.log.info("Something failed! %s", e)
            raise e
        scheme = []
        for space in datahub_response['spaces']:
            req = HTTPRequest('https://datahub.egi.eu/api/v3/onezone/user/spaces/%s' % space,
                    headers={'content-type': 'application/json',
                             'x-auth-token': '%s' % spawner.environment['DATAHUB_TOKEN']},
                    method='GET')
            try:
                resp = yield http_client.fetch(req)
                datahub_response = json.loads(resp.body.decode('utf8', 'replace'))
                scheme.append({
                    "root": datahub_response["name"],
                    "class": "onedatafs_jupyter.OnedataFSContentsManager",
                    "config": {"space": "/" + datahub_response["name"] },
                })
            except HTTPError as e:
                spawner.log.info("Something failed! %s", e)
                raise e
        pod.spec.containers[0].args = (pod.spec.containers[0].args +
            [
                '--NotebookApp.contents_manager_class=egi_hub_addons.manager.MixedContentsManager',
                '--OnedataFSContentsManager.oneprovider_host=plg-cyfronet-01.datahub.egi.eu',
                '--OnedataFSContentsManager.access_token=$(DATAHUB_TOKEN)',
                '--OnedataFSContentsManager.path=""',
                '--OnedataFSContentsManager.force_proxy_io=True',
                '--OnedataFSContentsManager.force_direct_io=False',
                '--MixedContentsManager.filesystem_scheme=%s' % json.dumps(scheme)
            ]
        )
        spawner.log.info("POD: %s", pod.spec.containers[0].args)
    return pod
