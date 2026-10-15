"""Validate batch controls and snapshot selected provider profiles before calls."""
import json
import re
from pathlib import Path
from finarch.shared.providers.profiles import read_profile


def load(path):
    value = json.loads(Path(path).read_text())
    if value.get('version') != 1:
        raise ValueError('UNSUPPORTED_HYPERPARAMETER_VERSION')
    count = value['dataset']['count']
    if type(count) is not int or count < 1:
        raise ValueError('INVALID_DATASET_COUNT')
    for stage, cap in (('preparation', 10), ('generation', 2)):
        for key, maximum in (('max_rounds', 3), ('concurrency', cap)):
            number = value[stage][key]
            if type(number) is not int or not 1 <= number <= maximum:
                raise ValueError('INVALID_HYPERPARAMETER:' + stage + '.' + key)
    for group in ('generation', 'validation'):
        name = value['models'][group + '_profile']
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            raise ValueError('INVALID_MODEL_PROFILE')
    return value


def profile_snapshot(path, controls):
    text = Path(path).read_text()
    for group in ('generation', 'validation'):
        name = controls['models'][group + '_profile']
        read_profile(path, name)
    selection = '[selection]\n' + ''.join(
        f'{group} = "{controls["models"][group + "_profile"]}"\n'
        for group in ('generation', 'validation'))
    return re.sub(r'(?ms)^\[selection\]\s*.*?(?=^\[|\Z)', '', text) + '\n' + selection
