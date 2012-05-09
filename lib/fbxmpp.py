from tornado import iostream
from tornado.escape import utf8
import socket
import ssl
import re
import base64
import logging
import urlparse
import urllib

class FacebookXMPP:
    STREAM_XML = '<stream:stream ' +\
      'xmlns:stream="http://etherx.jabber.org/streams" ' +\
      'version="1.0" xmlns="jabber:client" to="chat.facebook.com" ' +\
      'xml:lang="en" xmlns:xml="http://www.w3.org/XML/1998/namespace">\n'
    AUTH_XML = '<auth xmlns="urn:ietf:params:xml:ns:xmpp-sasl" ' +\
      'mechanism="X-FACEBOOK-PLATFORM"></auth>\n'
    CLOSE_XML = '</stream:stream>\n'
    RESOURCE_XML = '<iq type="set" id="3">' +\
      '<bind xmlns="urn:ietf:params:xml:ns:xmpp-bind">' +\
      '<resource>fb_xmpp_script</resource></bind></iq>\n'
    SESSION_XML = '<iq type="set" id="4" to="chat.facebook.com">' +\
      '<session xmlns="urn:ietf:params:xml:ns:xmpp-session"/></iq>\n'
    START_TLS = '<starttls xmlns="urn:ietf:params:xml:ns:xmpp-tls"/>\n'
    
    def __init__(self, key, secret, access_token):
        self.key = key
        self.secret = secret
        self.access_token = access_token
        
    def send_xml(self, xml):
        logging.debug('> %s' % xml)
        self.stream.write(xml)
    
    def connect(self, host='chat.facebook.com', port=5222):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.stream = iostream.IOStream(self.sock)
        self.stream.set_close_callback(self._on_close)
        self.stream.connect((host, port), self._on_connect)
        #self.stream.read_bytes(4096, callback=None, streaming_callback=self._on_read)
    
    def _on_close(self):
        logging.error('CLOSE')
        
    def _on_read(self, data):
        try:
            print data
            #logging.info("< %r" % data)
        except:
            logging.excception("OHMY")
            pass
        
    def _on_connect(self):
        self.send_xml(self.STREAM_XML)
        self.send_xml(self.START_TLS)
        self.stream.read_until('proceed', self._on_start_tls)
        
    def _on_start_tls(self, data):
        logging.debug("PROCEED")
        self.sock = ssl.wrap_socket(self.sock,
                                    do_handshake_on_connect=False,
                                    server_side = False, 
                                    ssl_version = ssl.PROTOCOL_TLSv1)
        self.stream = iostream.SSLIOStream(self.sock)
        self.stream.set_close_callback(self._on_close)
        self.send_xml(self.STREAM_XML)
        self.send_xml(self.AUTH_XML)
        self.stream.read_until('/challenge>', self._on_challenge)
    
    def _on_challenge(self, data):
        logging.debug("got challenge: %r" % data)
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
        logging.debug("got challenge success: %r" % data)
        self.send_xml(self.STREAM_XML)
        self.send_xml(self.RESOURCE_XML)
        self.stream.read_until('</jid>', self._on_jid)
    
    def _on_jid(self, data):
        logging.debug("got jid: %r" % data)
        match = re.match(r'.*<jid>([^<]*)', data, re.I|re.M)
        if not match:
            pass
        self.jid = match.group(1)
        self.send_xml(self.SESSION_XML)
        xml = '<iq type="get" id="3" from="%s"><query xmlns="jabber:iq:roster"/></iq>' % self.jid
        self.send_xml(xml)
        self.stream.read_bytes(1024*64, callback=self._on_read, streaming_callback=self._on_read)
        
    