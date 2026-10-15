"""Select generation and validation profiles without making model calls."""
import argparse
import json
import re
from pathlib import Path
from finarch.shared.providers.profiles import DEFAULT, read_profile, selected_profile


def select(path=DEFAULT, *, generation=None, validation=None):
    path = Path(path)
    text = path.read_text()
    for group, name in (('generation', generation), ('validation', validation)):
        if name is None:
            continue
        read_profile(path, name)
        pattern = r'(?m)^' + group + r'\s*=\s*[^\n]+'
        text, count = re.subn(pattern, lambda match: group + ' = ' + json.dumps(name), text)
        if count != 1:
            raise ValueError('UNIQUE_SELECTION_KEY_REQUIRED:' + group)
    if generation is not None or validation is not None:
        temporary = path.with_suffix('.tmp')
        temporary.write_text(text)
        temporary.replace(path)
    return {group: {key: value for key, value in selected_profile(path, role).items()
                    if key in ('id', 'provider', 'model', 'effort')}
            for group, role in (('generation', '02-generation.02-generate-text.realization'), ('validation', 'shared.01-02.02-03.review-and-validation'))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profiles', type=Path, default=DEFAULT)
    parser.add_argument('--generation')
    parser.add_argument('--validation')
    args = parser.parse_args()
    print(json.dumps(select(args.profiles, generation=args.generation, validation=args.validation), indent=2))
