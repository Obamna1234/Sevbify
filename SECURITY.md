# Security

Sevbify is reviewed by an independent security review before each release. This page explains how the parts that
touch your data or your network are protected, and what is still planned.

## Reporting a problem

Please open an issue on GitHub (leave out personal details). For something that shouldn't be public until it's
fixed, use GitHub's **Report a vulnerability** button on the Security tab.

## Updates

- New versions come only from this repository's releases, over HTTPS.
- Every download is checked against GitHub's SHA-256 before it's installed. Archives are checked for unsafe paths
  and links before they're unpacked. The Android app is signed with the same key every time (the key is not in
  this repository).

## Pairing a phone with a computer

- **Local network only.** Your phone connects straight to your computer. Only private, link-local and loopback
  addresses can connect. Nothing goes through the internet or any server.
- **Encrypted and authenticated.** P-256 key agreement with a fresh key each time (forward secrecy), HKDF-SHA256 and
  AES-256-GCM. The keys depend on a one-time code that is only in the QR code (or, later, on the phone's own key),
  and on the exact opening messages, so nobody else on the network can read, change, replay or downgrade the
  connection.
- **The QR code** works once, for 5 minutes, and only while the pairing window is open.
- **Paired phones** each have their own key. Remove a phone in Settings → Your phone and its key stops working
  straight away.
- **Transfers** need your OK each time (Decline is the default). Only music, cover pictures, lyrics and playlist
  files are saved, with safe file names, inside a "From <device>" folder. Nothing is overwritten, never more than was
  offered, and only when there is room on the disk.
- **Denial of service:** a connection has 10 seconds in all to prove it has the key. There are at most two unproven
  connections per address, and they never take paired phones' places.
- **Planned:** keeping the paired-phone keys in the system keychain (Windows DPAPI, macOS Keychain, Linux Secret
  Service). Today they're in a file in Sevbify's data folder that only your user account can read.

## Music servers (Jellyfin, Nextcloud)

- Sign-ins are only sent to the server's own address. Redirects to another address drop them. Plain http is only
  allowed on private networks.
- Sign-ins are kept on your device (never in playlists, profiles or logs). Planned: system keychain storage, as
  above.

## Other

- TLS certificate checks are never turned off.
- Profile files are plain JSON (gzip), size-limited, with only safe link types allowed.
- Remembered song pages are re-checked when loaded: only https pages on known music sites are used.
- Streamed audio is only cached in Sevbify's own cache folder (off by default), never your own files or sign-ins.
- The activity log shortens links to their site, keeps nothing about songs during a Private Session, and is never
  sent anywhere. You can save it and choose to share it.
