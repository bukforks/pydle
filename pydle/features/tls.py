## tls.py
# TLS support.
import ssl

from pydle import async
import pydle.protocol
from pydle.features import rfc1459
from .. import connection

__all__ = [ 'TLSSupport' ]

DEFAULT_TLS_PORT = 6697


class TLSSupport(rfc1459.RFC1459Support):
    """
    TLS support.

    Pass tls_client_cert, tls_client_cert_key and optionally tls_client_cert_password to have pydle send a client certificate
    upon TLS connections.
    """

    ## Internal overrides.

    def __init__(self, *args, tls_client_cert=None, tls_client_cert_key=None, tls_client_cert_password=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tls_client_cert = tls_client_cert
        self.tls_client_cert_key = tls_client_cert_key
        self.tls_client_cert_password = tls_client_cert_password

    @async.coroutine
    def connect(self, hostname=None, port=None, tls=False, **kwargs):
        """ Connect to a server, optionally over TLS. See pydle.features.RFC1459Support.connect for misc parameters. """
        if not port:
            if tls:
                port = DEFAULT_TLS_PORT
            else:
                port = rfc1459.protocol.DEFAULT_PORT
        return (yield from super().connect(hostname, port, tls=tls, **kwargs))

    @async.coroutine
    def _connect(self, hostname, port, reconnect=False, password=None, encoding=pydle.protocol.DEFAULT_ENCODING, channels=[], tls=False, tls_verify=False, source_address=None):
        """ Connect to IRC server, optionally over TLS. """
        self.password = password

        # Create connection if we can't reuse it.
        if not reconnect:
            self._autojoin_channels = channels
            self.connection = connection.Connection(hostname, port,
                source_address=source_address,
                tls=tls, tls_verify=tls_verify,
                tls_certificate_file=self.tls_client_cert,
                tls_certificate_keyfile=self.tls_client_cert_key,
                tls_certificate_password=self.tls_client_cert_password,
                eventloop=self.eventloop)
            self.encoding = encoding

        # Connect.
        yield from self.connection.connect()


    ## API.

    @async.coroutine
    def whois(self, nickname):
        info = yield from super().whois(nickname)
        info.setdefault('secure', False)
        return info


    ## Message callbacks.

    @async.coroutine
    def on_raw_421(self, message):
        """ Hijack to ignore absence of STARTTLS support. """
        if message.params[0] == 'STARTTLS':
            return
        yield from super().on_raw_421(message)

    @async.coroutine
    def on_raw_451(self, message):
        """ Hijack to ignore absence of STARTTLS support. """
        if message.params[0] == 'STARTTLS':
            return
        yield from super().on_raw_451(message)

    @async.coroutine
    def on_raw_670(self, message):
        """ Got the OK from the server to start a TLS connection. Let's roll. """
        self.connection.tls = True
        self.connection.setup_tls()

    @async.coroutine
    def on_raw_671(self, message):
        """ WHOIS: user is connected securely. """
        target, nickname = message.params[:2]
        info = {
            'secure': True
        }

        if nickname in self._whois_info:
            self._whois_info[nickname].update(info)

    @async.coroutine
    def on_raw_691(self, message):
        """ Error setting up TLS server-side. """
        self.logger.error('Server experienced error in setting up TLS, not proceeding with TLS setup: %s', message.params[0])
