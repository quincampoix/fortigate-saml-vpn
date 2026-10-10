# FortiGate IKEv2 VPN with SAML Authentication — Protocol Notes

## 1. Overview

This document describes the authentication and connection flow implemented by `fortigate-saml-vpn`.

The project demonstrates how a Linux client can authenticate against a FortiGate VPN gateway using browser-based SAML authentication and then establish an IPsec/IKEv2 tunnel using strongSwan.

The implementation is based on observed FortiGate behavior and practical experimentation. It is **not an official Fortinet protocol specification**.

The behavior described here has been tested against one FortiGate environment. Other FortiOS versions, authentication configurations, or VPN policies may behave differently.

## 2. Architecture

The connection involves four main components:

- **Python CLI:** Coordinates authentication and VPN connection management.
- **Web browser:** Performs the SAML authentication flow, typically through an identity provider such as Microsoft Entra ID.
- **FortiGate gateway:** Provides the SAML authentication endpoint and terminates the IKEv2 VPN connection.
- **strongSwan:** Establishes and manages the IPsec tunnel.

The Python application does not implement IKEv2 or IPsec itself. It delegates these operations to strongSwan.

### Connection sequence

```text
Python CLI               FortiGate             Browser / IdP          strongSwan
    |                        |                       |                    |
    |-- SAML initialization->|                       |                    |
    |<-- Redirect URL -------|                       |                    |
    |                        |                       |                    |
    |-- Open browser ------------------------------->|                    |
    |                        |<--SAML authentication>|                    |
    |                        |                       |                    |
    |<-- Local callback with tokenid ----------------|                    |
    |                        |                       |                    |
    |-- Load EAP identity and secret ------------------------------------>|
    |                        |                       |                    |
    |-- Initiate IKEv2 -------------------------------------------------->|
    |                        |<===================== IPsec ==============>|
    |                        |                       |                    |
    |<-- Connection status -----------------------------------------------|
```

This diagram is simplified. In particular, the browser communicates with both the FortiGate and the identity provider during authentication.

## 3. SAML Authentication Initialization

The client starts by generating a random session identifier, referred to here as the **SAML UID**.

Our implementation generates a 32-character uppercase hexadecimal string.

Example:

```text
A6D4C2E8F0194B73A51D0E29C8F643B2
```

This value is generated independently for each authentication attempt.

The client then sends an HTTPS POST request to the FortiGate SAML endpoint:

```http
POST https://vpn.example.com:1001/saml_login?
Content-Type: application/json
```

The request body follows this structure:

```json
{
  "type": "rawData",
  "bytes": "UID=A6D4C2E8F0194B73A51D0E29C8F643B2&REDIRECT_PORT=8020"
}
```

The two important parameters are:

| Parameter | Purpose |
|---|---|
| `UID` | Client-generated identifier associated with the authentication attempt |
| `REDIRECT_PORT` | Local TCP port used for the browser authentication callback |

In our implementation, the callback listener runs on `127.0.0.1:8020`.

The FortiGate responds with information allowing the client to construct or obtain a browser authentication URL, using a path of the form:

```text
https://vpn.example.com:1001/saml?...
```

The URL contains gateway-generated parameters that must be preserved.

The client opens this URL in the user's default browser.

**Important:** The `/saml_login` request format and the exact browser redirect behavior are implementation observations, not a guarantee of compatibility with every FortiGate configuration.

## 4. Browser-Based SAML Authentication

Once the browser opens the FortiGate authentication URL, the gateway coordinates the SAML exchange with the configured identity provider.

In our tested environment, the identity provider is Microsoft Entra ID.

The user may be asked to authenticate, complete multifactor authentication, or approve an access request, depending on the organization's policies.

If the browser already has a valid identity provider session, authentication may complete automatically without additional interaction.

The Python application does not collect the user's identity provider password or implement the SAML assertion exchange itself.

This separation is intentional: the browser handles the interactive authentication process.

## 5. Local Authentication Callback

After successful authentication, the browser is redirected to the client's local HTTP listener.

The observed callback has the following structure:

```text
http://127.0.0.1:8020/?tokenid=<TOKEN_ID>&username=<USERNAME>
```

The callback contains two important values:

| Parameter | Purpose |
|---|---|
| `tokenid` | Temporary authentication token returned after successful SAML authentication |
| `username` | Username associated with the authenticated session |

In our tested environment, `tokenid` is represented as a 32-character hexadecimal value.

The application extracts the token and username from the callback.

The `tokenid` is sensitive authentication material and must not be written to logs, committed to source control, or included in diagnostic output.

### Callback page behavior

After receiving the callback, the local HTTP server displays a short success page.

The page uses:

```javascript
history.replaceState(null, "", "/");
window.close();
```

The first statement replaces the current history entry's URL to remove authentication parameters from the displayed address.

The second attempts to close the browser tab automatically.

Browser security policies may prevent automatic tab closure. If that happens, the user can close the success page manually.

Replacing the URL does not guarantee removal of the token from all browser, proxy, or operating system records.

## 6. Bridging SAML Authentication to IKEv2

This is the key technical discovery behind the project.

Successful browser authentication alone does not establish the VPN tunnel.

The SAML authentication result must be associated with the subsequent IKEv2 authentication performed by strongSwan.

In the tested environment, this is achieved by using:

- The **client-generated SAML UID** as the IKEv2 EAP identity.
- The **FortiGate-provided `tokenid`** as the EAP secret.

Conceptually:

```text
SAML initialization:
    UID = <RANDOM_UID>

SAML callback:
    tokenid = <AUTHENTICATION_TOKEN>

strongSwan EAP identity:
    <RANDOM_UID>

strongSwan EAP secret:
    <AUTHENTICATION_TOKEN>
```

The UID must remain identical between the SAML initialization request and the strongSwan EAP configuration.

Using a different EAP identity prevents the gateway from associating the IKEv2 authentication attempt with the corresponding browser authentication session in our tested setup.

The token returned by the callback is temporary and should be treated as a short-lived credential.

The precise validity period and server-side lifecycle of this token have not been established by this project.

## 7. strongSwan Authentication Configuration

The project uses a permanent strongSwan configuration for the gateway connection and a temporary configuration containing the credentials for the current authentication session.

The permanent configuration defines the IKEv2 connection parameters, including the gateway address, identities, authentication methods, traffic selectors, and cryptographic settings.

The exact values depend on the FortiGate configuration.

### Temporary session configuration

After successful SAML authentication, the application creates a temporary `swanctl` configuration with the following structure:

```ini
include /etc/swanctl/conf.d/fortinet.conf

connections {
    fortigate {
        local {
            eap_id = "<SAML_UID>"
        }
    }
}

secrets {
    eap-fortigate {
        id = "<SAML_UID>"
        secret = "<TOKEN_ID>"
    }
}
```

This configuration overrides the EAP identity for the current connection and supplies the temporary authentication token.

The file is created with restrictive permissions and removed after its contents have been loaded into strongSwan.

The application loads the connection and credentials using:

```bash
sudo swanctl --load-conns --file <TEMPORARY_CONFIG>
sudo swanctl --load-creds --file <TEMPORARY_CONFIG>
```

The temporary file's deletion does **not** remove credentials already loaded into the strongSwan daemon.

Credential cleanup is therefore handled separately.

### Authentication layers

It is important to distinguish the different credentials involved:

| Credential | Role |
|---|---|
| FortiGate IKE PSK | Permanent credential used in the configured IKEv2 authentication |
| SAML UID | Identifier linking the browser authentication attempt to the EAP exchange |
| SAML `tokenid` | Temporary secret used for EAP authentication |

These values are not interchangeable.

The project does not attempt to replace the permanent IKEv2 configuration with SAML authentication alone.

## 8. Establishing the IPsec Tunnel

Once the temporary session credentials are loaded, the application instructs strongSwan to initiate the configured IKEv2 connection.

strongSwan performs the IKE negotiation, authentication, and creation of the required IPsec security associations.

The FortiGate validates the authentication information according to its VPN configuration.

When the exchange succeeds, strongSwan establishes the tunnel.

The CLI reports the connection as successful after the initiation operation completes successfully.

The application can subsequently inspect the IKE security associations to determine whether the configured VPN connection is established.

The project does not implement IPsec packet processing or encryption in Python.

## 9. DNS Configuration

In the tested environment, the FortiGate supplies DNS server information during IKEv2 configuration exchange.

strongSwan's `resolve` plugin can apply this information to the local system.

Our tested Linux configuration uses:

```ini
resolve {
    load = yes
    resolvconf {
        iface = enp2s0
    }
}
```

The network interface name is machine-specific.

With the appropriate resolver integration, the corporate DNS configuration is applied when the tunnel is established and removed when the tunnel terminates.

The Python application therefore does not need to modify `/etc/resolv.conf` or implement custom DNS restoration logic.

This behavior depends on the operating system, resolver implementation, and strongSwan plugin configuration.

## 10. Disconnecting and Cleaning Up Credentials

Disconnecting the VPN requires two distinct operations.

### Step 1 — Terminate the IKEv2 connection

The application instructs strongSwan to terminate the configured IKE security association:

```bash
sudo swanctl --terminate --ike fortigate
```

This disconnects the VPN tunnel.

### Step 2 — Remove the temporary EAP secret

The temporary EAP secret may remain loaded in the strongSwan daemon after the tunnel is terminated.

To remove it without affecting unrelated credentials, the application uses strongSwan's VICI interface.

The relevant operation is:

```python
session = vici.Session()
session.unload_shared({"id": "eap-fortigate"})
```

This removes the credential identified by `eap-fortigate`.

It does not unload the permanent `ike-fortigate` credential.

The distinction matters because globally clearing strongSwan credentials could disrupt other VPN connections or services managed by the same daemon.

### Cleanup after an error

The application also attempts to remove the temporary EAP credential if an error occurs after session loading has begun.

This behavior has been tested with a deliberately simulated connection failure after loading the credentials but before initiating IKEv2.

The test confirmed that the temporary EAP credential was removed while the permanent IKE credential remained loaded.

Other failure scenarios, including partial tunnel establishment and unexpected process termination, have not been exhaustively tested.

## 11. Security Considerations

This project handles sensitive authentication material and invokes privileged system operations.

The following precautions are part of the current design:

- HTTPS certificate verification is enabled for communication with the FortiGate SAML endpoint.
- The SAML UID is generated using a cryptographically secure random generator.
- The local callback listener binds to `127.0.0.1` rather than a public network interface.
- Temporary credential files use restrictive filesystem permissions.
- Temporary credentials are not intentionally printed in CLI output.
- The application attempts to unload the EAP secret after disconnection or connection failure.
- Credential cleanup targets a specific strongSwan secret instead of clearing all credentials.

### Known security limitations

The current implementation is a small experimental project, not a security-audited VPN client.

In particular:

- Some privileged operations execute Python code from a user-managed virtual environment through `sudo`.
- The local callback mechanism has not undergone a comprehensive security review.
- Unexpected termination, power loss, or forced process termination may bypass application-level credential cleanup.
- Token exposure through external logging, browser behavior, or system diagnostics has not been exhaustively evaluated.
- Compatibility and security properties may differ across FortiOS and strongSwan versions.

A future version could use a separately installed, root-owned helper for privileged VICI operations.

Users should review the source code and their organization's security requirements before using the project.

## 12. Compatibility and Scope

The implementation has been validated with:

- A FortiGate gateway configured for IPsec/IKEv2 and browser-based SAML authentication.
- Microsoft Entra ID as the SAML identity provider.
- strongSwan on Linux.
- A Python-based CLI coordinating the authentication and tunnel lifecycle.

At the time of writing, the project has been validated against a single FortiGate environment.

It should not be assumed that all FortiGate firmware versions, authentication policies, SAML providers, or Linux distributions behave identically.

The protocol details documented here are intended to help other developers reproduce, investigate, and improve the approach.

## 13. Further Reading

- [strongSwan documentation](https://docs.strongswan.org/)
- [strongSwan `swanctl` configuration](https://docs.strongswan.org/docs/latest/swanctl/swanctlConf.html)
- [strongSwan VICI interface](https://docs.strongswan.org/docs/latest/plugins/vici.html)
- [Fortinet documentation](https://docs.fortinet.com/)
- [Microsoft Entra documentation](https://learn.microsoft.com/en-us/entra/)

For installation instructions and distribution-specific requirements, see `installation.md`.