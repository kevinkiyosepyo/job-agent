# Answer once, reuse on future applications

After cloning the repo and installing `requirements.txt`, run:

```bash
python onboarding.py
```

No Chrome, Google Sheets, employer login, or application submission is needed for setup. Use Python 3.11 or newer. Password storage requires macOS Keychain; you can complete the questionnaire without it.

## What it asks

| Section | Questions | Why save it? |
|---|---|---|
| Basics | Name, contact information, location, school, degree, major, GPA, resume | Avoid repeating personal details on each form |
| US eligibility | US citizenship, US work authorization, sponsorship now and in the future, OPT and CPT | Keep legally different questions separate |
| Disclosures | Company affiliations, outside business activities, restrictive covenants | Reuse your own answers instead of guessing |
| Employer history | Current employment, former employment, and relatives at each named company | Prevent an answer for one employer from being reused for another |
| Availability and preferences | Graduation, start dates, relocation, target roles, compensation | Reduce routine follow-up questions |
| Optional demographics | Your chosen disclosure answers | Leave unanswered rather than infer personal attributes |
| Account setup | An optional reusable job-portal password, including Workday | Avoid repeatedly asking you to choose a password for new portal accounts |

Screening questions support **Yes / No / unknown**. Unknown is not No. OPT (Optional Practical Training) and CPT (Curricular Practical Training) are not automatically interchangeable with employer sponsorship. If unsure, leave the answer unknown and ask your school's designated school official or another qualified adviser. This questionnaire records what you tell it; it does not decide immigration eligibility.

A general answer about company affiliations does not establish that you have never worked at every company or have no relatives there. Add explicit employer records for those questions. Company matching ignores case and repeated spaces, but it does not guess subsidiaries or aliases. Add each exact employer name when needed.

## Review, save, and update

The wizard shows your answers for review before saving. The default save response is No. It starts fresh without borrowing the repository owner's identity or the example profile's fictional answers.

```bash
# Check setup and see which screening facts are still unknown.
python onboarding.py --check

# Update your saved answers; preserve unrelated profile fields.
python onboarding.py

# Set up the questionnaire without touching Keychain.
python onboarding.py --skip-credentials

# Use another private profile destination.
python onboarding.py --profile /path/to/private/profile.json
python onboarding.py --profile /path/to/private/profile.json --check
```

The default profile is `profile.json` beside the script. It is gitignored and saved atomically with owner-only file permissions (`0600`). If you use a custom destination, keep it outside version control or add that exact path to your ignore rules before use. Tracked/example files and unsafe destinations are refused. Do not paste profile contents into issues or commit them. The final review contains your personal answers, so run setup in a private terminal rather than recording or streaming it.

`--check` is a setup checklist, not proof of live application readiness. It does not authorize submission, log into a portal, or verify that a browser can apply. Missing screening answers remain visible so you can resolve them together before a run.

## Workday and universal passwords

The wizard offers three choices: skip password setup, reuse already saved credentials, or save a new shared job-portal password. Existing credentials require an explicit overwrite confirmation. Reusing a saved credential does not reveal it.

For a new password:

1. Choose a password dedicated to job portals. Do not reuse your email, banking, or primary password-manager password.
2. Type it into the hidden prompt and confirm it. Use at least 12 characters with uppercase, lowercase, a number, and a symbol.
3. The tool writes it directly to the macOS Keychain using a trusted OS backend, then reads it back in memory to verify the write.
4. The profile stores only service/account references. Passwords are not passed as command-line arguments, written to JSON, printed, or committed.

The two services are `hermes-job-agent-universal` and `hermes-job-agent-workday-universal`, under **your** email account. These are labels, not password values. No credentials from the repository owner are bundled or copied.

This is **credential storage/reference setup**, not a new automatic portal-login executor. The browser agent must follow the profile-based instructions in the vendored application and Workday skills. In an authorized login process, `onboarding_credentials.credential_reference(profile, "workday")` validates the saved service/account and requires its account to match `contact.email`; it never retrieves a password. Only that login process may read the Keychain value in memory and type it directly into the verified employer page. After changing your application email, configure credentials for the new account; old references will not validate. No real portal login is established by the offline tests.

A universal password is a convenience option, not a security recommendation. Reuse increases the impact of one employer's breach. Prefer unique tenant credentials where supported. Employers can have different password rules and separate Workday accounts; one password is not universal single sign-on. This setup does not change passwords on existing employer accounts or start a reset. A verified tenant-specific credential should take precedence over a shared creation credential.

If macOS Keychain is unavailable or a write cannot be verified, the tool reports the failure without exposing the password. There is no plaintext fallback. You can still save the questionnaire and configure credentials later.

## How applications consume the answers

`QuestionAnswerEngine` and the canonical resolver read the same local profile used by application preparation:

- `application_facts.us_citizen`, `needs_opt`, `needs_cpt`, `sponsorship_now`, and `sponsorship_future` are distinct facts.
- `application_facts.has_company_affiliations` and `restrictive_covenant` are explicit general disclosures.
- `company_disclosures` contains records keyed by exact company, including `current_employee`, `former_employee`, and `relatives_employed`.
- `application_facts.available_start_date` and `full_time_start_date` preserve separate availability dates.
- Existing contact, education, resume, preference, and screening keys remain usable.

The wizard migrates legacy combined sponsorship fields to separate timeframes so “No now / Yes later” stays truthful. Known equivalent prompts reuse the saved facts; differently scoped questions stay unknown. For example, “Do you need OPT?” does not answer “Are you currently on OPT?” or “Are you eligible for STEM OPT?”

The application still has to select a real option from the employer's form and verify that it saved. Having an answer does not bypass review, CAPTCHA, identity checks, assessments, or submission policy. No questionnaire can safely pre-answer every future legal question.

## For contributors

Keep questionnaire facts connected to actual resolver and review code, not just a JSON form. Test absent and conflicting facts as well as Yes/No, and keep company disclosures scoped. Exercise the wizard with synthetic data only:

```bash
python run_offline_tests.py tests/test_onboarding.py tests/test_onboarding_answers.py tests/test_onboarding_credentials.py -q
```

Credential tests use an injected in-memory backend; they do not touch a real Keychain, change a portal account, or establish live login success.
