"""Lossless source bindings for the JSON context shapes found in FinanceReasoning.

This is an input representation change, not financial or answer validation.
Numeric literals retain their spelling; JSON strings never become numbers.
"""
from dataclasses import dataclass
import hashlib
import html
import json
import re


NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")
LEXICAL_NUMBER = re.compile(r"(?<!\w)[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?(?!\w)")
DECODER = json.JSONDecoder()


class JsonContextError(ValueError):
    """An identified JSON context must not silently lose source information."""


@dataclass
class Node:
    kind: str
    start: int
    end: int
    pointer: str
    value: object = None
    children: object = None


def pointer_part(text):
    return text.replace("~", "~0").replace("/", "~1")


def parse(text):
    """Parse JSON with literal spans and duplicate-key detection."""
    position = 0

    def whitespace():
        nonlocal position
        while position < len(text) and text[position] in " \t\r\n":
            position += 1

    def value(pointer=""):
        nonlocal position
        whitespace()
        start = position
        if position >= len(text):
            raise JsonContextError("JSON_UNEXPECTED_END")
        char = text[position]
        if char == '"':
            decoded, end = DECODER.raw_decode(text, position)
            position = end
            return Node("string", start, end, pointer, decoded)
        if char in "{[":
            object_mode = char == "{"
            position += 1
            children = [] if object_mode else []
            keys = set()
            closing = "}" if object_mode else "]"
            whitespace()
            if position < len(text) and text[position] != closing:
                while True:
                    if object_mode:
                        key = value(pointer)
                        if key.kind != "string":
                            raise JsonContextError("JSON_OBJECT_KEY_NOT_STRING")
                        if key.value in keys:
                            raise JsonContextError("JSON_DUPLICATE_KEY:" + key.value)
                        keys.add(key.value)
                        key.pointer = pointer + "/" + pointer_part(key.value)
                        whitespace()
                        if position >= len(text) or text[position] != ":":
                            raise JsonContextError("JSON_MISSING_COLON")
                        position += 1
                        children.append((key, value(key.pointer)))
                    else:
                        children.append(value(pointer + "/" + str(len(children))))
                    whitespace()
                    if position < len(text) and text[position] == ",":
                        position += 1
                        whitespace()
                        continue
                    break
            if position >= len(text) or text[position] != closing:
                raise JsonContextError("JSON_MISSING_CLOSING_DELIMITER")
            position += 1
            return Node("object" if object_mode else "array", start, position, pointer,
                        children=children)
        for literal, kind, decoded in (("true", "boolean", True), ("false", "boolean", False),
                                       ("null", "null", None)):
            if text.startswith(literal, position):
                position += len(literal)
                return Node(kind, start, position, pointer, decoded)
        match = NUMBER.match(text, position)
        if match:
            position = match.end()
            literal = match.group()
            return Node("number" if any(c in literal for c in ".eE") else "integer",
                        start, position, pointer, literal)
        raise JsonContextError("JSON_INVALID_TOKEN:" + str(position))

    root = value()
    whitespace()
    if position != len(text):
        raise JsonContextError("JSON_TRAILING_CONTENT")
    return root


def plain(node):
    if node.kind in ("string", "integer", "number"):
        return node.value
    if node.kind == "null":
        return "null"
    if node.kind == "boolean":
        return "true" if node.value else "false"
    raise JsonContextError("JSON_CONTAINER_IN_VALUE_CELL")


def escape_cell(text):
    """Escape Markdown separators without changing the source binding."""
    return (html.escape(text, quote=False).replace("\\", "\\\\").replace("|", "\\|")
            .replace("\r", "<br data-cr>").replace("\n", "<br>"))


def unescape_cell(text):
    text = text.replace("<br data-cr>", "\r").replace("<br>", "\n")
    text = re.sub(r"\\([\\|])", r"\1", text)
    return html.unescape(text)


def binding(source, node, decoded_span=None, *, key=False, escaped=True):
    original = plain(node)
    return {"pointer": node.pointer, "source_span": [node.start, node.end],
            "raw_text": source[node.start:node.end],
            "value_type": "key" if key else node.kind,
            "decoded_span": decoded_span or [0, len(original)],
            "markdown_escaped": escaped}


def assemble_json(source):
    """Return common content fields, or None when C is not a JSON container."""
    stripped = source.lstrip()
    if not stripped.startswith(("{", "[")):
        return None
    try:
        root = parse(source)
    except (ValueError, json.JSONDecodeError) as error:
        # Markdown links and bracketed prose are ordinary contexts, not JSON.
        try:
            json.loads(source)
        except ValueError:
            return None
        raise JsonContextError(str(error)) from error
    if root.kind not in ("object", "array") or not root.children:
        return None
    if root.kind == "array":
        if (len(root.children) != 1 or root.children[0].kind != "string"
                or not root.children[0].value.lstrip().startswith("|")):
            raise JsonContextError("JSON_CONTEXT_UNSUPPORTED_ARRAY_SHAPE")
        return assemble_table_string(source, root.children[0])
    if any(row.kind != "object" or not row.children
           or any(cell.kind in ("object", "array") for _, cell in row.children)
           for _, row in root.children):
        raise JsonContextError("JSON_CONTEXT_UNSUPPORTED_OBJECT_SHAPE")

    chunks, segments, paragraphs, tables = [], [], [], []
    offset = 0
    location_index = 0

    def add(text, node=None, *, key=False, fragment=None, table=None, row=None, column=None):
        nonlocal offset, location_index
        start = offset
        chunks.append(text)
        offset += len(text)
        location = {"id": "json-location-" + str(location_index), "text": text,
                    "source_pointer": "/context", "context_span": [start, offset]}
        location_index += 1
        if node is not None:
            location["json_source"] = binding(source, node, fragment, key=key)
        numbers = [{"text": m.group(), "source_text_span": [m.start(), m.end()],
                    "context_span": [start + m.start(), start + m.end()]}
                   for m in LEXICAL_NUMBER.finditer(text)]
        if node is not None:
            segments.append({**location, "numbers": numbers})
        if table is not None:
            table["cells"].append({**location, "row": row, "column": column})
        return location

    def literal(text):
        nonlocal offset
        chunks.append(text)
        offset += len(text)

    # Split only explicit, contiguous source prefixes; do not infer categories
    # or reorder non-contiguous rows.
    groups = []
    for key, row_node in root.children:
        prefix, separator, label = key.value.partition(" -- ")
        group = prefix if separator else None
        if not groups or groups[-1][0] != group:
            groups.append((group, []))
        groups[-1][1].append((key, row_node, label if separator else key.value))
    for group_index, (title, items) in enumerate(groups):
        if group_index:
            literal("\n\n")
        if title is not None:
            key = items[0][0]
            paragraphs.append(add(escape_cell(title), key, key=True, fragment=[0, len(title)]))
            literal("\n\n")
        table = {"id": "json-table-" + str(group_index), "source_pointer": "/context",
                 "rows": [], "cells": []}
        columns = {}
        for _, row_node, _ in items:
            for col_key, _ in row_node.children:
                columns.setdefault(col_key.value, col_key)
        labels = list(columns)
        table["rows"].append(["Item", *(escape_cell(label) for label in labels)])
        literal("| ")
        add("Item", table=table, row=0, column=0)
        for column, label in enumerate(labels, 1):
            literal(" | ")
            add(escape_cell(label), columns[label], key=True, table=table, row=0, column=column)
        literal(" |\n|" + "|".join(["---"] * (len(labels) + 1)) + "|\n")
        for row_index, (key, row_node, label) in enumerate(items, 1):
            values = {col.value: cell for col, cell in row_node.children}
            row_texts = [escape_cell(label)] + [
                escape_cell(plain(values[col])) if col in values else "[missing]"
                for col in labels]
            table["rows"].append(row_texts)
            literal("| ")
            fragment = [len(key.value) - len(label), len(key.value)]
            add(row_texts[0], key, key=True, fragment=fragment, table=table,
                row=row_index, column=0)
            for column, col in enumerate(labels, 1):
                literal(" | ")
                add(row_texts[column], values.get(col), table=table, row=row_index, column=column)
            literal(" |\n" if row_index != len(items) else " |")
        tables.append(table)
    return {"context": "".join(chunks), "source_content": {"paragraphs": paragraphs, "tables": tables},
            "context_mapping": mapping(segments)}


def mapping(segments):
    return {"offset_unit": "Unicode code points", "interval": "[start, end)",
            "source_root": "raw-record.json#/record", "segments": segments,
            "number_status": "lexical candidates only; meaning and units not validated"}


def assemble_table_string(source, node):
    """Unwrap the existing Markdown table without changing its decoded text."""
    context = node.value
    full = {"id": "json-array-table-text", "text": context, "source_pointer": "/context",
            "context_span": [0, len(context)], "json_source": binding(source, node, escaped=False)}
    numbers = [{"text": m.group(), "source_text_span": [m.start(), m.end()],
                "context_span": [m.start(), m.end()]} for m in LEXICAL_NUMBER.finditer(context)]
    table = {"id": "json-table-0", "source_pointer": "/context", "rows": [], "cells": []}
    offset = 0
    for line in context.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        if not content.strip() or re.fullmatch(r"\s*\|?[\s|:\-]+\|?\s*", content):
            offset += len(line)
            continue
        bounds = [m.start() for m in re.finditer(r"(?<!\\)\|", content)]
        if len(bounds) < 2:
            raise JsonContextError("JSON_ARRAY_TABLE_NOT_RECTANGULAR")
        row = []
        row_index = len(table["rows"])
        for column, (a, b) in enumerate(zip(bounds, bounds[1:])):
            raw = content[a + 1:b]
            start = offset + a + 1 + len(raw) - len(raw.lstrip())
            text = raw.strip()
            row.append(text)
            table["cells"].append({"id": f"json-array-cell-{row_index}-{column}",
                "text": text, "source_pointer": "/context", "context_span": [start, start + len(text)],
                "json_source": binding(source, node, [start, start + len(text)], escaped=False),
                "row": row_index, "column": column})
        table["rows"].append(row)
        offset += len(line)
    if not table["rows"] or len({len(row) for row in table["rows"]}) != 1:
        raise JsonContextError("JSON_ARRAY_TABLE_NOT_RECTANGULAR")
    return {"context": context, "source_content": {"paragraphs": [], "tables": [table]},
            "context_mapping": mapping([{**full, "numbers": numbers}])}


def validate_conversion(source, result):
    """Check the rendered cells against raw token spans, not carried-over values."""
    root = parse(source)
    expected, root_keys, keys = {}, {}, {}
    if root.kind == "object":
        for key, row in root.children:
            root_keys[key.pointer] = key
            keys[key.pointer] = key
            for col, node in row.children:
                expected[node.pointer] = node
                keys[col.pointer] = col
    elif root.kind == "array":
        expected = {node.pointer: node for node in root.children}
    else:
        raise JsonContextError("JSON_CONTEXT_NOT_CONTAINER")
    actual, observed_keys = {}, set()
    context = result["context"]
    locations = (result["context_mapping"]["segments"] + result["source_content"]["paragraphs"]
                 + [cell for table in result["source_content"]["tables"] for cell in table["cells"]])
    for location in locations:
        a, b = location["context_span"]
        if context[a:b] != location["text"]:
            raise JsonContextError("JSON_RENDERED_LOCATION_MISMATCH")
        source_info = location.get("json_source")
        if not source_info:
            continue
        a, b = source_info["source_span"]
        token = source[a:b]
        if token != source_info["raw_text"]:
            raise JsonContextError("JSON_SOURCE_TOKEN_MISMATCH")
        pointer = source_info["pointer"]
        if source_info["value_type"] == "key":
            if pointer not in keys or [a, b] != [keys[pointer].start, keys[pointer].end]:
                raise JsonContextError("JSON_KEY_SOURCE_POSITION_MISMATCH")
        elif pointer not in expected or source_info["value_type"] != expected[pointer].kind:
            raise JsonContextError("JSON_CELL_TYPE_MISMATCH")
        text = json.loads(token) if source_info["value_type"] in ("key", "string") else token
        if not isinstance(text, str):
            raise JsonContextError("JSON_CELL_TYPE_MISMATCH")
        left, right = source_info["decoded_span"]
        if not 0 <= left <= right <= len(text):
            raise JsonContextError("JSON_DECODED_FRAGMENT_MISMATCH")
        decoded = unescape_cell(location["text"]) if source_info["markdown_escaped"] else location["text"]
        if text[left:right] != decoded:
            raise JsonContextError("JSON_CELL_VALUE_MISMATCH")
        if source_info["value_type"] == "key":
            if pointer in root_keys and [left, right] == [len(text) - len(decoded), len(text)]:
                observed_keys.add(pointer)
        elif [left, right] == [0, len(text)]:
            if pointer not in expected or source_info["value_type"] != expected[pointer].kind:
                raise JsonContextError("JSON_CELL_TYPE_MISMATCH")
            if [a, b] != [expected[pointer].start, expected[pointer].end]:
                raise JsonContextError("JSON_CELL_SOURCE_POSITION_MISMATCH")
            actual[pointer] = decoded
    if set(actual) != set(expected) or observed_keys != set(root_keys):
        raise JsonContextError("JSON_SOURCE_COVERAGE_MISMATCH")
    row_labels = [cell["json_source"]["pointer"] for table in result["source_content"]["tables"]
                  for cell in table["cells"] if cell["column"] == 0 and cell["row"] > 0
                  and cell.get("json_source", {}).get("value_type") == "key"]
    if root.kind == "object" and row_labels != list(root_keys):
        raise JsonContextError("JSON_SOURCE_ROW_ORDER_MISMATCH")
    for table in result["source_content"]["tables"]:
        for cell in table["cells"]:
            if table["rows"][cell["row"]][cell["column"]] != cell["text"]:
                raise JsonContextError("JSON_TABLE_CELL_MISMATCH")
    for segment in result["context_mapping"]["segments"]:
        for number in segment["numbers"]:
            a, b = number["source_text_span"]
            left, right = number["context_span"]
            if (segment["text"][a:b] != number["text"] or context[left:right] != number["text"]
                    or [left, right] != [segment["context_span"][0] + a, segment["context_span"][0] + b]):
                raise JsonContextError("JSON_NUMBER_LOCATION_MISMATCH")
    return {"status": "PASS", "value_cells": len(expected), "root_labels": len(root_keys),
            "tables": len(result["source_content"]["tables"]),
            "rows": sum(len(t["rows"]) - 1 for t in result["source_content"]["tables"]),
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "context_sha256": hashlib.sha256(context.encode()).hexdigest(),
            "checks": ["original_leaf_coverage", "root_label_coverage", "typed_literal_values",
                       "raw_token_spans", "rendered_spans", "table_coordinates", "numeric_spans"]}
