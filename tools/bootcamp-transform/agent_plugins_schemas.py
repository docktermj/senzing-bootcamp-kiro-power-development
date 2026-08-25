#!/usr/bin/env python3
"""Vendored Agent Plugins v1.0.0 JSON Schemas — `plugin.json` and `mcp.json`.

The produced Power's manifests declare these two schemas by URL:

    https://agent-plugins.org/schemas/1.0.0/plugin.schema.json
    https://agent-plugins.org/schemas/1.0.0/mcp.schema.json

Both URLs are live and resolvable. The `Schema_Validator` nonetheless resolves
neither of them at validation time, and that is the whole reason this module
exists: **a release gate that needs the internet is not a gate.** A validator
that fetched its own schemas would report a network outage, a DNS failure, a
proxy, or an upstream edit as a property of the artifact under validation — it
would block a correct release for an unrelated reason, and, worse, an upstream
edit to a hosted schema could silently change what the gate admits between two
runs over identical bytes. The schemas are therefore carried here as data,
pinned by digest, so the gate is a function of the produced tree alone.

The alternative considered was re-expressing each schema's constraints as
hand-written checks. That was rejected: the constraints would then exist twice,
in the upstream schema and in this repository's paraphrase of it, and the two
could drift without either being wrong on its own terms — exactly the failure
the single-sourcing rule elsewhere in this pipeline exists to prevent. Vendoring
keeps one authority for "conforms to the Agent Plugins v1.0.0 schema".

Provenance
----------
The two documents below are the **verbatim upstream bytes**, embedded as raw
string literals and parsed at import. They are byte-identical to both the hosted
URLs above and to the upstream specification repository:

    repository   https://github.com/agentplugins/agent-plugins-spec
    path         schemas/1.0.0/plugin.schema.json
                 schemas/1.0.0/mcp.schema.json
    git blob     8fed0e1fe45d0464aee880d3fbab228b71ecfc1e  (plugin.schema.json)
                 a9139a4259b932c60b5351c8d9da6a5c60c97646  (mcp.schema.json)
    sha256       0a4aad95ce337878ad38802ebf0daa3fde76abe3f65400c86bcbb1ec0b3ab883
                 6539175bfcdf43085855183e86da40ea94b166547a72b47ae9a0a390516d3acb
    retrieved    2026-08-20 (hosted URL and repository compared; identical)
    license      Apache-2.0, per the upstream repository's LICENSE.md, which
                 licenses schemas and source code under Apache-2.0 and
                 specification text under CC BY 4.0. Apache-2.0 matches this
                 repository's own license.

Refreshing
----------
Replace the raw literal with the newly fetched bytes and update the digests
above and the `*_SHA256` constants below. `EMBEDDED_DIGESTS` lets a test assert
that the embedded text still hashes to the recorded value, so an accidental edit
to a vendored document is loud rather than silent. Note that upstream also
publishes a `1.1.0` schema directory; this repository targets **1.0.0**, which is
the version the produced manifests declare, so a refresh means re-fetching
1.0.0, not moving to a later one.

Nothing in this module imports `jsonschema` or touches the network or the
filesystem. It is data plus two integrity constants.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

__all__ = [
    "AGENT_PLUGINS_VERSION",
    "EMBEDDED_DIGESTS",
    "MCP_SCHEMA",
    "MCP_SCHEMA_ID",
    "MCP_SCHEMA_SHA256",
    "PLUGIN_SCHEMA",
    "PLUGIN_SCHEMA_ID",
    "PLUGIN_SCHEMA_SHA256",
    "SCHEMAS_BY_ID",
    "embedded_digest",
]

#: The Agent Plugins version these schemas define, and the only one this
#: repository targets.
AGENT_PLUGINS_VERSION = "1.0.0"

#: The canonical `$id` of each vendored schema — also the exact string the
#: produced manifests must carry in their `$schema` field, which each schema
#: enforces itself with a `const`.
PLUGIN_SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"

#: SHA-256 of the embedded upstream bytes, recorded so a refresh is verifiable
#: and an accidental edit is detectable.
PLUGIN_SCHEMA_SHA256 = (
    "0a4aad95ce337878ad38802ebf0daa3fde76abe3f65400c86bcbb1ec0b3ab883"
)
MCP_SCHEMA_SHA256 = (
    "6539175bfcdf43085855183e86da40ea94b166547a72b47ae9a0a390516d3acb"
)


# ---------------------------------------------------------------------------
# Vendored upstream bytes — do not reformat
# ---------------------------------------------------------------------------
#
# Raw literals, so the JSON escaping in `plugin.schema.json`'s `pattern` reaches
# `json.loads` exactly as upstream wrote it. Reformatting, re-indenting, or
# re-serializing these would break the digests above and, with them, the only
# evidence that what this gate validates against is what upstream published.

_PLUGIN_SCHEMA_JSON = r"""{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "title": "Agent Plugins Manifest",
  "description": "Machine-readable schema for plugin.json in Agent Plugins 1.0.0. The Agent Plugins specification defines additional semantic and operational requirements.",
  "type": "object",
  "properties": {
    "$schema": {
      "const": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
      "description": "Canonical identifier of the plugin manifest schema for the Agent Plugins version targeted by this document."
    },
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 64,
      "pattern": "^(?!.*(?:--|\\.\\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$",
      "description": "Human-readable plugin name."
    },
    "version": {
      "type": "string"
    },
    "description": {
      "type": "string"
    },
    "author": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string"
        },
        "email": {
          "type": "string"
        },
        "url": {
          "type": "string"
        }
      },
      "additionalProperties": false
    },
    "homepage": {
      "type": "string"
    },
    "repository": {
      "type": "string"
    },
    "license": {
      "type": "string"
    },
    "keywords": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "extensions": {
      "type": "object",
      "description": "Client-specific manifest data keyed by reverse-domain extension namespace. Agent Plugins assigns no semantics to namespace object contents.",
      "additionalProperties": {
        "type": "object"
      }
    }
  },
  "required": ["$schema", "name"],
  "additionalProperties": false
}
"""

_MCP_SCHEMA_JSON = r"""{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
  "title": "Agent Plugins MCP Configuration",
  "description": "Machine-readable schema for mcp.json in Agent Plugins 1.0.0. The Agent Plugins specification defines additional semantic and operational requirements.",
  "type": "object",
  "properties": {
    "$schema": {
      "const": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
      "description": "Canonical identifier of the MCP configuration schema for the Agent Plugins version targeted by this document."
    },
    "mcpServers": {
      "type": "object",
      "additionalProperties": {
        "$ref": "#/$defs/server"
      }
    }
  },
  "required": ["$schema", "mcpServers"],
  "additionalProperties": false,
  "$defs": {
    "server": {
      "title": "MCP server",
      "oneOf": [
        {
          "$ref": "#/$defs/stdioServer"
        },
        {
          "$ref": "#/$defs/streamableHttpServer"
        },
        {
          "$ref": "#/$defs/sseServer"
        }
      ]
    },
    "stdioServer": {
      "title": "stdio MCP server",
      "type": "object",
      "properties": {
        "type": {
          "const": "stdio"
        },
        "command": {
          "type": "string",
          "minLength": 1,
          "description": "Executable token. Resolution rules are defined by the Agent Plugins specification."
        },
        "args": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "env": {
          "type": "object",
          "propertyNames": {
            "not": {
              "enum": ["PLUGIN_ROOT", "PLUGIN_DATA"]
            }
          },
          "additionalProperties": {
            "type": "string"
          }
        },
        "cwd": {
          "type": "string",
          "pattern": "^(?:\\./|\\$\\{PLUGIN_ROOT\\}(?:/|$)|\\$\\{PLUGIN_DATA\\}(?:/|$))",
          "description": "Plugin-relative, PLUGIN_ROOT-rooted, or PLUGIN_DATA-rooted working directory. Filesystem containment is validated separately."
        }
      },
      "required": ["type", "command"],
      "additionalProperties": false
    },
    "streamableHttpServer": {
      "title": "Streamable HTTP MCP server",
      "type": "object",
      "properties": {
        "type": {
          "const": "streamable-http"
        },
        "url": {
          "type": "string",
          "minLength": 1,
          "description": "MCP endpoint URL. URL semantics are defined by the Agent Plugins specification."
        },
        "headers": {
          "$ref": "#/$defs/headers"
        }
      },
      "required": ["type", "url"],
      "additionalProperties": false
    },
    "sseServer": {
      "title": "Legacy HTTP+SSE MCP server",
      "type": "object",
      "properties": {
        "type": {
          "const": "sse"
        },
        "url": {
          "type": "string",
          "minLength": 1,
          "description": "MCP endpoint URL. URL semantics are defined by the Agent Plugins specification."
        },
        "headers": {
          "$ref": "#/$defs/headers"
        }
      },
      "required": ["type", "url"],
      "additionalProperties": false
    },
    "headers": {
      "title": "HTTP headers",
      "type": "object",
      "additionalProperties": {
        "type": "string"
      }
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Parsed schemas
# ---------------------------------------------------------------------------

#: The Agent Plugins v1.0.0 `plugin.json` schema (R13 AC1).
PLUGIN_SCHEMA: Mapping[str, Any] = json.loads(_PLUGIN_SCHEMA_JSON)

#: The Agent Plugins v1.0.0 `mcp.json` schema (R13 AC2).
MCP_SCHEMA: Mapping[str, Any] = json.loads(_MCP_SCHEMA_JSON)

#: `$id` → schema, the shape a `jsonschema` reference store wants. Both schemas
#: are self-contained (`mcp.schema.json`'s only `$ref`s are local `#/$defs/…`
#: fragments), so a resolver seeded with this mapping never needs to retrieve
#: anything.
SCHEMAS_BY_ID: Mapping[str, Mapping[str, Any]] = {
    PLUGIN_SCHEMA_ID: PLUGIN_SCHEMA,
    MCP_SCHEMA_ID: MCP_SCHEMA,
}

#: `$id` → SHA-256 of the embedded upstream bytes.
EMBEDDED_DIGESTS: Mapping[str, str] = {
    PLUGIN_SCHEMA_ID: PLUGIN_SCHEMA_SHA256,
    MCP_SCHEMA_ID: MCP_SCHEMA_SHA256,
}

_EMBEDDED_TEXT: Mapping[str, str] = {
    PLUGIN_SCHEMA_ID: _PLUGIN_SCHEMA_JSON,
    MCP_SCHEMA_ID: _MCP_SCHEMA_JSON,
}


def embedded_digest(schema_id: str) -> str:
    """SHA-256 of the vendored bytes for `schema_id`, computed not recorded.

    Exists so the recorded digests above can be checked against the text that
    is actually embedded, which is the difference between a pin and a comment.
    """
    try:
        text = _EMBEDDED_TEXT[schema_id]
    except KeyError:
        raise KeyError(f"no Agent Plugins schema is vendored under {schema_id!r}") from None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# The `$schema` const each schema enforces is the schema's own `$id`, and this
# module's constants are used as dictionary keys and in findings. If a refresh
# ever moved one apart from the other, every `$schema` finding would name the
# wrong URL, so the two are tied together here rather than trusted to match.
for _schema_id, _schema in SCHEMAS_BY_ID.items():
    if _schema.get("$id") != _schema_id:
        raise ValueError(
            f"vendored schema keyed as {_schema_id!r} declares "
            f"$id {_schema.get('$id')!r}"
        )
    _const = _schema.get("properties", {}).get("$schema", {}).get("const")
    if _const != _schema_id:
        raise ValueError(
            f"vendored schema {_schema_id!r} constrains $schema to {_const!r}"
        )
del _schema_id, _schema, _const
