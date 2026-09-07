from __future__ import annotations

from dataclasses import dataclass
from canonical_answers import CanonicalAnswerError, resolve_fact


@dataclass(frozen=True)
class AnswerResult:
    status: str
    answer: str | None = None
    source: str | None = None
    question_key: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class SourceResolution:
    answer: str | None = None
    source: str | None = None
    reason: str | None = None


class QuestionAnswerEngine:
    def __init__(self, *, profile: dict, google_doc_answers: list[dict] | None = None):
        self.profile = profile
        self.google_doc_answers = list(google_doc_answers or [])

    def answer(self, question: str, *, company: str | None = None) -> AnswerResult:
        question_key = self._question_key(question)
        if question_key == 'unknown':
            return AnswerResult(status='unknown', question_key=question_key, reason='unknown_question')
        profile_answer, profile_reason = self._profile_answer(question_key, question=question)
        if profile_reason == 'conflicting_profile_fact':
            return AnswerResult(status='conflict', question_key=question_key, reason=profile_reason)
        if profile_answer is None and question_key not in ('how_did_you_hear', 'social_media_source'):
            return AnswerResult(status='unknown', question_key=question_key, reason=profile_reason or 'unknown_profile_fact')
        google_doc_resolution = self._google_doc_answer(question_key, company=company)
        if profile_answer is not None:
            return AnswerResult(
                status="answered",
                answer=profile_answer,
                source="profile",
                question_key=question_key,
            )
        if google_doc_resolution.reason is not None:
            return AnswerResult(status="conflict", question_key=question_key, reason=google_doc_resolution.reason)
        if google_doc_resolution.answer is not None:
            return AnswerResult(
                status="answered",
                answer=google_doc_resolution.answer,
                source=google_doc_resolution.source,
                question_key=question_key,
            )
        return AnswerResult(status="unknown", question_key=question_key, reason=profile_reason or "unknown_question")

    def _normalize_company(self, company: str | None) -> str:
        return (company or "").strip().casefold()

    def _question_key(self, question: str) -> str:
        lowered = ' '.join(question.casefold().strip().rstrip('?*').split())
        ordinary = {
            'what is your gpa': 'gpa', 'what degree are you pursuing': 'degree',
            'what is your major': 'discipline', 'what university do you attend': 'school',
            'name of school': 'school',
            'are you legally authorized to work in the united states': 'work_authorization',
            'will you now or will you in the future require employment visa sponsorship': 'sponsorship_now_or_future',
            'will you now or in the future require sponsorship': 'sponsorship_now_or_future',
            'do you now, or will you in the future, need sponsorship from an employer in order to obtain, extend or renew your authorization to work in the united states': 'sponsorship_now_or_future',
            'are you 18 years of age or older': 'is_18_or_older',
            'are you willing to relocate': 'willing_to_relocate',
            'do you have outside business activities': 'outside_business_activities',
            'what is your gender': 'gender', 'what is your race/ethnicity': 'race',
            'what is your veteran status': 'veteran', 'what is your disability status': 'disability',
            'which social media source': 'social_media_source', 'what is your desired salary': 'desired_salary',
            'are you authorized to work in the us': 'work_authorization',
            'are you legally authorized to work in the u.s.': 'work_authorization',
            'will you require sponsorship': 'sponsorship_future', 'do you require visa sponsorship': 'sponsorship_now',
            'are you at least 18 years old': 'is_18_or_older',
            'are you willing to relocate for this role': 'willing_to_relocate',
            'cumulative gpa': 'gpa', 'current degree': 'current_degree',
            'gender': 'gender', 'disability status': 'disability',
        }
        if lowered in ordinary:
            return ordinary[lowered]
        if lowered in ('what is your expected graduation date', 'what is your expected graduation season'):
            return "graduation_season"
        if "hear" in lowered and "about" in lowered:
            return "how_did_you_hear"
        if lowered.startswith("what month did you start at "):
            return "experience_start_month"
        return "unknown"

    def _profile_answer(self, question_key: str, *, question: str) -> tuple[str | None, str | None]:
        if question_key == "experience_start_month":
            start = self._experience_start_value(question)
            if not start:
                return None, "unknown_profile_fact"
            month = self._month_from_date(start)
            if month is None:
                return None, "unknown_profile_fact"
            return month, None
        try:
            return str(resolve_fact(self.profile, question_key)), None
        except CanonicalAnswerError as exc:
            return None, 'conflicting_profile_fact' if 'conflicting' in str(exc) or 'malformed' in str(exc) else 'unknown_profile_fact'

    def _google_doc_answer(self, question_key: str, *, company: str | None = None) -> SourceResolution:
        normalized_company = self._normalize_company(company)
        company_matches: list[str] = []
        generic_matches: list[str] = []
        for entry in self.google_doc_answers:
            if entry.get("question_key") != question_key:
                continue
            answer = entry.get("answer")
            if not answer:
                continue
            entry_company = self._normalize_company(entry.get("company"))
            if entry_company:
                if entry_company == normalized_company:
                    company_matches.append(str(answer))
            else:
                generic_matches.append(str(answer))
        if company_matches:
            if len(set(company_matches)) > 1:
                return SourceResolution(reason="conflicting_google_doc_answers")
            return SourceResolution(answer=company_matches[0], source="google_doc:company")
        if generic_matches:
            if len(set(generic_matches)) > 1:
                return SourceResolution(reason="conflicting_google_doc_answers")
            return SourceResolution(answer=generic_matches[0], source="google_doc")
        return SourceResolution()

    def _experience_start_value(self, question: str) -> str | None:
        normalized_question = ' '.join(question.casefold().strip().rstrip('?*').split())
        employer = normalized_question.removeprefix('what month did you start at ')
        matches = []
        for experience in self.profile.get("experience", []):
            company = str(experience.get("company", ""))
            aliases = {' '.join(company.casefold().split()), self._company_acronym(company).casefold()}
            if employer and employer in aliases:
                matches.append(experience)
        if len(matches) == 1 and matches[0].get("start"):
            return str(matches[0]["start"])
        return None

    def _company_acronym(self, company: str) -> str:
        letters = [word[0] for word in company.split() if word and word[0].isalnum()]
        return "".join(letters)

    def _month_from_date(self, value: str) -> str | None:
        parts = value.split("-")
        if len(parts) < 2 or not parts[1].isdigit():
            return None
        month_number = int(parts[1])
        month_names = {
            1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December",
        }
        return month_names.get(month_number)
