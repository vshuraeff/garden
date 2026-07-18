# Platform support

GARDEN v1 does not support Windows. CI validates Ubuntu and macOS with Python
3.11 and 3.14. GARDEN may import and run under Windows Python, but its path
confinement guarantees are exercised and validated only with POSIX-style paths.

CI has validated the packaged plugin against Claude Code CLI 2.1.212 and Codex CLI
(`@openai/codex`) 0.144.1 through `.github/workflows/integration.yml`. This is not a
minimum-version requirement.

Windows path semantics are outside the accepted configuration model. The
`config_schema._normalize_relative` security boundary rejects drive-letter and
UNC paths, converts other backslashes to `/`, and then validates the result as a
confined POSIX-relative path. This is an intentional platform policy, not an
untested cross-platform compatibility claim.
