# Text-realization instructions have moved

This file is no longer used for LLM calls. Current instructions are split into four types in [realize-prompts/README.md](realize-prompts/README.md). `realization_prompts.py` selects one type using the request's `axis` and attaches the shared output contract. The complete request, selected file, and hash are saved in `01-input.json`. Read the original saved prompt in each historical run when inspecting an older execution.
