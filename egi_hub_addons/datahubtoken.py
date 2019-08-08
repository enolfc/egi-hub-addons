"""
EGI Check-in + datahub authenticator for JupyterHub

Uses OpenID Connect with aai.egi.eu, fetches DataHub token
and keeps it in auth_state
"""

import json

from tornado import gen
from tornado.httpclient import HTTPRequest, AsyncHTTPClient, HTTPError
from traitlets import Unicode

from oauthenticator.egicheckin import EGICheckinAuthenticator

class DataHubAuthenticator(EGICheckinAuthenticator):
    onezone_url = Unicode(default_value='https://datahub.egi.eu',
                          config=True,
                          help="""Onedata onezone URL""")
    oneprovider_host = Unicode(default_value='',
                               config=True,
                               help="""Onedata oneprovider hostname""")

    @gen.coroutine
    def authenticate(self, handler, data=None):
        user_data = yield super(DataHubAuthenticator,
                                self).authenticate(handler, data)
        http_client = AsyncHTTPClient()
        onedata_token = None
        # We now go to the datahub to get a token
        req = HTTPRequest(self.onezone_url + '/api/v3/onezone/user/client_tokens',
                          headers={'content-type': 'application/json',
                                   'x-auth-token': 'egi:%s' % user_data['auth_state']['access_token']},
                          method='GET')
        try:
            resp = yield http_client.fetch(req)
            datahub_response = json.loads(resp.body.decode('utf8', 'replace'))
            if datahub_response['tokens']:
                onedata_token = datahub_response['tokens'].pop(0)
        except HTTPError as e:
            self.log.info("Something failed! %s", e)
            raise e
        if not onedata_token:
            # we don't have a token, create one
            req = HTTPRequest(self.onezone_url + '/api/v3/onezone/user/client_tokens',
                              headers={'content-type': 'application/json',
                                       'x-auth-token': 'egi:%s' % user_data['auth_state']['access_token']},
                              method='POST',
                              body='')
            try:
                resp = yield http_client.fetch(req)
                datahub_response = json.loads(resp.body.decode('utf8', 'replace'))
                onedata_token = datahub_response['token']
            except HTTPError as e:
                self.log.info("Something failed! %s", e)
                raise e
        user_data['auth_state'].update({'onedata_token': onedata_token})
        return user_data

    @gen.coroutine
    def pre_spawn_start(self, user, spawner):
        yield super(DataHubAuthenticator, self).pre_spawn_start(user, spawner)
        auth_state = yield user.get_auth_state()
        if not auth_state:
            # auth_state not enabled
            return
        spawner.environment['ONECLIENT_ACCESS_TOKEN'] = auth_state.get('onedata_token')
        spawner.environment['ONEPROVIDER_HOST'] = self.oneprovider_host
