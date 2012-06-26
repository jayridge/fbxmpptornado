import socket
import ssl
import re
import base64
import logging
import urlparse
import urllib

from cStringIO import StringIO
from lxml import etree
from tornado import iostream, ioloop
from tornado.escape import utf8


class FacebookXMPP:
    STREAM_XML = '<stream:stream ' +\
      'xmlns:stream="http://etherx.jabber.org/streams" ' +\
      'version="1.0" xmlns="jabber:client" to="chat.facebook.com" ' +\
      'xml:lang="en" xmlns:xml="http://www.w3.org/XML/1998/namespace">'
    AUTH_XML = '<auth xmlns="urn:ietf:params:xml:ns:xmpp-sasl" ' +\
      'mechanism="X-FACEBOOK-PLATFORM"></auth>'
    CLOSE_XML = '</stream:stream>'
    RESOURCE_XML = '<iq type="set" id="3">' +\
      '<bind xmlns="urn:ietf:params:xml:ns:xmpp-bind">' +\
      '<resource>fb_xmpp_script</resource></bind></iq>'
    SESSION_XML = '<iq type="set" id="4" to="chat.facebook.com">' +\
      '<session xmlns="urn:ietf:params:xml:ns:xmpp-session"/></iq>'
    START_TLS = '<starttls xmlns="urn:ietf:params:xml:ns:xmpp-tls"/>'

    def __init__(self, key, secret, access_token):
        self.state = 'NONE'
        self.id = 4
        self.key = key
        self.secret = secret
        self.access_token = access_token
        self.cb_map = {}
        self.buffer = StringIO()

    def get_id(self):
        self.id += 1
        return str(self.id)

    def send_xml(self, xml):
        xml = utf8(xml)
        logging.debug('> %s' % xml)
        self.stream.write(xml)

    def get_roster(self, callback):
        id = self.get_id()
        xml = '<iq type="get" id="%s" from="%s"><query xmlns="jabber:iq:roster"/></iq>' \
            % (id, self.jid)
        self.cb_map[id] = callback
        self.send_xml(xml)

    def send_message(self, to, message):
        xml = '<message type="chat" from="%s" to="%s" xml:lang="en"><body>%s</body></message>' \
            % (self.jid, to, message)
        self.send_xml(xml)

    def connect(self, host='chat.facebook.com', port=5222, callback=None):
        self.ready_callback = callback
        self.state = 'CONNECTING'
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.stream = iostream.IOStream(self.sock)
        self.stream.set_close_callback(self._on_close)
        self.stream.connect((host, port), self._on_connect)

    def close(self):
        self.state = 'CLOSING'
        self.send_xml(self.CLOSE_XML)

    def _on_close(self):
        self.state = 'CLOSED'
        logging.info('CLOSED')

    def _on_read(self, data):
        if self.state is 'CLOSING':
            return
        self.buffer.write(data)
        if data.endswith('>'):
            try:
                data = self.buffer.getvalue()
                root = etree.fromstring(data)
                id = root.xpath('//iq/@id')
                logging.debug("id %r" % id)
                if id and id[0] in self.cb_map:
                    id = id[0]
                    try:
                        callback = self.cb_map.get(id)
                        callback(root)
                    except:
                        logging.exception("callback failed: %r" % id)
                        print etree.tostring(root)
                    del(self.cb_map[id])
                else:
                    logging.warning("no callback for message: %r" % data)
                    pass
                self.buffer.truncate(0)
            except:
                logging.exception("parse failed: %.200r" % self.buffer.getvalue())
                pass

    def _on_connect(self):
        self.send_xml(self.STREAM_XML)
        self.send_xml(self.START_TLS)
        self.stream.read_until('proceed', self._on_start_tls)

    def _on_start_tls(self, data):
        self.sock = ssl.wrap_socket(self.sock,
                                    do_handshake_on_connect=False,
                                    server_side = False,
                                    ssl_version = ssl.PROTOCOL_TLSv1)

        try:
            ioloop.IOLoop.instance().remove_handler(self.sock)
        except:
            pass

        self.stream = iostream.SSLIOStream(self.sock)
        self.stream.set_close_callback(self._on_close)
        self.send_xml(self.STREAM_XML)
        self.send_xml(self.AUTH_XML)
        self.stream.read_until('/challenge>', self._on_challenge)

    def _on_challenge(self, data):
        match = re.match(r'.*<\s*challenge[^>]+>([^<]*)', data, re.I|re.M)
        if not match:
            pass
        challenge = urlparse.parse_qs(base64.b64decode(match.group(1)))
        params = {
            'method': challenge['method'][0],
            'nonce': challenge['nonce'][0],
            'access_token': self.access_token,
            'api_key': self.key,
            'call_id': 0,
            'v': '1.0'
        }
        print params
        response = urllib.urlencode(params)
        xml = '<response xmlns="urn:ietf:params:xml:ns:xmpp-sasl">%s</response>\n' \
              % base64.b64encode(response)
        self.send_xml(xml)
        self.stream.read_until('success', self._on_challenge_success)

    def _on_challenge_success(self, data):
        print data
        self.send_xml(self.STREAM_XML)
        self.send_xml(self.RESOURCE_XML)
        self.stream.read_until('</iq>', self._on_jid)

    def _on_jid(self, data):
        print data
        match = re.match(r'.*<jid>([^<]*)', data, re.I|re.M)
        if not match:
            pass
        self.jid = match.group(1)
        self.send_xml(self.SESSION_XML)
        self.stream.read_until('</iq>', self._ready)

    def _ready(self, data):
        self.state = 'READY'
        if self.ready_callback:
            self.ready_callback()

        def _noop(self, data):
            pass
        self.stream.read_bytes(1024*64, callback=_noop, streaming_callback=self._on_read)
