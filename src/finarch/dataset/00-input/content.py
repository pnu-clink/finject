"""Common original-content structure and exact Unicode character locations.

Numbers are lexical candidates, not verified financial quantities or evidence.
JSON pointers refer to the record inside raw-record.json.
"""
import re
import importlib

json_context = importlib.import_module("finarch.dataset.00-input.json_context")

NUMBER = re.compile(r"(?<!\w)[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?(?!\w)")


def assemble(record, kind):
    """Route by source schema, then normalize the actual Finance context shape.

    Source IDs remain provenance; they do not force prose into JSON conversion.
    Existing TAT-QA tables use their native table and paragraph bindings.
    """
    chunks, paragraphs, tables, segments = [], [], [], []
    offset = 0

    def append(text, pointer=None, identity=None):
        nonlocal offset
        start = offset
        chunks.append(text)
        offset += len(text)
        if pointer is not None:
            segments.append({"id": identity, "context_span": [start, offset],
                             "source_pointer": pointer, "text": text,
                             "numbers": [{"text": match.group(),
                                          "source_text_span": [match.start(), match.end()],
                                          "context_span": [start + match.start(), start + match.end()]}
                                         for match in NUMBER.finditer(text)]})
        return [start, offset]

    if kind == "finance":
        text = record["context"]
        converted = json_context.assemble_json(text)
        if converted is not None:
            json_context.validate_conversion(text, converted)
            return converted
        span = append(text, "/context", "paragraph-0")
        paragraphs.append({"id": "paragraph-0", "text": text, "source_pointer": "/context",
                           "context_span": span})
    elif kind == "tatqa":
        rows = record["table"]["table"]
        cells = []
        for row_index, row in enumerate(rows):
            if row_index:
                append("\n")
            for column_index, cell in enumerate(row):
                if column_index:
                    append(" | ")
                pointer = f"/table/table/{row_index}/{column_index}"
                identity = f"table-0-cell-{row_index}-{column_index}"
                span = append(str(cell), pointer, identity)
                cells.append({"id": identity, "row": row_index, "column": column_index,
                              "text": str(cell), "source_pointer": pointer, "context_span": span})
        tables.append({"id": "table-0", "source_pointer": "/table/table", "rows": rows, "cells": cells})
        append("\n\n")
        for position, (original_index, paragraph) in enumerate(
                sorted(enumerate(record["paragraphs"]), key=lambda pair: pair[1]["order"])):
            if position:
                append("\n")
            pointer = f"/paragraphs/{original_index}/text"
            identity = f"paragraph-{original_index}"
            span = append(paragraph["text"], pointer, identity)
            paragraphs.append({"id": identity, "text": paragraph["text"], "source_pointer": pointer,
                               "context_span": span})
    else:
        raise ValueError("UNKNOWN_CONTENT_KIND")
    return {"context": "".join(chunks),
            "source_content": {"paragraphs": paragraphs, "tables": tables},
            "context_mapping": {"offset_unit": "Unicode code points", "interval": "[start, end)",
                                "source_root": "raw-record.json#/record", "segments": segments,
                                "number_status": "lexical candidates only; meaning and units not validated"}}
