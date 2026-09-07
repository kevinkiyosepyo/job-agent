"""Narrow deterministic qualification grammar; all unparsed body text blocks.

This is not a general eligibility classifier. Only full, explicit clauses below
are supported. No inferred skills, enrollment, citizenship, date or LLM judgment.
Even ordinary unrecognized employer prose parks for verification. The decision
commits the complete raw posting and independently loaded canonical profile.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from html.parser import HTMLParser


def content_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


class _Body(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts=[]
    def handle_starttag(self, tag, attrs):
        if tag in {'p','li','br','div','h1','h2','h3','ul','ol'}:
            self.parts.append('\n')
    def handle_endtag(self, tag):
        self.handle_starttag(tag, [])
    def handle_data(self, data):
        self.parts.append(data)


def _month(value):
    return datetime.strptime(value, '%B').month


def _graduation_matches(education, facts, lower, upper):
    def bound(value, end):
        if re.fullmatch(r'20\d{2}', value):
            return int(value), 12 if end else 1
        month, year=value.split()
        return int(year), _month(month)
    low, high=bound(lower, False), bound(upper, True)
    value=education.get('expected_graduation')
    if not isinstance(value, str) or not re.fullmatch(r'20\d{2}(?:-\d{2})?', value):
        return False
    year=int(value[:4])
    month=int(value[5:]) if len(value)>4 else None
    explicit=facts.get('education_end_month')
    if explicit:
        canonical_month=_month(explicit)
        if month is not None and month != canonical_month:
            return False
        month=canonical_month
    if month is not None and not 1 <= month <= 12:
        return False
    # Without a month, the entire possible year must fit: never invent a date.
    return low <= (year, month or 1) <= (year, month or 12) <= high


def qualification_decision(posting, profile):
    result={'version':1, 'posting_sha256':content_hash(posting),
            'profile_sha256':content_hash(profile), 'status':'blocked_fact',
            'reason':'posting_qualification_unverified', 'checks':[]}
    if not isinstance(posting, dict) or not isinstance(posting.get('content'), str) or not posting['content'].strip():
        result['reason']='official_posting_body_missing'
        return result
    parser=_Body()
    # Decode character references only as text, never as a second HTML layer.
    # Escaped documents remain unsupported literal clauses and fail closed.
    parser.feed(posting['content'])
    parser.close()
    clauses=[' '.join(line.split()).rstrip('.').replace('’', "'")
             for line in re.split(r'[\n;]', ''.join(parser.parts)) if line.strip()]
    education=profile.get('education', {})
    facts=profile.get('application_facts', {})
    preferred_next = False
    for clause in clauses:
        heading = clause.casefold().rstrip(':')
        if heading in {'preferred skills and experience', 'preferred qualifications'}:
            preferred_next = True
            continue
        preferred_gpa = preferred_next
        preferred_next = False  # Never leak scope across another clause or heading.
        if heading in {'qualifications','requirements','required qualifications'}:
            continue
        kind=None
        matched=False
        try:
            explicit_preferred_gpa = re.fullmatch(
                r'(?:\* )?Minimum GPA of ([0-4](?:\.\d+)?) or higher is preferred, but not required',
                clause, re.I)
            gpa=(explicit_preferred_gpa
                 or re.fullmatch(r'Minimum GPA(?: of)? ([0-4](?:\.\d+)?)', clause, re.I)
                 or re.fullmatch(r'GPA of ([0-4](?:\.\d+)?) or above', clause, re.I))
            graduation=re.fullmatch(r'Graduation between ((?:[A-Za-z]+ )?20\d{2}) and ((?:[A-Za-z]+ )?20\d{2})', clause, re.I)
            skills=re.fullmatch(r'Required skills: ([A-Za-z0-9+#., /-]+)', clause, re.I)
            if gpa:
                kind='gpa'
                preferred_gpa = ((explicit_preferred_gpa is not None
                                  or (preferred_gpa and clause.casefold().startswith('gpa of ')))
                                 and 0 <= float(gpa[1]) <= 4)
                value=education.get('gpa')
                matched=(type(value) in (int,float) and math.isfinite(value)
                         and 0 <= float(gpa[1]) <= value <= 4)
            elif graduation:
                kind='graduation'
                matched=_graduation_matches(education, facts, graduation[1], graduation[2])
            elif clause.casefold()=="must be currently enrolled in a bachelor's degree program":
                kind='enrollment'
                matched=(education.get('currently_enrolled') is True
                         and education.get('degree') in {'Bachelor of Science','Bachelor of Arts'})
            elif clause.casefold()=='u.s. citizenship required':
                kind='citizenship'
                matched=profile.get('citizenship')=='United States'
            elif skills:
                kind='skills'
                known=profile.get('skills')
                required={s.strip().casefold() for s in skills[1].split(',')}
                matched=(isinstance(known,list) and all(isinstance(s,str) for s in known)
                         and bool(required) and '' not in required
                         and required <= {s.casefold() for s in known})
        except (ValueError, TypeError, AttributeError):
            matched=False
        check = {'constraint':kind or 'unsupported', 'verified':bool(matched)}
        if preferred_gpa and kind == 'gpa':
            check['requirement'] = 'preferred'
        result['checks'].append(check)
    required_checks = [c for c in result['checks'] if c.get('requirement') != 'preferred']
    if required_checks and all(c['verified'] for c in required_checks):
        result.update(status='qualified', reason='explicit_canonical_requirements_matched')
    return result
