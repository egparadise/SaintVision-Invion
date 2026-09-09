"""Generate Pydantic, TS and Go types from the single JSON Schema bundle."""

from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "contracts/v1alpha1/core.schema.json"
schema = json.loads(source.read_text("utf-8"))
generated = ROOT / "services/control-plane/src/inv/generated"
generated.mkdir(parents=True, exist_ok=True)
generated.joinpath("core.schema.json").write_bytes(source.read_bytes())
subprocess.run(
    [
        sys.executable,
        "-m",
        "datamodel_code_generator",
        "--input",
        str(source),
        "--input-file-type",
        "jsonschema",
        "--output",
        str(generated / "models.py"),
        "--output-model-type",
        "pydantic_v2.BaseModel",
        "--target-python-version",
        "3.12",
        "--disable-timestamp",
        "--use-standard-collections",
        "--extra-fields",
        "forbid",
    ],
    check=True,
)


def typename(spec, lang):
    if "anyOf" in spec:
        choices = spec["anyOf"]
        concrete = [item for item in choices if item.get("type") != "null"]
        if len(choices) != 2 or len(concrete) != 1:
            raise ValueError("Only a single nullable type is supported")
        value = typename(concrete[0], lang)
        return "(" + value + " | null)" if lang == "ts" else "*" + value
    if "$ref" in spec:
        return spec["$ref"].split("/")[-1]
    if lang == "ts" and "const" in spec:
        return json.dumps(spec["const"])
    if lang == "ts" and "enum" in spec:
        return " | ".join(json.dumps(v) for v in spec["enum"])
    typ = spec["type"]
    if typ == "array":
        return (
            ("Array<" + typename(spec["items"], lang) + ">")
            if lang == "ts"
            else "[]" + typename(spec["items"], lang)
        )
    return {
        "ts": {
            "string": "string",
            "integer": "number",
            "number": "number",
            "boolean": "boolean",
        },
        "go": {
            "string": "string",
            "integer": "int64",
            "number": "float64",
            "boolean": "bool",
        },
    }[lang][typ]


ts = ["// Generated; runtime validation must use the canonical JSON Schema."]
go = ["// Code generated from core.schema.json; DO NOT EDIT.", "package contracts", ""]
for name, spec in schema["$defs"].items():
    if spec.get("type") == "object":
        ts.append("export interface " + name + " {")
        go.append("type " + name + " struct {")
        for field, field_schema in spec["properties"].items():
            required = field in spec["required"]
            ts.append(
                "  "
                + field
                + ("" if required else "?")
                + ": "
                + typename(field_schema, "ts")
                + ";"
            )
            go_type = typename(field_schema, "go")
            go.append(
                "    "
                + field[0].upper()
                + field[1:]
                + " "
                + ("" if required else "*")
                + go_type
                + " "
                + chr(96)
                + "json:"
                + json.dumps(field + ("" if required else ",omitempty"))
                + chr(96)
            )
        ts.append("}")
        go.append("}")
    else:
        ts.append("export type " + name + " = " + typename(spec, "ts") + ";")
        go.append("type " + name + " " + typename(spec, "go"))
    ts.append("")
    go.append("")
for rel, lines in [
    ("packages/contracts-ts/src/index.ts", ts),
    ("packages/contracts-go/contracts.go", go),
]:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("\n".join(lines).rstrip() + "\n").encode())
print("Generated Python, TypeScript, Go and packaged validation schema.")

node_schema = ROOT / "services/node-agent/internal/wire/core.schema.json"
node_schema.parent.mkdir(parents=True, exist_ok=True)
node_schema.write_bytes(source.read_bytes())
