# Sevbify — release notes draft (security hardening)

> Draft for the next beta. No functional changes; hardening only. Review before publishing.

## Recommended version — security hardening

Adds a preventative hardening fix from the October 2026 security review. **Nothing about how the app works
changes.**

**What changed**
- Importing a profile (`.sevbify`): a hand-crafted profile can no longer smuggle a device file path through
  the song `file` field (which the app never uses to open anything — this just closes the door).

**Severity:** low, preventative. No critical or high-severity issues were found in the review.

## Note for a later update

Three items from the review are documented in `SECURITY.md` but intentionally held for a future update
because they touch the Jellyfin/Nextcloud sign-in or podcast playback and need testing against a real server
first: moving server credentials into the OS keychain, the VLC stream-URL credential handling, and scoping
Android cleartext to specific podcast domains.

## Keeping a stable fallback

The previous beta remains available as a known-good fallback.
