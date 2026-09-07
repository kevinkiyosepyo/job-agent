# GPA clauses from saved SWE pilots

Use when an official requirement says `GPA of X or above`. The narrow `posting_qualifications.qualification_decision` grammar accepts this complete clause as equivalent to its existing `Minimum GPA of X` clause. It does not accept partial sentence matching, alternate grading scales, appended mandatory requirements or preferred qualifications as verified requirements.

Procedure:
1. Keep the entire original posting content and source metadata. Never replace a complete posting with its easiest GPA line to manufacture a qualified result.
2. Read only the canonical profile source under the umbrella; the GPA must be a finite numeric value on the supported 0–4 scale. Missing, string, boolean, out-of-range or below-threshold values do not pass. Do not round up.
3. Evaluate all clauses. A matched GPA does not verify hardware, embedded, communication, enrollment or other experience. Unsupported mandatory clauses and unrelated unparsed body content remain blocked. The decision retains complete posting/profile commitments.
4. Distinguish a required form response from a qualification that requires Yes. A junior-year Yes/No prompt is not itself a requirement that the candidate answer Yes.

Verification through `terminal`: run `run_offline_tests.py tests/test_posting_gpa_above.py tests/test_posting_qualifications.py -q` with the installed interpreter, then the full guarded suite. Test the below-threshold backend seam parks before worker requests and attempt creation. Saved-source replay should preserve all other checks and the full-body blocked result while identifying the GPA clause accurately.

Limits: this is a conservative grammar extension, not general required-versus-preferred section classification or internship eligibility support. The narrow explicit and immediate-heading GPA preference cases below are supported; other unparsed body content still blocks. It adds no live ATS capability, submission authorization, profile fact or resume authority. Prefer a truthful blocked result to deleting other employer requirements.

## Explicit not-required GPA preference

The complete clause `Minimum GPA of X or higher is preferred, but not required` is an explicit preference, independently of a section heading. One leading literal `* ` list marker is accepted for this clause only because some official structured job descriptions carry text bullets. HTML list markup also works. This does not strip arbitrary bullets or generalize other requirement wording.

The parser records `constraint: gpa`, the actual canonical match in `verified`, and `requirement: preferred` only for thresholds within 0–4. It does not round a below-threshold GPA up or invent missing/invalid GPA values. A preference-only posting still cannot establish eligibility. Out-of-scale thresholds, major GPA, different grading scales, escaped documents, conditional or appended mandatory wording remain unverified and do not gain this waiver. An ordinary `Minimum GPA` clause remains mandatory; this explicit preference never waives other clauses or leaks to a later minimum. A `Desired` heading is not by itself a general supported section exemption.

Use the complete official body, including clearance, course, work-experience and date clauses. For Eightfold-backed employer pages where ordinary extraction is dominated by configuration, an exact official page's unambiguous `application/ld+json` JobPosting can provide the full description and title/location/date metadata. Keep the raw source bytes and original description, corroborate identity, and do not present published dates, descriptions or schema as rendered application state. Do not execute configuration scripts or treat embedded CAPTCHA text as rendered clearance/gate proof.

Through `terminal`, run guarded `run_offline_tests.py tests/test_explicit_preferred_gpa.py tests/test_preferred_gpa_section.py tests/test_posting_qualifications.py -q`, then the full guarded suite. Replay whole saved descriptions, requiring unchanged source/profile commitments and every non-target check. Unverified required content must still park the backend before any worker request or attempt creation. This adds no connected ATS capability or submission authority.

## Scope-specific GPA and application preferences

A requirement for `Major GPA` is not a cumulative-GPA requirement. Do not compare the canonical cumulative GPA to it or invent a major GPA. The narrow full-clause parser leaves that wording unsupported; this is not evidence of a failed minimum or a bug in its generic-GPA matcher. Retain the complete requirement and seek an independently grounded scope-specific fact before any eligibility decision.

Some official listings also say applying selects the candidate's top preference and excludes other engineering/quant roles for the season. Treat that as a material user preference, not a routine Yes checkbox or permission inferred from a generic apply request. Preserve it when reading the full posting; unknown preference and major GPA can park a candidate without claiming the employer rejected them. Interview/assessment AI prohibitions concern those stages and must be honored; they do not establish that a public application page is itself an active assessment.

## Immediate explicit preferred GPA

When `Preferred Skills and Experience` or `Preferred Qualifications` is a whole heading (optional colon, case-insensitive), only the immediately following nonempty `GPA of X or above` clause, with X on the supported 0–4 scale, is recorded as `requirement: preferred`. Its `verified` field still reports the actual canonical GPA match; a preference is not a mandatory minimum. `Minimum GPA` wording without the explicit not-required clause above, malformed/out-of-scale thresholds, compound wording and other clause types never gain this exemption. Scope expires after that one clause or another heading; this is deliberately not a whole-section waiver.

The result is qualified only if at least one non-preferred check exists and every such check is verified. A preference-only posting does not prove eligibility. Unknown prose or an unverified mandatory clause still parks before browser requests. Preserve full posting/profile commitments, and do not use an extracted GPA-only snippet as whole-posting proof. HTML parsing does not confer rendered visibility or decode escaped tags into another document.

Through `terminal`, also run `run_offline_tests.py tests/test_preferred_gpa_section.py -q` with the configured interpreter, then the full guarded suite. A saved full posting replay must retain all non-heading checks, label only its immediate GPA preference, and remain blocked wherever other required/unknown content remains unresolved.
