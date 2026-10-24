"""Claude boundary: client, prompts and tool schemas.

The only package that talks to the Anthropic API. Everything here fails open:
a timeout, a refusal or a malformed tool call returns None so the caller can
fall back to a deterministic default.
"""
