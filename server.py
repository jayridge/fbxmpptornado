import sys
import os
import tornado
import tornado.auth
import tornado.options
import tornado.web
from tornado.escape import utf8
import settings
import logging
import functools
from lxml import etree
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
        """write an api error in the appropriate response format"""
        self.api_response(status_code=status_code, status_txt=status_txt, data=data)

    def api_response(self, data, status_code=200, status_txt="OK"):
        """write an api response in json"""
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.finish(json.dumps(dict(data=data, status_code=status_code, status_txt=status_txt)))

    def get_current_user(self):
        data = self.get_secure_cookie("user")
        if data:
            return json.loads(data)


class IndexHandler(BaseHandler):
    def get(self):
        self.render("index.tpl")

class TestHandler(BaseHandler,
                  tornado.auth.FacebookGraphMixin):
    @tornado.web.asynchronous
    def get(self):
        user = self.get_current_user()
        print user, self.settings
        xmpp = FacebookXMPP(self.settings["facebook_api_key"],
                            self.settings["facebook_secret"],
                            user['access_token'])
        xmpp.connect(callback=functools.partial(self._on_ready, xmpp=xmpp))

    def _on_ready(self, xmpp):
        xmpp.get_roster(callback=functools.partial(self._on_roster, xmpp=xmpp))

    def _on_roster(self, root, xmpp):
        to = '-500126071@chat.facebook.com'
        message = 'monkey balls'
        xmpp.send_message(to, message, callback=functools.partial(self._on_send, xmpp=xmpp))
   
    def _on_send(self, root, xmpp):
        print etree.tostring(root)
        self.render("index.tpl")
    

class FacebookHandler(BaseHandler,
                      tornado.auth.FacebookGraphMixin):
    @tornado.web.asynchronous
    def get(self):
        if self.get_argument("code", False):
            self.get_authenticated_user(
                redirect_uri='http://127.0.0.1:8888/login',
                client_id=self.settings["facebook_api_key"],
                client_secret=self.settings["facebook_secret"],
                code=self.get_argument("code"),
                callback=self.async_callback( self._on_login))
            return
        self.authorize_redirect(redirect_uri='http://127.0.0.1:8888/login',
                                client_id=self.settings["facebook_api_key"],
                                extra_params={"scope": "offline_access,xmpp_login"})

    def _on_login(self, user):
        logging.info(user)
        self.set_secure_cookie("user", json.dumps(user))
        self.render("index.tpl")


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
        'static_path': os.path.join(os.path.dirname(__file__), "www"),
        'template_path': os.path.join(os.path.dirname(__file__), "www"),
        'cookie_secret': 'a horse is a horse of course of course',
        'debug': True,
    }
    application = tornado.web.Application([
        (r"/", IndexHandler),
        (r"/login", FacebookHandler),
        (r"/test", TestHandler),
        (r"/stats", StatsHandler),
    ], **app_settings)
    application.listen(tornado.options.options.port)
    logging.info("listening on http://%s:%d" % (tornado.options.options.host,
                                                tornado.options.options.port))
    tornado.ioloop.IOLoop.instance().start()
