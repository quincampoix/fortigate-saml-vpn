# System Tray Integration (Optional)

This directory contains an optional system tray application for `fortigate-saml-vpn`, developed in Python using PySide6 (Qt).

It has been developed and tested on KDE Plasma, but should also work with other Linux desktop environments that support system tray icons.

## Features

- Displays the VPN connection status using a shield icon:
  - Green: VPN connected
  - Gray: VPN disconnected
- Automatically checks the strongSwan connection status every 5 seconds using VICI.
- Provides Connect and Disconnect actions from the system tray menu.
- Detects connection changes even when initiated outside the tray application.

## Connection and disconnection

The Connect and Disconnect actions currently open a **Konsole terminal** and execute the corresponding `fortigate-saml-vpn` CLI command.

This is intentional: the CLI requires sudo authentication, and using a terminal allows the user to enter their password and view command output or errors.

The terminal remains open after execution.

This implementation is tailored to Konsole. Users of other desktop environments, terminals or shells are welcome to adapt these commands in `tray.py`.

## Status monitoring

The application uses a separate Python helper (`vpn_status.py`) to query strongSwan through VICI.

Since the VICI socket normally requires root privileges, the helper must be installed in a root-controlled location with its dependencies protected from modification by unprivileged users.

A narrowly scoped sudoers rule can then allow the tray application to run this specific status-check command without repeatedly prompting for a password.

**Do not grant unrestricted access to the VICI socket or configure passwordless sudo for a helper located in a user-writable directory.**

## Project scope

This tray integration is optional and experimental. It is not required to use the main `fortigate-saml-vpn` CLI.

The core VPN client remains independent of PySide6 and the desktop environment.



## Installation

The main `fortigate-saml-vpn` CLI must already be installed and working before setting up the tray application.

### 1. Install the graphical dependencies

From the project root, install PySide6 in the existing Python virtual environment:

```bash
.venv/bin/python -m pip install -r tray/requirements.txt
```

The tray application also expects `konsole` to be installed, and the `fortigate-saml-vpn` command to be available in the shell's `PATH`.

### 2. Install the VICI status helper

The tray application checks the VPN status through strongSwan's VICI interface.

Since access to the VICI socket normally requires root privileges, install a dedicated, root-controlled copy of the status helper and its Python dependencies.

Run the following commands from the project root:

```bash
sudo mkdir -p /usr/local/libexec/fortigate-saml-vpn

sudo python3 -m venv /usr/local/libexec/fortigate-saml-vpn/venv

sudo /usr/local/libexec/fortigate-saml-vpn/venv/bin/python -m pip install 'vici>=6.0.3,<7'

sudo install -o root -g root -m 755 \
    tray/vpn_status.py \
    /usr/local/libexec/fortigate-saml-vpn/vpn_status.py
```

The installed helper and its Python environment must remain protected from modification by unprivileged users.

### 3. Configure restricted sudo access

The tray application needs to execute the status helper without prompting for a password every five seconds.

Create a dedicated sudoers file:

```bash
sudo visudo -f /etc/sudoers.d/fortigate-saml-vpn-tray
```

Add the following rule, replacing `YOUR_USERNAME` with your Linux username:

```sudoers
YOUR_USERNAME ALL=(root) NOPASSWD: /usr/local/libexec/fortigate-saml-vpn/venv/bin/python /usr/local/libexec/fortigate-saml-vpn/vpn_status.py
```

Make sure the file is owned by root and has the correct permissions:

```bash
sudo chown root:root /etc/sudoers.d/fortigate-saml-vpn-tray
sudo chmod 440 /etc/sudoers.d/fortigate-saml-vpn-tray
sudo visudo -c
```

**Security note:** This rule must authorize only the exact status-check command shown above. Do not grant unrestricted passwordless access to Python, strongSwan or the VICI socket.

### 4. Test the status helper

Run:

```bash
sudo -n /usr/local/libexec/fortigate-saml-vpn/venv/bin/python \
    /usr/local/libexec/fortigate-saml-vpn/vpn_status.py

echo $?
```

Expected exit codes:

| Exit code | Meaning |
|---|---|
| `0` | VPN connected |
| `1` | VPN disconnected |
| `2` | Unable to determine VPN status |

The helper should return `0` when the FortiGate tunnel is established and `1` when disconnected.

If the helper fails with a permission error, verify the sudoers configuration and the installed file permissions.

### 5. Start the tray application

From the project root:

```bash
.venv/bin/python tray/tray.py
```

A shield icon should appear in the system tray.

- **Green shield:** VPN connected.
- **Gray shield:** VPN disconnected.
- **Connect:** Opens Konsole and starts the CLI connection process.
- **Disconnect:** Opens Konsole and runs the CLI disconnection command.
- **Quit:** Closes the tray application without disconnecting the VPN.

The VPN status is refreshed automatically every five seconds.

### Customization

The current implementation uses Konsole to execute the CLI:

```python
subprocess.Popen([
    "konsole",
    "--hold",
    "-e",
    "fortigate-saml-vpn connect",
])
```

Users of other terminal emulators or shells can adapt the `connect()` and `disconnect()` methods in `tray.py`.

The status helper currently checks a strongSwan connection named `fortigate`. If your connection uses a different name, update `CONNECTION_NAME` in `tray/vpn_status.py` **before installing the helper**.

After modifying the helper, reinstall its root-controlled copy using the installation command above.