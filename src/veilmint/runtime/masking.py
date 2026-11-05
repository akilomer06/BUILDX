"""Pure API identifier masking; no persistence or logging dependencies."""
from collections.abc import Mapping
from copy import deepcopy


def mask_api_identifiers(payload: dict, rules: Mapping[str,str]) -> dict:
    """Mask explicit top-level identifiers, rejecting missing/invalid values."""
    result=deepcopy(payload)
    for field,kind in rules.items():
        value=result.get(field)
        if not isinstance(value,str) or not value.strip():
            raise ValueError('API identifier cannot be masked safely.')
        if kind=='account':
            masked='*'*max(1,len(value)-4)+value[-4:] if len(value)>4 else '*'*len(value)
        elif kind=='email':
            local,separator,domain=value.partition('@')
            if not local or not separator or not domain or '@' in domain:
                raise ValueError('API email cannot be masked safely.')
            prefix=local[0] if len(local)>1 else ''
            masked=prefix+'*'*max(1,len(local)-len(prefix))+'@'+domain
        elif kind=='phone':
            positions=[i for i,char in enumerate(value) if char.isdigit()]
            hide=set(positions[:-4] if len(positions)>4 else positions)
            if not hide:raise ValueError('API phone cannot be masked safely.')
            masked=''.join('*' if i in hide else char for i,char in enumerate(value))
        elif kind=='name':
            masked=' '.join(word[0]+'*'*(len(word)-1) if len(word)>1 else '*' for word in value.split())
        else:
            raise ValueError('Unsupported API masking rule.')
        if masked==value:raise ValueError('API identifier was not masked.')
        result[field]=masked
    return result
