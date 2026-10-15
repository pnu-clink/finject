"""Stage role names, with read compatibility for saved configurations."""
LEGACY_ROLES = {'preparation.revise': '01-preparation.02-review-and-correct.revision', 'preparation.evidence': '01-preparation.03-calculation.review-answer-evidence', 'pot.author': '01-preparation.03-calculation.pot', 'dtt.realize': '02-generation.02-generate-text.realization', 'dtt.audit': 'shared.01-02.02-03.review-and-validation', 'dtt.feedback': '02-generation.feedback.case-feedback'}

def resolve_role(role):
    return LEGACY_ROLES.get(role, role)

def normalize_config(config):
    result = dict(config)
    for key in ('roles', 'capabilities'):
        if isinstance(result.get(key), dict):
            normalized = {}
            for role, value in result[key].items():
                current = resolve_role(role)
                if current in normalized and normalized[current] != value:
                    raise ValueError('CONFLICTING_ROLE_CONFIGURATION')
                normalized[current] = value
            result[key] = normalized
    if result.get('use_model_selection'):
        result.setdefault('roles', {}).setdefault('01-preparation.05-verification.semantic', {})
        result.setdefault('capabilities', {}).setdefault('01-preparation.05-verification.semantic', {'tools': [], 'skills': []})
        result.setdefault('roles', {}).setdefault('shared.01-06.02-04.exception-handler', {})
        result.setdefault('capabilities', {}).setdefault('shared.01-06.02-04.exception-handler', {'tools': [], 'skills': []})
    if result.get("use_model_selection"):
        from finarch.dataset.schemas.failure_interpretation import ROLE, TRANSLATION_ROLE
        for role in (ROLE, TRANSLATION_ROLE):
            result.setdefault("roles", {}).setdefault(role, {})
            result.setdefault("capabilities", {}).setdefault(role, {"tools": [], "skills": []})
    from finarch.dataset.schemas.ea_inverse_review import ROLE
    audit = 'shared.01-02.02-03.review-and-validation'
    if audit in result.get('roles', {}):
        result['roles'].setdefault(ROLE, dict(result['roles'][audit]))
        # This independent review never receives tool access or feedback.
        result.setdefault('capabilities', {}).setdefault(ROLE, {'tools': [], 'skills': []})
    return result
