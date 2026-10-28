#!/usr/bin/env python3

import sys

import vici


CONNECTION_NAME = "fortigate"


def main():
    try:
        session = vici.Session()

        for entry in session.list_sas():
            for name, details in entry.items():
                if name != CONNECTION_NAME:
                    continue

                if details.get("state") != b"ESTABLISHED":
                    continue

                child_sas = details.get("child-sas", {})

                for child in child_sas.values():
                    if child.get("state") == b"INSTALLED":
                        return 0

        return 1

    except Exception as exc:
        print(f"Unable to query VPN status: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())