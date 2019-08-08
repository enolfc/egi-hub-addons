import json

from tornado import gen
from tornado.httpclient import HTTPRequest, AsyncHTTPClient, HTTPError

def datahub_pod_modifier(onezone_url='https://datahub.egi.eu',
                         oneprovider_host='plg-cyfronet-01.datahub.egi.eu',
                         manager_class='eginotebooks.manager.MixedContentsManager',
                         token_variable='ONECLIENT_ACCESS_TOKEN'):
    @gen.coroutine
    def datahub_args(spawner, pod):
        spawner.log.info("*"* 80)
        spawner.log.info("*"* 80)
        spawner.log.info("*"* 80)
        if spawner.environment.get(token_variable, ''):
            http_client = AsyncHTTPClient()
            req = HTTPRequest(onezone_url + '/api/v3/onezone/user/effective_spaces',
                    headers={'content-type': 'application/json',
                             'x-auth-token': '%s' % spawner.environment[token_variable]},
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
                req = HTTPRequest(onezone_url + '/api/v3/onezone/user/spaces/%s' % space,
                        headers={'content-type': 'application/json',
                                 'x-auth-token': '%s' % spawner.environment[token_variable]},
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
                    '--NotebookApp.contents_manager_class=%s' % manager_class,
                    '--OnedataFSContentsManager.oneprovider_host=%s' % oneprovider_host,
                    '--OnedataFSContentsManager.access_token=$(%s)' % token_variable,
                    '--OnedataFSContentsManager.path=""',
                    '--OnedataFSContentsManager.force_proxy_io=False',
                    '--OnedataFSContentsManager.force_direct_io=True',
                    '--MixedContentsManager.filesystem_scheme=%s' % json.dumps(scheme)
                ]
            )
            spawner.log.info("POD: %s", pod.spec.containers[0].args)
        return pod
    return datahub_args
