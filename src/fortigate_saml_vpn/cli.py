from fortigate_saml_vpn.strongswan import unload_session
import argparse

from .config import ConfigError, load_config
from .saml import (
    SamlError,
    authenticate,
)
from .strongswan import (
    StrongSwanError,
    disconnect,
    ensure_strongswan_running,
    get_status,
    initiate,
    load_session,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fortigate-saml-vpn",
        description=(
            "SAML authentication helper for FortiGate "
            "IKEv2 VPNs using strongSwan."
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "connect",
        help="Authenticate with SAML and connect the VPN",
    )

    subparsers.add_parser(
        "disconnect",
        help="Disconnect the VPN and restore network settings",
    )

    subparsers.add_parser(
        "status",
        help="Show the current VPN status",
    )

    subparsers.add_parser(
        "saml",
        help="Test FortiGate SAML pre-authentication",
    )

    return parser
   

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 1    


    if args.command == "disconnect":
        try:
            ensure_strongswan_running()

            status = get_status(
                connection_name=config["strongswan"]["connection"]
            )

            if status["connected"]:
                print("Disconnecting VPN...")
                disconnect(
                    connection_name=config["strongswan"]["connection"]
                )
                print("VPN disconnected successfully.")
            else:
                print("VPN is already disconnected.")

            print("Ensuring temporary credentials are removed...")
            unload_session()

        except StrongSwanError as exc:
            print(f"Disconnection error: {exc}")
            return 1

        return 0


    if args.command == "status":
        status = get_status(connection_name=config["strongswan"]["connection"])
        if "error" in status:
            print(f"VPN status: error ({status['error']})")
            return 1

        if status["connected"]:
            print("VPN status: connected")
        else:
            print("VPN status: disconnected")

        return 0


    if args.command == "saml":
        print("Starting SAML authentication...")

        try:
            token_id = authenticate(
                gateway=config["fortigate"]["gateway"],
                saml_port=config["fortigate"]["saml_port"],
            )
        except SamlError as exc:
            print(f"SAML error: {exc}")
            return 1

        print("SAML authentication successful.")
        print(f"Token ID received ({len(token_id)} characters).")

        return 0

    
    if args.command == "connect":
        session_loaded = False

        try:
            print("Checking strongSwan service...")
            ensure_strongswan_running()

            print("Checking VPN status...")
            status = get_status(
                connection_name=config["strongswan"]["connection"]
            )

            if status["connected"]:
                print("VPN is already connected.")
                return 0

            print("Starting SAML authentication...")
            session = authenticate(
                gateway=config["fortigate"]["gateway"],
                saml_port=config["fortigate"]["saml_port"]
            )
            print("SAML authentication successful.")

            # Set before loading: a partial failure may leave credentials behind.
            session_loaded = True

            print("Loading strongSwan session...")
            load_session(
                saml_uid=session.uid,
                token_id=session.token_id,
            )

            print("Initiating VPN connection...")
            initiate(
                connection_name=config["strongswan"]["connection"]
            )

        except (SamlError, StrongSwanError) as exc:
            print(f"Connection error: {exc}")

            if session_loaded:
                try:
                    print("Ensuring temporary credentials are removed...")
                    unload_session()
                except StrongSwanError as cleanup_exc:
                    print(f"Credential cleanup error: {cleanup_exc}")

            return 1

        print("VPN connected successfully.")
        return 0



if __name__ == "__main__":
    raise SystemExit(main())