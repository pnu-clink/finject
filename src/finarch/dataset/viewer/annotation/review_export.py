"""Embed recipient-specific requests and verified text in one offline HTML."""
from pathlib import Path

from finarch.dataset.viewer.evaluation_export import inline_json

TEMPLATE = Path(__file__).resolve().parents[5] / 'viewer/dataset/annotation/reviewer.html'
SHARED = TEMPLATE.parents[2] / 'shared'


def render(document):
    return (TEMPLATE.read_text()
            .replace('__FINARCH_I18N_CSS__', (SHARED / 'i18n.css').read_text())
            .replace('__FINARCH_I18N_JS__', (SHARED / 'i18n.js').read_text())
            .replace('__REVIEW_DATA__', inline_json(document)))
