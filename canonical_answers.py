"""Pure canonical profile facts. Never use an agent answer as its own source.

The caller must load the accepted, digest-verified profile, not merge an answer
file into it. Returned values are private; errors intentionally omit values.
"""
from __future__ import annotations


class CanonicalAnswerError(ValueError):
    """A canonical fact is unknown, malformed, or conflicting."""


# Paths are the actual profile.json schema, not guessed flattened defaults.
FACT_PATHS = {
    'first_name': ('name.first',), 'phone': ('contact.phone',), 'email': ('contact.email',),
    'school': ('education.university',), 'degree': ('education.degree',),
    'discipline': ('education.major',), 'gpa': ('education.gpa',),
    'education_end_year': ('education.expected_graduation',),
    'graduation_season': ('education.graduation_season',),
    'work_authorization': ('work_authorization', 'screening_defaults.authorized_to_work_us'),
    'sponsorship_now': ('requires_sponsorship', 'screening_defaults.require_sponsorship'),
    'sponsorship_future': ('requires_sponsorship', 'screening_defaults.require_sponsorship'),
    'is_18_or_older': ('screening_defaults.is_18_or_older',),
    'willing_to_relocate': ('screening_defaults.willing_to_relocate',),
    'outside_business_activities': ('screening_defaults.outside_business_activities',),
    'gender': ('gender', 'screening_defaults.demographic_disclosures.gender'),
    'race': ('race_ethnicity', 'screening_defaults.demographic_disclosures.race'),
    'veteran': ('veteran_status', 'screening_defaults.demographic_disclosures.veteran'),
    'disability': ('disability', 'screening_defaults.demographic_disclosures.disability'),
    'how_did_you_hear': ('screening_defaults.how_did_you_hear',),
    'social_media_source': ('screening_defaults.social_media_source',),
    'desired_salary': ('screening_defaults.desired_salary',),
    'city': ('contact.location.city',), 'resume': ('resume.primary',),
    'last_name': ('name.last',), 'full_name': ('name.full',),
    'country': ('contact.location.country',), 'state': ('contact.location.state',),
    'zip': ('contact.location.zip',), 'linkedin': ('links.linkedin',),
}


BOOLEAN_FIELDS = frozenset({'work_authorization', 'sponsorship_now', 'sponsorship_future', 'sponsorship_now_or_future',
                            'is_18_or_older', 'willing_to_relocate', 'outside_business_activities'})
TENANT_ALIASES = {
    'schonfeld': {
        'school': {'University of California, San Diego': 'University of California - San Diego'},
        'degree': {'Bachelor of Science': "Bachelor's Degree"},
        'current_degree': {'Bachelor of Science': "Bachelor's"},
        # Only this learned tenant lacks Data Science; never a generic fallback.
        'discipline': {'Data Science': 'Other'},
    },
}
FACT_PATHS['current_degree'] = FACT_PATHS['degree']
for alias, field in {'sponsorship': 'sponsorship_now', 'requires_sponsorship': 'sponsorship_now',
                     'authorized_to_work_us': 'work_authorization'}.items():
    FACT_PATHS[alias] = FACT_PATHS[field]
BOOLEAN_FIELDS = BOOLEAN_FIELDS | {'sponsorship', 'requires_sponsorship', 'authorized_to_work_us'}


def _normalize(field: str, value: object) -> str:
    from decimal import Decimal, InvalidOperation
    if isinstance(value, bool):
        if field not in BOOLEAN_FIELDS:
            raise CanonicalAnswerError(f'canonical profile fact malformed for {field}')
        return 'Yes' if value else 'No'
    if not isinstance(value, (str, int, float)) or not str(value).strip():
        raise CanonicalAnswerError(f'canonical profile fact malformed for {field}')
    text = str(value).strip()
    if field in BOOLEAN_FIELDS and text not in ('Yes', 'No'):
        raise CanonicalAnswerError(f'canonical profile fact malformed for {field}')
    if field == 'gpa':
        try:
            number = Decimal(text)
            if not number.is_finite() or number < 0:
                raise InvalidOperation
            return format(number.normalize(), 'f')
        except InvalidOperation:
            raise CanonicalAnswerError(f'canonical profile fact malformed for {field}') from None
    if field == 'phone':
        if any(not (c.isascii() and c.isdigit()) and c not in '+(). -' for c in text):
            raise CanonicalAnswerError('canonical profile phone must not be masked')
        text = ''.join(c for c in text if c.isdigit())
        if not text:
            raise CanonicalAnswerError('canonical profile phone missing')
    return text


def resolve_fact(profile: dict, field: str, *, tenant: str | None = None) -> str | bool:
    """Resolve a semantic field independently of actions, or fail closed.

    application_facts is an explicit accepted-profile extension, not an agent
    answer store. Duplicated facts must agree; aliases are tenant-scoped.
    """
    aliases = TENANT_ALIASES.get(tenant or '', {}).get(field, {})
    values = []
    if field == 'sponsorship_now_or_future':
        timeframes = [resolve_fact(profile, key, tenant=tenant)
                      for key in ('sponsorship_now', 'sponsorship_future')]
        values.append('Yes' if 'Yes' in timeframes else 'No')
    for path in (*FACT_PATHS.get(field, ()), f'application_facts.{field}'):
        value = profile
        for part in path.split('.'):
            value = value.get(part) if isinstance(value, dict) else None
        if value is not None:
            text = _normalize(field, value)
            values.append(aliases.get(text, text))
    if not values:
        raise CanonicalAnswerError(f'canonical profile fact missing for {field}')
    if len(set(values)) != 1:
        raise CanonicalAnswerError(f'canonical profile facts conflicting for {field}')
    return values[0]


def verify_profile_answers(profile: dict, answers: dict, *, tenant: str | None = None) -> None:
    """Validate proposed semantic answers; success never proves a Review readback."""
    for field, answer in answers.items():
        expected = resolve_fact(profile, field, tenant=tenant)
        actual = answer.get('exact_option') if isinstance(answer, dict) else answer
        if isinstance(answer, dict) and 'selected_option' in answer and _normalize(field, answer['selected_option']) != expected:
            raise CanonicalAnswerError(f'canonical profile selected option conflicting for {field}')
        if _normalize(field, actual) != expected:
            raise CanonicalAnswerError(f'canonical profile fact conflicting for {field}')


def canonical_review_fields(profile: dict, controls: dict, *, selectors: list[str] | None = None,
                            tenant: str | None = None) -> dict:
    """Resolve learned Review controls, including prefilled fields with no actions.

    If selecting a subset, callers must supply the union of all populated and
    required Review selectors; reconciliation rejects ungrounded extra fields.
    """
    by_selector = {}
    for field, control in controls.items():
        if not isinstance(control, dict):
            raise CanonicalAnswerError('canonical profile control map malformed')
        if control.get('operation') in ('cdp_upload', 'submit'):
            continue
        selector = control.get('selector')
        if not isinstance(selector, str) or not selector or selector in by_selector:
            raise CanonicalAnswerError('canonical profile control map ambiguous')
        by_selector[selector] = field
    requested = list(by_selector) if selectors is None else selectors
    if any(selector not in by_selector for selector in requested):
        raise CanonicalAnswerError('canonical profile unknown Review selector')
    return {selector: resolve_fact(profile, by_selector[selector], tenant=tenant) for selector in requested}


def verify_actions(profile: dict, actions: list[dict], controls: dict, *, tenant: str | None = None) -> None:
    """Reject drift or conflicting values before executing learned semantic actions."""
    seen = set()
    for action in actions:
        field = action.get('field')
        control = controls.get(field)
        if (not isinstance(field, str) or field in seen or not isinstance(control, dict)
            or action.get('selector') != control.get('selector')
            or action.get('operation') != control.get('operation')):
            raise CanonicalAnswerError('canonical profile action binding mismatch')
        seen.add(field)
        verify_profile_answers(profile, {field: action.get('value')}, tenant=tenant)
        if 'expected_value' in action:
            verify_profile_answers(profile, {field: action['expected_value']}, tenant=tenant)
