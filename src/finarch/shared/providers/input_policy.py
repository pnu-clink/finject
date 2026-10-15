"""Reject preconstructed model outputs before a CLI process can start."""


def reject_preconstructed(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {'value_intent', 'draft_sentence', 'draft', 'wording'}:
                raise ValueError('PRECONSTRUCTED_OUTPUT_FORBIDDEN: '+key)
            if key == 'exact_text' and item is not None:
                raise ValueError('FIXED_RESPONSE_FORBIDDEN')
            # Whitespace defines paragraph placement, not generated wording.
            if key == 'required_prefix' and item and (not isinstance(item, str) or item.strip()):
                raise ValueError('FIXED_RESPONSE_PREFIX_FORBIDDEN')
            reject_preconstructed(item)
    elif isinstance(value, list):
        for item in value:
            reject_preconstructed(item)


def validate_model_input(role, payload):
    from finarch.dataset.schemas.ea_inverse_review import ROLE
    if role == ROLE and set(payload) != {'context', 'question'}:
        raise ValueError('EA_INVERSE_QC_ONLY_REQUIRED')
    if role in {'01-preparation.03-calculation.pot', '02-generation.02-generate-text.realization', 'shared.01-02.02-03.review-and-validation'}:
        reject_preconstructed(payload)
        original_review = (role == 'shared.01-02.02-03.review-and-validation'
                           and payload.get('axis') == 'ANSWER'
                           and payload.get('intent',{}).get('preserve_original') is True)
        def check(value, top=False):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {'reference', 'reference_answer', 'private_reference', 'gold', 'expected_answer', 'expected_judgment'}:
                        if not (original_review and top and key == 'reference_answer'):
                            raise ValueError('PRESET_ANSWER_OR_JUDGMENT_FORBIDDEN: '+key)
                    check(item)
            elif isinstance(value, list):
                for item in value:
                    check(item)
        check(payload, top=True)
