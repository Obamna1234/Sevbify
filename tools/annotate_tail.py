"""Turn the last lines of a log (stdin) into one GitHub error annotation.
Used by the build so test crashes are readable without downloading logs."""
import sys

title = sys.argv[1] if len(sys.argv) > 1 else "Failure"
lines = [line.rstrip() for line in sys.stdin.read().splitlines() if line.strip()][-45:]
body = "%0A".join(line.replace("%", "%25").replace("\r", "") for line in lines)
print(f"::error title={title}::{body[:12000]}")
