from __future__ import annotations

from dataclasses import dataclass


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
        profile_answer, profile_reason = self._profile_answer(question_key, question=question)
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
        lowered = question.casefold()
        if "graduation" in lowered:
            return "graduation_season"
        if "hear" in lowered and "about" in lowered:
            return "how_did_you_hear"
        if "start" in lowered and "month" in lowered:
            return "experience_start_month"
        return "unknown"

    def _profile_answer(self, question_key: str, *, question: str) -> tuple[str | None, str | None]:
        if question_key == "graduation_season":
            return self.profile.get("education", {}).get("graduation_season"), None
        if question_key == "experience_start_month":
            start = self._experience_start_value(question)
            if not start:
                return None, "unknown_profile_fact"
            month = self._month_from_date(start)
            if month is None:
                return None, "unknown_profile_fact"
            return month, None
        return None, None

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
        normalized_question = question.casefold()
        for experience in self.profile.get("experience", []):
            company = str(experience.get("company", ""))
            aliases = {company.casefold(), self._company_acronym(company).casefold()}
            if any(alias and alias in normalized_question for alias in aliases):
                start = experience.get("start")
                if start:
                    return str(start)
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
