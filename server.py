#!/usr/bin/env python

import os
import tornado
import tornado.options
import tornado.web
import settings
import logging
import functools
import simplejson as json

from lib.fbxmpp import FacebookXMPP


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
    def get(self):
        to = self.get_argument('to')
        message = self.get_argument('message')
        access_token = self.get_argument('access_token')

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
