"""
EGI Check-in + datahub authenticator for JupyterHub

Uses OpenID Connect with aai.egi.eu, fetches DataHub token 
and keeps it in auth_state
"""
from tornado import gen
from tornado.httpclient import HTTPRequest, AsyncHTTPClient, HTTPError

from oauthenticator.egicheckin import EGICheckinAuthenticator

class DataHubAuthenticator(EGICheckinAuthenticator):
    @gen.coroutine
    def authenticate(self, handler, data=None):
        user_data = yield super(DataHubAuthenticator,
                                self).authenticate(handler, data)
        self.log.error("SOMETHING: %s",  user_data)
        http_client = AsyncHTTPClient()
        # We now go to the datahub to get a token
        req = HTTPRequest('https://datahub.egi.eu/api/v3/onezone/user/client_tokens',
                          headers={'content-type': 'application/json',
                                   'x-auth-token': 'egi:%s' % user_data['auth_state']['access_token']},
                          method='GET',
                          body='')
        try:
            resp = yield http_client.fetch(req)
            datahub_response = json.loads(resp.body.decode('utf8', 'replace'))
            if datahub_response['tokens']:
                onedata_token = datahub_response['tokens'].pop(0)
        except HTTPError as e:
            self.log.info("Something failed! %s", e)
            raise e
        # we don't have a token, create one
        req = HTTPRequest('https://datahub.egi.eu/api/v3/onezone/user/client_tokens',
                          headers={'content-type': 'application/json',
                                   'x-auth-token': 'egi:%s' % user_data['auth_state']['access_token']},
                          method='GET',
                          body='')
        try:
            resp = yield http_client.fetch(req)
            datahub_response = json.loads(resp.body.decode('utf8', 'replace'))
            onedata_token = datahub_response['token']
        except HTTPError as e:
            self.log.info("Something failed! %s", e)
            raise e
        user_data['auth_state'].update({'onedata_token': onedata_token})

    @gen.coroutine
    def pre_spawn_start(self, user, spawner):
        yield super(DataHubAuthenticator, self).pre_spawn_data(user, spawner)
        auth_state = yield user.get_auth_state()
        if not auth_state:
            # auth_state not enabled
            return
        spawner.environment['DATAHUB_TOKEN'] = auth_state.get('onedata_token')
