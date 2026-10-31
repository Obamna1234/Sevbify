# Security notes

## October 2026 security review

A read-only security review of Sevbify (desktop, Android, iOS) plus the related SEVBY, SEVBY HQ and
UniFetcher projects was carried out. No critical or high-severity issues were found. This file records the
fixes made here and the items intentionally deferred.

### Reviewed, no change needed

1. **Profile `file` field.** This was considered as a possible path-injection hardening target, but testing
   showed the field is **by-design**: a profile legitimately round-trips a track's own local path across
   devices (the `test_windows_export_then_import_on_another_computer` test asserts this), and the value is
   never used to open or write a path unsafely. An import-time guard was prototyped and **reverted** because
   it broke that round-trip. No vulnerability here; left as-is.

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
