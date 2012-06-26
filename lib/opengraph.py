import functools
import logging
import tornado.httpclient

log = logging.getLogger(__name__)


def get_permissions(access_token, callback, timeout=5000):
    uri = 'https://graph.facebook.com/me/permissions?access_token={}'.format(access_token)

    log.debug('get_permissions: {}'.format(uri))

    http_request = tornado.httpclient.HTTPRequest(uri, 'GET', connect_timeout=timeout)
    http_client = tornado.httpclient.AsyncHTTPClient()

    cb = functools.partial(_permissions_cb, callback=callback)

    http_client.fetch(http_request, callback=cb)

def _permissions_cb(response, callback):
    callback(response)
