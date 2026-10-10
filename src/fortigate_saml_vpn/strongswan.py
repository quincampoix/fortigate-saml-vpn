import subprocess
import os
import subprocess
import tempfile
import sys

CONNECTION_NAME = "fortigate"


class StrongSwanError(Exception):
    """Raised when an operation with strongSwan fails."""



def ensure_strongswan_running() -> None:
    result = subprocess.run(
        ["systemctl", "is-active", "--quiet", "strongswan.service"],
        check=False,
    )

    if result.returncode == 0:
        return

    raise StrongSwanError(
        "strongSwan is not running.\n"
        "Start it with:\n"
        "  sudo systemctl start strongswan.service"
    )

def load_session(
    saml_uid: str,
    token_id: str,
) -> None:
    session_config = f"""
include /etc/swanctl/conf.d/fortinet.conf

connections {{
    fortigate {{
        local {{
            eap_id = "{saml_uid}"
        }}
    }}
}}

secrets {{
    eap-fortigate {{
        id = "{saml_uid}"
        secret = "{token_id}"
    }}
}}
"""

    temp_path = None

    try:
        fd, temp_path = tempfile.mkstemp(
            prefix="fortigate-saml-",
            suffix=".conf",
        )

        os.fchmod(fd, 0o600)

        with os.fdopen(fd, "w") as file:
            file.write(session_config)

        result = subprocess.run(
            [
                "sudo",
                "swanctl",
                "--load-conns",
                "--file",
                temp_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise StrongSwanError(
                result.stderr.strip()
                or result.stdout.strip()
                or "Unable to load strongSwan connection"
            )

        result = subprocess.run(
            [
                "sudo",
                "swanctl",
                "--load-creds",
                "--file",
                temp_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise StrongSwanError(
                result.stderr.strip()
                or result.stdout.strip()
                or "Unable to load strongSwan credentials"
            )

    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass

def initiate(connection_name: str) -> None:
    result = subprocess.run(
        [
            "sudo",
            "swanctl",
            "--initiate",
            "--child",
            connection_name,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise StrongSwanError(
            result.stderr.strip()
            or result.stdout.strip()
            or "Unable to initiate VPN connection"
        )

def disconnect(connection_name: str) -> None:
    result = subprocess.run(
        [
            "sudo",
            "swanctl",
            "--terminate",
            "--ike",
            connection_name,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise StrongSwanError(
            result.stderr.strip()
            or result.stdout.strip()
            or "Unable to disconnect VPN"
        )


def get_status(connection_name: str = "fortigate") -> dict:
    result = subprocess.run(
        ["sudo", "swanctl", "--list-sas"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise StrongSwanError(
            result.stderr.strip()
            or "Unable to retrieve VPN status"
        )

    connected = any(
        line.startswith(f"{connection_name}:")
        and "ESTABLISHED" in line
        for line in result.stdout.splitlines()
    )

    return {
        "connected": connected,
        "raw": result.stdout,
    }


def unload_session(secret_id: str = "eap-fortigate") -> None:
    """Remove the temporary EAP secret from strongSwan."""

    result = subprocess.run(
        [
            "sudo",
            sys.executable,
            "-m",
            "fortigate_saml_vpn.vici_helper",
            "unload-eap",
            "--secret-id",
            secret_id,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise StrongSwanError(
            result.stderr.strip() or "Unable to unload EAP secret"
        )
    