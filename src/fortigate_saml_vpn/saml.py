import re
import secrets
import ssl
import urllib.error
import urllib.request
import json
import http.client
import threading
import webbrowser


from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from dataclasses import dataclass


@dataclass
class SamlSession:
    uid: str
    token_id: str
    username: str | None = None

class SamlCallbackHandler(BaseHTTPRequestHandler):
    token_id = None
    username = None
    callback_event = threading.Event()

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        token_ids = query.get("tokenid")
        usernames = query.get("username")

        if not token_ids:
            self.send_response(400)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return

        type(self).token_id = token_ids[0]

        if usernames:
            type(self).username = usernames[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        self.wfile.write(
            b"""
            <!doctype html>
            <html>
            <head>
                <title>VPN authentication successful</title>
                <script>
                    history.replaceState(null, "", "/success");
                    window.close();
                </script>
            </head>
            <body>
                <h2>VPN authentication successful</h2>
                <p>You can close this browser tab.</p>
            </body>
            </html>
            """
        )

        self.wfile.flush()

        type(self).callback_event.set()

    def log_message(self, format, *args):
        # Do not log callback URLs because they contain the token.
        pass

class SamlError(Exception):
    """Raised when the FortiGate SAML pre-authentication fails."""


def authenticate(
    gateway: str,
    saml_port: int,
    redirect_port: int = 8020,
    verify_tls: bool = True,
    timeout: int = 120,
) -> str:
    """
    Perform FortiGate SAML authentication and return the token ID.
    """

    SamlCallbackHandler.token_id = None
    SamlCallbackHandler.username = None
    SamlCallbackHandler.callback_event.clear()

    try:
        server = HTTPServer(
            ("127.0.0.1", redirect_port),
            SamlCallbackHandler,
        )
    except OSError as exc:
        raise SamlError(
            f"Unable to listen on localhost:{redirect_port}: {exc}"
        ) from exc

    server_thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    server_thread.start()
   

    try:
        saml_uid = generate_saml_uid()
        saml_url = request_saml_url(
            gateway=gateway,
            saml_port=saml_port,
            saml_uid=saml_uid,
            redirect_port=redirect_port,
            verify_tls=verify_tls,
        )

        print("Opening browser for SAML authentication...")
        
        if not webbrowser.open(saml_url):
            raise SamlError(
                "Unable to open the browser automatically"
            )

        if not SamlCallbackHandler.callback_event.wait(timeout):
            raise SamlError(
                "Timed out waiting for SAML authentication"
            )

        if not SamlCallbackHandler.token_id:
            raise SamlError(
                "SAML authentication completed without a token ID"
            )

        if SamlCallbackHandler.username:
            print("SAML username received.")    

        return SamlSession(
            uid=saml_uid,
            token_id=SamlCallbackHandler.token_id,
            username=SamlCallbackHandler.username,
        )

    finally:
        server.shutdown()
        server.server_close()


def generate_saml_uid() -> str:
    """
    Generate a random 128-bit identifier as 32 uppercase hexadecimal
    characters.

    Example:
        7F42B861DA1E4C87947B16E74AF9C321
    """
    return secrets.token_hex(16).upper()


def request_saml_url(
    gateway: str,
    saml_port: int,
    saml_uid: str,
    redirect_port: int = 8020,
    verify_tls: bool = True,
) -> str:
    """
    Start FortiGate SAML pre-authentication and return the SAML URL.

    This reproduces the FortiClient pre-authentication request without
    performing the browser authentication itself.
    """

    url = f"https://{gateway}:{saml_port}/saml_login?"

    raw_data = (
        f"UID={saml_uid}"
        f"&REDIRECT_PORT={redirect_port}"
    )

    body = json.dumps(
        {
            "type": "rawData",
            "bytes": raw_data,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": (
                "FortiSSLVPN "
                "(Linux; SV1 [SV{v=02.01; f=05;}])"
            ),
        },
    )

    ssl_context = ssl.create_default_context()

    if not verify_tls:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(
            request,
            context=ssl_context,
            timeout=10,
        ) as response:
            html = response.read().decode("utf-8", errors="replace")


    except (
        urllib.error.URLError,
        http.client.RemoteDisconnected,
        TimeoutError,
    ) as exc:
        raise SamlError(
            f"Unable to contact FortiGate SAML endpoint: {exc}"
        ) from exc

    match = re.search(
        r"""(?:window\.)?location(?:\.href)?\s*=\s*["']([^"']+)["']""",
        html,
        re.IGNORECASE,
    )

    if not match:
        raise SamlError(
            "FortiGate response did not contain a SAML redirect URL"
        )

    return match.group(1)