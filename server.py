#!/usr/bin/env python

import os
import tornado
import tornado.options
import tornado.web
import settings
import lib.opengraph as opengraph
import logging
import functools
import simplejson as json

from lib.fbxmpp import FacebookXMPP


log = logging.getLogger(__name__)


class BaseHandler(tornado.web.RequestHandler):
    def get_int_argument(self, name, default=None):
        value = self.get_argument(name, default=default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def error(self, status_code=500, status_txt=None, data=None):
        self.api_response(status_code=status_code, status_txt=status_txt, data=data)

    def api_response(self, data, status_code=200, status_txt="OK"):
        self.set_status(status_code)
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.finish(json.dumps(dict(data=data, status_code=status_code, status_txt=status_txt)))

    def get_current_user(self):
        data = self.get_secure_cookie("user")
        if data:
            return json.loads(data)


class IndexHandler(BaseHandler):
    def get(self):
        self.render("index.tpl")


class SendHandler(BaseHandler):
    @tornado.web.asynchronous
    def post(self):
        to = self.get_argument('to')
        message = self.get_argument('message')
        access_token = self.get_argument('access_token')

        cb = functools.partial(self._on_permissions_ready, to=to, message=message, access_token=access_token)
        opengraph.get_permissions(access_token, callback=cb)


    def _on_permissions_ready(self, response, to, message, access_token):
        response = json.loads(response.body)

        if 'error' in response:
            error = response['error']

            if error.get('type') == 'OAuthException':
                status_code = 403
            else:
                status_code = 500

            self.error(status_txt=error.get('type'), data=error.get('message'), status_code=status_code)
            return
        else:
            permissions = response.get('data')

            if permissions:
                permissions = permissions[0].keys()
            else:
                permissions = []

        if 'xmpp_login' not in permissions:
            self.error(status_txt='XMPP_LOGIN_PERMISSION_REQUIRED', data='xmpp_login permission required', status_code=403)
            return

        to = '-{}@chat.facebook.com'.format(to)

        xmpp = FacebookXMPP(self.settings["facebook_api_key"],
                            self.settings["facebook_secret"],
                            access_token)

        xmpp.connect(callback=functools.partial(self._on_ready, xmpp=xmpp, to=to, message=message))


    def _on_ready(self, xmpp, to, message):
        print xmpp, to, message
        xmpp.send_message(to, message)
        xmpp.close()
        self.api_response(message)


class StatsHandler(BaseHandler):
    def get(self):
        self.api_response({})


if __name__ == "__main__":
    tornado.options.define("host", default="127.0.0.1", help="Listen address", type=str)
    tornado.options.define("port", default=8888, help="Listen on port", type=int)
    tornado.options.define("key", default=settings.get('key'), help="Facebook API Key", type=str)
    tornado.options.define("secret", default=settings.get('secret'), help="Facebook App Secret", type=str)
    tornado.options.parse_command_line()
    logging.getLogger().setLevel(settings.get('logging_level'))

    app_settings = {
        'facebook_api_key': tornado.options.options.key,
        'facebook_secret': tornado.options.options.secret,
        'debug': True,
    }

    application = tornado.web.Application([
        (r"/", IndexHandler),
        (r"/send", SendHandler),
        (r"/stats", StatsHandler),
    ], **app_settings)

    application.listen(tornado.options.options.port)
    logging.info('listening on: http://{}:{}'.format(tornado.options.options.host, tornado.options.options.port))
    tornado.ioloop.IOLoop.instance().start()
