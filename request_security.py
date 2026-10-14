"""Origin checks shared by dashboard mutations and the Orbit bridge."""
from urllib.parse import urlsplit


def same_origin(headers):
    origin = headers.get('Origin', '')
    host = headers.get('Host', '')
    try:
        parsed = urlsplit(origin)
        authority = urlsplit(parsed.scheme + '://' + host)
        return (parsed.scheme in ('http', 'https') and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None
                and not parsed.path and not parsed.query and not parsed.fragment
                and authority.username is None and authority.password is None
                and not authority.path and not authority.query and not authority.fragment
                and parsed.hostname.lower() == (authority.hostname or '').lower()
                and (parsed.port or (443 if parsed.scheme == 'https' else 80))
                == (authority.port or (443 if parsed.scheme == 'https' else 80)))
    except (ValueError, UnicodeError):
        return False


def allowed_mutation(headers):
    if headers.get('Sec-Fetch-Site', '').lower() in ('cross-site', 'same-site'):
        return False
    if headers.get('Origin') is not None:
        return same_origin(headers)
    # Native clients do not send Origin; a custom header rules out HTML forms.
    return headers.get('X-Dashboard-Action') == 'write'
