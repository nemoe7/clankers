"""Arena extension backend: read-only bridges from an Arena agent to owner-held tools.

The agent reaches this server with the `fetch_page` tool, which sends one GET
request, carries no credentials, and returns text only. Every module here keeps
that shape: results are text or JSON, inputs travel in the query string, and the
provider credentials stay on the owner's machine.
"""

VERSION = "2.0.0"
