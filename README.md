# fortigate-saml-vpn

**A small experimental Linux CLI for connecting to FortiGate IPsec/IKEv2 VPNs using browser-based SAML authentication and strongSwan.**

This project started with a simple goal: I wanted to connect to my company's FortiGate VPN from Linux without relying on proprietary software. FortiClient was actually the last proprietary application I still needed on my Linux workstation, and I was determined to find a fully open-source alternative.

The challenge was that my company's VPN relied on browser-based SAML authentication combined with IPsec/IKEv2, and I couldn't find an existing open-source solution that worked with this particular setup.

This led me to explore whether **strongSwan**, a well-established open-source IPsec implementation, could be combined with FortiGate's SAML authentication mechanism.

After quite a bit of investigation, experimentation, and debugging, it turns out that it is possible — at least with the FortiGate configuration I had access to.

This repository is the result of that exploration.

> **Project status: Experimental**
>
> This is a small personal project, not a production-ready VPN client or a universal FortiClient replacement. It has been tested against one FortiGate environment, and compatibility with other configurations is currently unknown.

## Features

- Browser-based FortiGate SAML authentication, including Microsoft Entra ID.
- IPsec/IKEv2 VPN connections powered by strongSwan.
- Support for existing browser SSO sessions and MFA.
- Automatic retrieval of the temporary authentication token.
- Automatic browser tab closure after successful authentication.
- Simple `connect`, `status`, and `disconnect` commands.
- Automatic DNS configuration through strongSwan's `resolve` plugin, when properly configured.
- Targeted cleanup of temporary EAP credentials through the strongSwan VICI interface.
- TLS certificate verification for HTTPS communication with the FortiGate gateway.

## How it works

The application coordinates two distinct operations:

1. **SAML authentication:** Python opens the FortiGate authentication page in your browser, allowing your organization's identity provider to authenticate you.
2. **IKEv2 connection:** The authentication result is passed to strongSwan, which establishes the actual IPsec tunnel.

The interesting part is how these two operations are linked.

In the FortiGate environment used for this project, the client generates a temporary UID during SAML initialization. After successful browser authentication, FortiGate returns a `tokenid`.

The same UID is then used as the strongSwan EAP identity, while the `tokenid` is used as the temporary EAP secret.

This allows FortiGate to associate the IKEv2 authentication attempt with the previously authenticated SAML session.

The Python application does not implement IPsec, IKEv2, or SAML itself. It simply coordinates the components needed to make the connection work.

For a detailed explanation of the observed authentication flow, see [Protocol Notes](docs/protocol.md).

## Requirements

- Linux
- Python 3.11 or newer
- strongSwan with `swanctl` and VICI support
- A compatible FortiGate IPsec/IKEv2 VPN with browser-based SAML authentication
- A web browser
- `sudo` access for strongSwan operations

The project has primarily been developed and tested on **CachyOS (Arch Linux-based)**.

Other distributions may require adjustments, particularly for strongSwan service management and DNS integration.

## Quick start

Clone the repository:

```bash
git clone <https://github.com/quincampoix/fortigate-saml-vpn.git>
cd fortigate-saml-vpn
```

Create a Python virtual environment and install the application:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Create your local application configuration:

```bash
cp examples/config.toml config.toml
```

Example:

```toml
[fortigate]
gateway = "vpn.example.com"
saml_port = 1001

[strongswan]
connection = "fortigate"
```

strongSwan must also be configured with your organization's IKEv2 parameters, authentication settings, and pre-shared key.

The supplied `examples/swanctl.conf` can be used as a starting point.

**Do not attempt to connect before completing the strongSwan and DNS setup.**

See the [Installation Guide](docs/installation.md) for the full configuration procedure.

## Usage

Connect to the VPN:

```bash
fortigate-saml-vpn connect
```

Example output:

```text
Checking strongSwan service...
Checking VPN status...
Starting SAML authentication...
Opening browser for SAML authentication...
SAML username received.
SAML authentication successful.
Loading strongSwan session...
Initiating VPN connection...
VPN connected successfully.
```

Check the connection status:

```bash
fortigate-saml-vpn status
```

```text
VPN status: connected
```

Disconnect:

```bash
fortigate-saml-vpn disconnect
```

```text
Disconnecting VPN...
VPN disconnected successfully.
Ensuring temporary credentials are removed...
```

The disconnect command also attempts to remove the temporary EAP secret from strongSwan, even if the VPN is already disconnected.

### Run without activating the virtual environment

By default, the application is installed inside the Python virtual environment. You can run it directly without activating the environment:

```bash
./.venv/bin/fortigate-saml-vpn connect
```

To make the command available system-wide, you can optionally create a symbolic link:

```bash
sudo ln -s "$(pwd)/.venv/bin/fortigate-saml-vpn" /usr/local/bin/fortigate-saml-vpn
```

Run this command from the root directory of the cloned repository.

You can then use the application from any terminal:

```bash
fortigate-saml-vpn connect
fortigate-saml-vpn status
fortigate-saml-vpn disconnect
```

The application will continue using its dedicated Python virtual environment and installed dependencies. Activating the environment manually is no longer necessary.

**Note:** The symbolic link depends on the repository remaining at its original location. If you move or delete the repository, you will need to recreate the virtual environment and symbolic link.

## The story behind this project

Beyond simply getting a VPN connection working, this project became a really enjoyable technical investigation.

I was curious about how FortiClient could combine browser-based SAML authentication with an IKEv2/IPsec tunnel, and whether the same process could be reproduced using open-source tools.

I worked on this investigation together with **ChatGPT by OpenAI**, using it as a technical research and development partner.

We explored strongSwan, experimented with FortiGate's SAML endpoints, examined authentication parameters, investigated how the temporary credentials were passed to IKEv2, and gradually assembled a working Python implementation.

There were plenty of failed attempts, unexpected behaviors, and small discoveries along the way. That was actually one of the most rewarding parts of the project.

**The fun was not just in making it work, but in figuring out why it worked.**

I decided to publish the result in case it helps another Linux user facing a similar situation, or simply gives someone a useful starting point for further experimentation.

All implementation changes were reviewed and tested by the project author. ChatGPT provided assistance with research, reasoning, code development, debugging, and documentation.

## Known limitations

This project currently makes several assumptions based on the FortiGate environment used during development:

- The gateway exposes a compatible SAML authentication flow.
- SAML authentication returns a temporary token that can be used with IKEv2 EAP authentication.
- The VPN uses compatible IKEv2 authentication methods and cryptographic proposals.
- The strongSwan connection is configured using the expected connection name.
- The local SAML callback uses port `8020`.
- The Linux system provides compatible strongSwan and DNS resolver components.

The project has not been extensively tested against different FortiOS versions, identity providers, or Linux distributions.

It also has known security limitations, particularly around privileged Python execution and the handling of unexpected process termination.

**Please review the code and understand these limitations before using it, especially in a corporate environment.**

More information is available in the [Installation Guide](docs/installation.md) and [Protocol Notes](docs/protocol.md).

## Future improvements

If the project proves useful to others, some possible improvements include:

- Testing compatibility with additional FortiGate configurations and FortiOS versions.
- Supporting more Linux distributions and resolver implementations.
- Improving strongSwan service detection and management.
- Making the connection name fully configurable throughout the application.
- Replacing the current privileged Python execution with a restricted, root-owned helper.
- Improving cleanup after unexpected termination or partially established VPN connections.
- Making the local SAML callback port configurable.
- Adding automated tests.
- Potentially providing a simple desktop interface.

These are ideas rather than a committed roadmap. The main goal is to keep the project small, understandable, and useful.

## Documentation

- [Installation Guide](docs/installation.md) — Dependencies, strongSwan configuration, DNS setup, and troubleshooting.
- [Protocol Notes](docs/protocol.md) — Technical explanation of the observed SAML and IKEv2 authentication flow.
- [Application configuration example](examples/config.toml)
- [strongSwan configuration example](examples/swanctl.conf)

## Contributions and feedback

This is a personal experimental project, so contributions and suggestions are appreciated, but support and compatibility cannot be guaranteed.

## Credits

**Author:** Frédéric MARTIN (quincampoix)

**Technical research and development assistance:** ChatGPT by OpenAI.

This project was developed through a collaborative investigation involving practical testing, protocol exploration, iterative debugging, and AI-assisted development.

The project author performed the experiments, validated the results, and remains responsible for the code and its maintenance.

## License

See [LICENSE](LICENSE).

This project is independent and is not affiliated with, sponsored by, or endorsed by Fortinet, Microsoft, or the strongSwan project.

FortiGate and FortiClient are trademarks of Fortinet. Other product names belong to their respective owners.