# Installation Guide

This guide explains how to install and configure `fortigate-saml-vpn` on Linux.

The project uses Python to perform browser-based FortiGate SAML authentication and strongSwan to establish an IKEv2/IPsec VPN tunnel.

**Project status:** Experimental. Tested against one FortiGate environment. Installation steps may require adaptation for your Linux distribution and your organization's VPN configuration.

For an explanation of the authentication mechanism, see [Protocol Notes](protocol.md).

## 1. Prerequisites

Before starting, make sure you have:

- A Linux machine with Python 3.11 or newer.
- A working strongSwan installation with `swanctl` and VICI support.
- A browser capable of completing your organization's SAML authentication.
- `sudo` access to configure strongSwan and execute privileged VPN operations.
- Your organization's FortiGate VPN connection parameters.
- Permission from your organization to connect using a third-party VPN client.

The FortiGate must be configured for an IPsec/IKEv2 VPN using the SAML authentication mechanism supported by this project.

A working FortiClient configuration can be useful for identifying the required gateway and VPN parameters.

### Required VPN information

You will generally need:

| Parameter | Description |
|---|---|
| VPN gateway | FortiGate hostname or IP address |
| SAML port | HTTPS port used for SAML authentication (1001 in our tested environment) |
| IKE authentication | Authentication methods and any required pre-shared key |
| Local IKE identity | Identity expected by the FortiGate |
| IKE/ESP proposals | Cryptographic algorithms supported by the gateway |
| Traffic selectors | Network ranges permitted by the VPN configuration |

These values depend on your organization's FortiGate configuration. Do not assume that the example values will work for another gateway.

## 2. Install System Dependencies

The required strongSwan packages and service names vary across distributions.

### Arch Linux / CachyOS

Install strongSwan, Python, and Git:

```bash
sudo pacman -S strongswan python git
```

Verify that the required tools are available:

```bash
swanctl --version
python --version
```

### Debian / Ubuntu

Install Python, Git, and the strongSwan components used by `swanctl`:

```bash
sudo apt update
sudo apt install \
    python3 \
    python3-venv \
    python3-pip \
    git \
    strongswan-swanctl \
    charon-systemd \
    libcharon-extra-plugins
```

Depending on your distribution version, some packages may have different names or may already be installed.

Verify:

```bash
swanctl --version
python3 --version
```

**Note:** The Debian/Ubuntu instructions are provided as a starting point and have not yet been independently validated for this project.

### strongSwan service

The project expects a running strongSwan daemon with the VICI interface enabled.

On systems using the `strongswan` systemd service:

```bash
sudo systemctl enable --now strongswan
sudo systemctl status strongswan
```

On other distributions, the service may be named `strongswan-swanctl` or `strongswan-starter`, depending on the packaging and selected daemon.

Check the available units:

```bash
systemctl list-unit-files | grep -i strongswan
```

The application currently uses the `strongswan` service name when checking or starting the daemon. Distributions using a different unit name may require an adaptation.

Verify that VICI is available:

```bash
sudo swanctl --list-sas
```

If the command cannot connect to the VICI socket, resolve the strongSwan service or plugin configuration before continuing.

## 3. Download the Project

Clone the repository:

```bash
git clone https://github.com/quincampoix/fortigate-saml-vpn.git
cd fortigate-saml-vpn
```

### Create a Python virtual environment


Create a Python virtual environment:

```bash
python3 -m venv .venv
```

Activate the virtual environment using the command corresponding to your shell:

**Bash / Zsh (most Linux distributions):**

```bash
source .venv/bin/activate
```

**Fish (e.g., CachyOS with fish configured as the default shell):**

```fish
source .venv/bin/activate.fish
```

Then install the application:

```bash
python -m pip install -e .
```

**Note:** The virtual environment only needs to be activated during installation or when working on the project. If you configure the optional symbolic link described below, you can run `fortigate-saml-vpn` from any directory without activating the environment.

Verify:

```bash
fortigate-saml-vpn --help
```

The command should display the available CLI options and subcommands.

**Important:** Keep the virtual environment and its dependencies under your control. The current implementation uses the Python interpreter from this environment for a privileged VICI cleanup operation. See [Security Considerations](#10-security-considerations).


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



## 4. Configure strongSwan

strongSwan is responsible for establishing the IKEv2/IPsec tunnel.

The project includes an example configuration:

```text
examples/swanctl.conf
```

Review this file and adapt it to your FortiGate configuration.

### Create the permanent configuration

Create a configuration file:

```bash
sudo mkdir -p /etc/swanctl/conf.d
sudoedit /etc/swanctl/conf.d/fortinet.conf
```

Use the supplied example as a starting point.

Your permanent configuration must define the connection named `fortigate`, including the gateway, authentication settings, cryptographic proposals, and any required IKE pre-shared key.

**The connection name is significant:** the current application loads a temporary configuration that overrides the `fortigate` connection and its EAP identity.

The current implementation expects the connection to be named fortigate in the permanent strongSwan configuration. The application configuration must use the same name. Supporting a different connection name requires adapting the temporary configuration generation.

### Protect credentials

If the permanent configuration contains a pre-shared key, restrict access to the file:

```bash
sudo chown root:root /etc/swanctl/conf.d/fortinet.conf
sudo chmod 600 /etc/swanctl/conf.d/fortinet.conf
```

Do not commit this file or its credentials to Git.

### Configuration loading

The Python application loads a temporary configuration that includes:

```ini
include /etc/swanctl/conf.d/fortinet.conf
```

It then injects the current SAML UID and authentication token into strongSwan.

You should not need to manually edit the EAP identity or temporary EAP secret for each connection.

## 5. Configure the Application

Copy the supplied configuration example:

```bash
cp examples/config.toml config.toml
```

Edit `config.toml`:

```toml
[fortigate]
gateway = "vpn.example.com"
saml_port = 1001

[strongswan]
connection = "fortigate"
```

### Configuration parameters

| Parameter | Description |
|---|---|
| `fortigate.gateway` | FortiGate hostname used for SAML authentication |
| `fortigate.saml_port` | HTTPS port for the FortiGate SAML endpoint |
| `strongswan.connection` | Name of the strongSwan connection to initiate and manage |

Replace the example values with the correct values for your environment.

The `strongswan.connection` value must match the connection name defined in `/etc/swanctl/conf.d/fortinet.conf`. The current implementation uses `fortigate` as the connection name in its dynamically generated session configuration, so keep this name unless you also adapt the corresponding Python code.

The local IKE identity, authentication methods, cryptographic proposals, and pre-shared key are configured directly in strongSwan, not in the application's `config.toml`.

DNS configuration is also handled by strongSwan's `resolve` plugin, as described in the next section. No DNS server addresses or network interface settings are required in `config.toml`.

Keep your local `config.toml` out of version control. The repository's `.gitignore` should contain `/config.toml` so that `examples/config.toml` remains tracked.

## 6. Configure DNS Integration

In our tested environment, the FortiGate provides DNS server information through IKEv2.

strongSwan can apply these DNS settings automatically using its `resolve` plugin.

This avoids the need for the Python application to modify `/etc/resolv.conf` or manage DNS restoration itself.

### Configure the resolve plugin

Edit:

```text
/etc/strongswan.d/charon/resolve.conf
```

Example:

```ini
resolve {
    load = yes
    resolvconf {
        iface = enp2s0
    }
}
```

Replace `enp2s0` with your actual network interface.

To identify the interface used for your default route:

```bash
ip route get 1.1.1.1
```

Look for the interface name following `dev`.

### Resolver compatibility

The exact behavior depends on your distribution's DNS stack.

Our tested setup uses systemd-resolved with a compatible `resolvconf` integration.

Other distributions may use NetworkManager, `resolvconf`, `openresolv`, or a different resolver configuration.

The `resolve` plugin must be able to communicate with the resolver mechanism available on the system.

A configuration that works on CachyOS may require changes on Debian, Ubuntu, Fedora, or other distributions.

### Restart strongSwan

After modifying the plugin configuration:

```bash
sudo systemctl restart strongswan
```

Use the appropriate service name for your distribution.

**Warning:** Restarting strongSwan may disconnect other active IPsec tunnels managed by the same daemon.

### Verify DNS after connection

Once the VPN is connected:

```bash
resolvectl status
```

On systems using systemd-resolved, inspect the interface DNS settings.

The DNS servers supplied by the FortiGate should appear if the gateway provides them and the resolver integration is working.

After disconnection, verify that these temporary DNS settings are removed.

If your distribution does not use systemd-resolved, use its equivalent DNS inspection tools.

## 7. Connect to the VPN

Activate your Python virtual environment if necessary:

```bash
source .venv/bin/activate
```

Start the VPN connection:

```bash
fortigate-saml-vpn connect
```

Expected output:

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

### Browser authentication

The application opens your default browser to complete the FortiGate SAML authentication.

Depending on your organization's identity provider configuration, you may need to:

- Sign in to your corporate account.
- Complete multifactor authentication.
- Approve the authentication request.

If an existing browser session is valid, the process may complete without additional interaction.

After successful authentication, the browser is redirected to a local callback listener on:

```text
http://127.0.0.1:8020/
```

The success page attempts to close the browser tab automatically.

Some browsers may refuse automatic tab closure. In that case, simply close the success page manually.

The application then initiates the IKEv2 tunnel through strongSwan.

## 8. Check Status and Disconnect

### Check VPN status

```bash
fortigate-saml-vpn status
```

Example:

```text
VPN status: connected
```

or:

```text
VPN status: disconnected
```

### Disconnect

```bash
fortigate-saml-vpn disconnect
```

Example:

```text
Disconnecting VPN...
VPN disconnected successfully.
Ensuring temporary credentials are removed...
```

If the VPN is already disconnected:

```text
VPN is already disconnected.
Ensuring temporary credentials are removed...
```

The disconnect command also attempts to remove the temporary EAP credential from strongSwan.

This operation is safe to repeat.

### Verify credential cleanup

For troubleshooting, you can inspect the identifiers of loaded strongSwan shared secrets:

```bash
sudo swanctl --list-sas
```

To inspect shared-secret identifiers through VICI, if the system Python provides the VICI bindings:

```bash
sudo /usr/bin/python -c \
  'import vici; print(vici.Session().get_shared())'
```

After disconnection, the temporary `eap-fortigate` identifier should no longer be present.

The permanent `ike-fortigate` credential may remain loaded.

The VICI output shown here lists credential identifiers, not their secret values.

## 9. Troubleshooting

### Cannot connect to VICI

Possible causes:

- The strongSwan daemon is not running.
- The VICI plugin is unavailable or disabled.
- The expected VICI socket is missing.
- The command lacks the required permissions.

Check:

```bash
sudo systemctl status strongswan
sudo swanctl --list-sas
```

### SAML authentication does not complete

Check that:

- The FortiGate hostname and SAML port are correct.
- The SAML endpoint is reachable.
- The browser can reach the identity provider.
- The local callback port 8020 is available.
- The authentication process is permitted by your organization's policies.

You can inspect the local listener while authentication is running:

```bash
ss -ltn | grep ':8020'
```

### SAML succeeds but IKEv2 fails

Possible causes include:

- Incorrect local or remote IKE identities.
- Incorrect pre-shared key.
- Unsupported IKE or ESP proposals.
- Traffic selector mismatch.
- A SAML UID that does not match the EAP identity.
- An expired or rejected temporary authentication token.
- Different FortiGate behavior from the environment tested by this project.

Inspect the strongSwan logs:

```bash
sudo journalctl -u strongswan -n 100 --no-pager
```

**Caution:** Authentication logs may contain sensitive details. Review and redact them before sharing.

### VPN connects but internal DNS does not work

Check:

```bash
resolvectl status
```

Verify that the DNS servers provided by the gateway are installed on the expected interface.

Also verify that your resolver implementation is compatible with the strongSwan `resolve` plugin configuration.

### VPN disconnects but credentials remain loaded

Try:

```bash
fortigate-saml-vpn disconnect
```

The command attempts credential cleanup even when the VPN is already disconnected.

If cleanup fails, inspect the reported VICI error and verify that the privileged helper can access the strongSwan VICI socket.

## 10. Security Considerations

This is an experimental, community-developed project.

It is not affiliated with or endorsed by Fortinet, strongSwan, or Microsoft.

The current implementation includes some important security precautions:

- TLS certificate verification for FortiGate HTTPS requests.
- Cryptographically random SAML session identifiers.
- A callback listener bound to localhost.
- Temporary credential files with restricted permissions.
- Targeted removal of temporary EAP credentials.
- No intentional logging of SAML authentication tokens.

However, the implementation has not undergone a formal security audit.

### Privileged Python execution

The current version uses `sudo` to execute a Python helper from the application's virtual environment for VICI credential cleanup.

Because this environment is typically writable by the local user, it is **not a hardened privilege boundary**.

Users should understand this limitation before installing the project.

A future implementation may introduce a root-owned helper with a restricted execution environment.

### Organizational policies

Before using this project, verify that your organization's security policies permit third-party VPN clients.

Do not share VPN pre-shared keys, SAML tokens, internal gateway details, or private configuration files in public issues or logs.

## 11. Current Limitations

The project has currently been tested against a single FortiGate environment.

Known limitations include:

- Distribution-specific strongSwan service and packaging differences.
- Distribution-specific DNS resolver integration.
- A fixed local SAML callback port (8020).
- Assumptions about FortiGate SAML endpoint behavior.
- A privileged helper implementation intended for experimental use.
- Limited testing of unexpected termination and partially established tunnels.

Contributions and reports from other Linux distributions and FortiGate configurations are welcome.

For implementation details and the observed authentication flow, see [Protocol Notes](protocol.md).