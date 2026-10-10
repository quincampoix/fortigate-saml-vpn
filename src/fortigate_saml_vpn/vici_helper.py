
import argparse
import sys

import vici


def unload_eap_secret(secret_id: str) -> None:
    session = vici.Session()
    session.unload_shared({"id": secret_id})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["unload-eap"])
    parser.add_argument("--secret-id", default="eap-fortigate")
    args = parser.parse_args()

    try:
        if args.command == "unload-eap":
            unload_eap_secret(args.secret_id)
    except Exception as exc:
        print(f"VICI error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
