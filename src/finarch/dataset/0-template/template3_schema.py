class __CLASS__(StrictModel):
    """Local-file provenance for __DATASET__; no invented remote origin."""
    dataset: Literal[__DATASET_LITERAL__]
    name: Text
    sha256: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
