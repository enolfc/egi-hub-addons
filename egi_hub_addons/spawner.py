#from tornado import gen
#from tornado.httputil import url_concat
#from tornado.httpclient import HTTPRequest, AsyncHTTPClient, HTTPError
#from egispawner.spawner import EGISpawner
#import uuid
#import json
#import requests
#
#from kubernetes.client.models import V1ObjectMeta, V1Secret
#
#class DataHubSpawner(EGISpawner):
#    @gen.coroutine
#    def get_access_token(self):
#        self.log.info("Get access token from Check-in first")
#        auth_state = yield self.user.get_auth_state()
#        if not auth_state or 'refresh_token' not in auth_state:
#            raise web.HTTPError(500, 'No auth state available')
#        http_client = AsyncHTTPClient()
#        headers = {
#            "Accept": "application/json",
#            "User-Agent": "JupyterHub",
#        }
#        params = dict(
#            client_id=self.authenticator.client_id,
#            client_secret=self.authenticator.client_secret,
#            grant_type='refresh_token',
#            refresh_token=auth_state['refresh_token'],
#            scope=' '.join(self.authenticator.scope),
#        )
#        url = url_concat(self.authenticator.token_url, params)
#        req = HTTPRequest(url,
#                          auth_username=self.authenticator.client_id,
#                          auth_password=self.authenticator.client_secret,
#                          headers=headers,
#                          method='POST',
#                          body=''
#                          )
#        resp = yield http_client.fetch(req)
#        refresh_response = json.loads(resp.body.decode('utf8', 'replace'))
#        return refresh_response['access_token']
#
#
#    def find_secret(self):
#        secrets = self.api.list_namespaced_secret(namespace=self.namespace)
#        for s in secrets.items:
#            if s.type == 'egi.eu/onedata' and s.metadata.annotations.get('hub.jupyter.org/username', '') == self.user.name:
#                # let's assume the secret is ok, no need to do anything else
#                self.log.info('Found secret with token, moving on')
#                return s.metadata.name
#        self.log.info('No secret with token :/')
#        return ''
#
#    @gen.coroutine
#    def create_secret(self, checkin_access_token):
#        self.log.info("Get access token from DataHub")
#        http_client = AsyncHTTPClient()
#        req = HTTPRequest('https://datahub.egi.eu/api/v3/onezone/user/client_tokens',
#                          headers={'content-type': 'application/json',
#                                   'x-auth-token': 'egi:%s' % checkin_access_token},
#                          method='POST',
#                          body='')
#        try:
#            resp = yield http_client.fetch(req)
#            datahub_response = json.loads(resp.body.decode('utf8', 'replace'))
#            onedata_token = datahub_response['token']
#        except HTTPError as e:
#            self.log.info("Something failed! %s", e)
#            raise e
#        # Create a new secret with this
#        secret_name = uuid.uuid4().hex
#        secret = V1Secret(type="egi.eu/onedata",
#                          metadata=V1ObjectMeta(name=secret_name,
#                          annotations={'hub.jupyter.org/username': self.user.name}),
#                          string_data={"token": onedata_token})
#        try:
#            yield self.asynchronize(
#                self.api.create_namespaced_secret,
#                self.namespace,
#                secret,
#            )
#        except:
#            self.log.info("yay, error")
#            raise
#        self.log.info("it works?")
#        return secret_name
#
#    @gen.coroutine
#    def start(self):
#        secret_name = self.find_secret()
#        if not secret_name:
#            # not found let's create it with a new token
#            checkin_access_token = yield self.get_access_token()
#            secret_name = yield self.create_secret(checkin_access_token)
#        self.log.info('SECRET NAME: %s', secret_name)
#        # here we should have the secret in place, so add the sidecar
#        self.singleuser_extra_containers = [{
#            "name": "oneclient",
#            "image": "onedata/oneclient:18.02.0-rc13",
#            "env": [
#                {"name": "ONECLIENT_PROVIDER_HOST", "value": "{{ oneprovider_host }}"},
#                {"name": "ONECLIENT_ACCESS_TOKEN",
#                 "valueFrom": {"secretKeyRef": {"name": secret_name, "key": "token"}}}
#            ],
#            "command": ["oneclient", "--opt",  "allow_other",  "-f", "/mnt/oneclient",
#                        "--monitoring-type", "graphite", "--monitoring-level-full",
#                        "--monitoring-period", "10", "--graphite-url", 
#                        "tcp://149.156.10.216:2003", "--graphite-namespace-prefix",
#                        "cs3jupyter"],
#            "securityContext": {
#                "runAsUser": 0,
#                "privileged": True,
#                "capabilities": {"add": ["SYS_ADMIN"]},
#            },
#            "volumeMounts": [
#                {"mountPath": "/mnt/oneclient:shared", "name": "oneclient"},
#            ],
#            "lifecycle": {
#                  "preStop": { "exec": {"command": ["fusermount", "-uz", "/mnt/oneclient"]}},
#            },
#        }]
#        # add the oneclient volume to the pod
#        vols = []
#        for v in self.volumes:
#            self.log.info(v)
#            if 'emptyDir' in v and v['name'] == 'oneclient':
#                self.log.info("oneclient volume is already there, skipping")
#                break
#        else:
#            self.log.info("Add volume and volumemounts for oneclient")
#            self.volumes.append({
#                'name': 'oneclient',
#                'emptyDir': {}
#            })
#            self.volume_mounts.append({'mountPath': '/datahub:shared', 'name': 'oneclient'})
#            self.volumes.append({
#                'name': 'oneclient-token',
#                'secret': {'secretName': secret_name}
#            })
#            self.volume_mounts.append({'mountPath': '/onedata-token', 'name': 'oneclient-token'})
#        # we are done :)
#        pod_info = yield super().start()
#        return pod_info
#
#    def get_env(self):
#        env = super().get_env()
#        env.update({
#            'ONEZONE_HOST': 'https://datahub.egi.eu',
#            'ONEZONE_TOKEN_FILE': '/onedata-token/token',
#        })
#        return env
#
