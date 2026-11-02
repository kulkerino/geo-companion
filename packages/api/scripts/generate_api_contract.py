"""Generate deterministic OpenAPI and TypeScript API artifacts from FastAPI contracts."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT / "packages" / "api" / "src"))

from geo_companion.main import app  # noqa: E402

OPENAPI_PATH = REPOSITORY_ROOT / "packages" / "api" / "openapi" / "openapi.json"
TYPESCRIPT_PATH = REPOSITORY_ROOT / "apps" / "web" / "src" / "api" / "generated.ts"


def ts_type(schema: Mapping[str, Any]) -> str:
    """Render the small JSON Schema subset emitted by this service into TypeScript."""
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", maxsplit=1)[-1]
    if "enum" in schema:
        return " | ".join(json.dumps(value) for value in schema["enum"])
    for union_key in ("anyOf", "oneOf", "allOf"):
        if union_key in schema:
            return " | ".join(ts_type(option) for option in schema[union_key])
    schema_type = schema.get("type")
    if schema_type == "array":
        return f"Array<{ts_type(schema['items'])}>"
    if schema_type in {"integer", "number"}:
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "null":
        return "null"
    if schema_type == "string":
        return "string"
    if schema_type == "object":
        additional = schema.get("additionalProperties")
        if isinstance(additional, Mapping):
            return f"Record<string, {ts_type(additional)}>"
        return "Record<string, unknown>"
    return "unknown"


def render_interfaces(openapi: Mapping[str, Any]) -> str:
    schemas = openapi["components"]["schemas"]
    blocks: list[str] = []
    for name in sorted(schemas):
        schema = schemas[name]
        if "enum" in schema:
            blocks.append(f"export type {name} = {ts_type(schema)};")
            continue
        properties = schema.get("properties")
        if not properties:
            blocks.append(f"export type {name} = {ts_type(schema)};")
            continue
        required = set(schema.get("required", []))
        fields = "\n".join(
            "  "
            f"{property_name}{'' if property_name in required else '?'}: "
            f"{ts_type(property_schema)};"
            for property_name, property_schema in properties.items()
        )
        blocks.append(f"export interface {name} {{\n{fields}\n}}")
    return "\n\n".join(blocks)


def response_type(operation: Mapping[str, Any]) -> str:
    responses = operation.get("responses", {})
    success = next((value for code, value in responses.items() if code.startswith("2")), None)
    if not isinstance(success, Mapping):
        return "void"
    schema = success.get("content", {}).get("application/json", {}).get("schema")
    return ts_type(schema) if isinstance(schema, Mapping) else "void"


def request_body(operation: Mapping[str, Any]) -> tuple[str, bool] | None:
    request_body = operation.get("requestBody", {})
    content = request_body.get("content", {})
    required = bool(request_body.get("required", False))
    schema = content.get("application/json", {}).get("schema")
    if isinstance(schema, Mapping):
        return ts_type(schema), required
    # A raw binary body (a photo upload) is sent as a Blob with the Blob's own content type.
    if content and all(
        media.get("schema", {}).get("format") == "binary" for media in content.values()
    ):
        return "Blob", required
    return None


def path_parameters(operation: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        parameter
        for parameter in operation.get("parameters", [])
        if parameter.get("in") == "path"
    ]


def render_client(openapi: Mapping[str, Any]) -> str:
    methods: list[str] = []
    for path, path_item in sorted(openapi["paths"].items()):
        for method, operation in sorted(path_item.items()):
            if method not in {"delete", "get", "patch", "post", "put"}:
                continue
            operation_id = operation["operationId"]
            body = request_body(operation)
            return_type = response_type(operation)
            parameters = path_parameters(operation)
            arguments = [
                f"{parameter['name']}: {ts_type(parameter['schema'])}" for parameter in parameters
            ]
            path_values = ", ".join(
                f'"{parameter["name"]}": String({parameter["name"]})' for parameter in parameters
            )
            path_argument = f"{{ {path_values} }}" if path_values else "{}"
            body_argument = "undefined"
            if body is not None:
                body_type, body_required = body
                arguments.append(f"body{'' if body_required else '?'}: {body_type}")
                body_argument = "body"
            methods.append(
                "  async "
                f"{operation_id}({', '.join(arguments)}): "
                f"Promise<{return_type}> {{\n"
                f"    return this.request<{return_type}>(\n"
                f"      \"{method.upper()}\", \"{path}\", {path_argument}, {body_argument},\n"
                "    );\n"
                "  }"
            )
    return "\n\n".join(methods)


def render_typescript(openapi: Mapping[str, Any]) -> str:
    header = (
        "/* This file is generated by "
        "packages/api/scripts/generate_api_contract.py. Do not edit. */"
    )
    return f'''{header}
/* OpenAPI version: {openapi["info"]["version"]} */

{render_interfaces(openapi)}

export class GeoCompanionApiClient {{
  constructor(private readonly baseUrl = "") {{}}

  private async request<T>(
    method: string,
    template: string,
    pathParams: Record<string, string>,
    body?: unknown,
  ): Promise<T> {{
    const path = template.replace(/{{([^}}]+)}}/g, (_, key: string) =>
      encodeURIComponent(pathParams[key] ?? ""),
    );
    const binary = body instanceof Blob;
    const contentType = binary ? body.type || "application/octet-stream" : "application/json";
    const response = await fetch(`${{this.baseUrl}}${{path}}`, {{
      method,
      headers: body === undefined ? undefined : {{ "content-type": contentType }},
      body: body === undefined ? undefined : binary ? body : JSON.stringify(body),
    }});
    if (!response.ok) {{
      const errorBody = await response.json().catch(() => null) as {{ detail?: string }} | null;
      throw new Error(
        errorBody?.detail ?? `Geo Companion API request failed: ${{response.status}}`,
      );
    }}
    return response.status === 204 ? (undefined as T) : (await response.json()) as T;
  }}

{render_client(openapi)}
}}
'''


def generated_files() -> dict[Path, str]:
    openapi = app.openapi()
    return {
        OPENAPI_PATH: json.dumps(openapi, indent=2, sort_keys=True) + "\n",
        TYPESCRIPT_PATH: render_typescript(openapi),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="fail when committed generated files drift"
    )
    args = parser.parse_args()
    files = generated_files()
    if args.check:
        stale = []
        for path, contents in files.items():
            if not path.exists() or path.read_text(encoding="utf-8") != contents:
                stale.append(path)
        if stale:
            print("Generated API artifacts are stale:")
            print("\n".join(str(path.relative_to(REPOSITORY_ROOT)) for path in stale))
            return 1
        return 0
    for path, contents in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
