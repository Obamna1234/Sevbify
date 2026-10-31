# Security notes

## October 2026 security review

A read-only security review of Sevbify (desktop, Android, iOS) plus the related SEVBY, SEVBY HQ and
UniFetcher projects was carried out. No critical or high-severity issues were found. This file records the
fixes made here and the items intentionally deferred.

### Fixed in this pass

1. **Profile import path hardening (CWE-20/CWE-22).** `core/profile.clean_track()` now drops the `file`
   field of an imported `.sevbify` profile if it looks like a device path (absolute, `..` traversal,
   Windows drive/UNC, or a `file:`/`content:` scheme). A profile's `file` is only ever a song's own
   description; it is never used to open a path, so this is a preventative guard with no behaviour change.

### Already strong (verified, no change needed)

- In-app update (desktop + Android): HTTPS GitHub-only, SHA-256 verified before install, size-bounded, with
  zip/tar path-traversal and symlink/hardlink/device checks before extraction.
- Server (Jellyfin/Nextcloud) HTTP: auth headers stripped on cross-origin redirects; HTTPS enforced except
  on private networks; XXE blocked; stream URLs confined to the same host.
- Profile parsing: gzip+JSON (no pickle), size-bounded, URL-scheme allow-listed.
- TLS verification is never disabled anywhere in the codebase.

### Deferred (need testing against real infrastructure, or a decision)

These were identified but **not** changed in this pass, to avoid shipping untested changes to the
Jellyfin/Nextcloud sign-in path or to podcast playback:

1. **Server credentials at rest (Medium).** `servers.json` stores Jellyfin tokens / Nextcloud app-passwords
   as plaintext (file mode `0600`). Recommended: move them to the OS keychain (DPAPI / macOS Keychain /
   libsecret). Deferred because it needs testing against a live server before release.
2. **Credentials embedded in the VLC stream URL (Low).** For local playback VLC receives the sign-in in the
   URL. Recommended: a local authenticated proxy. Architectural; deferred.
3. **App-wide Android cleartext (Low/Medium).** `network_security_config.xml` permits cleartext app-wide for
   legacy http podcast episodes. Recommended: scope it to a `domain-config` allow-list — needs the list of
   http-only feed domains.

## Reporting a problem

Open an issue on GitHub (without personal data), or contact the repository owner.
