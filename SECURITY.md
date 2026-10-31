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

1. **Server credentials at rest (Medium) — FIX WRITTEN, pending live test.** `servers.json` used to store
   Jellyfin tokens / Nextcloud app-passwords as plaintext (file mode `0600`). `core/server_store.py` now
   keeps the secret in the OS secure store (Windows Credential Manager / macOS Keychain / Linux Secret
   Service) via `keyring`, and writes only non-secret details to the file. It is **fail-safe**: with no
   secure store (or no `keyring`) it falls back to exactly the previous behaviour, and it only drops a secret
   from the file after confirming it reads back from the store, so a sign-in can't be lost. **Still to do
   before shipping:** test the add/sign-in/play flow against a real Jellyfin & Nextcloud server, and
   regenerate `requirements-lock.txt` to include `keyring` (the packaged build installs from the lock with
   `--require-hashes`, so until then packaged builds safely fall back to the file).
2. **Credentials embedded in the VLC stream URL (Low).** For local playback VLC receives the sign-in in the
   URL. Recommended: a local authenticated proxy. Architectural; deferred.
3. **App-wide Android cleartext (Low/Medium).** `network_security_config.xml` permits cleartext app-wide for
   legacy http podcast episodes. Recommended: scope it to a `domain-config` allow-list — needs the list of
   http-only feed domains.

## Reporting a problem

Open an issue on GitHub (without personal data), or contact the repository owner.
