"""Dataclass-based job application data model."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict, is_dataclass
from datetime import UTC, date, datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence


PROFILE_ID_METADATA_KEY = "profile_id"


def _utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""

    return datetime.now(UTC)


@dataclass(slots=True)
class MailingAddress:
    """Structured representation of a postal address."""

    street: Optional[str] = None
    city: Optional[str] = None
    state_or_region: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


@dataclass(slots=True)
class OnlineProfile:
    """External profile or portfolio link."""

    label: str
    url: str


@dataclass(slots=True)
class SalaryExpectation:
    """Desired compensation range and currency."""

    minimum: Optional[float] = None
    maximum: Optional[float] = None
    currency: Optional[str] = None
    period: str = "year"


@dataclass(slots=True)
class Certification:
    """Professional certification or license."""

    name: str
    authority: Optional[str] = None
    obtained_date: Optional[date] = None
    expiration_date: Optional[date] = None


@dataclass(slots=True)
class EducationEntry:
    """Formal education record."""

    institution: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    minor: Optional[str] = None
    graduation_date: Optional[date] = None
    gpa: Optional[float] = None
    honors: Optional[str] = None
    ongoing: bool = False
    certifications: List[Certification] = field(default_factory=list)


@dataclass(slots=True)
class WorkExperienceEntry:
    """Professional experience entry."""

    company: str
    title: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: bool = False
    location: Optional[str] = None
    responsibilities: List[str] = field(default_factory=list)
    achievements: List[str] = field(default_factory=list)
    manager_name: Optional[str] = None
    manager_contact: Optional[str] = None
    can_contact_manager: Optional[bool] = None
    reason_for_leaving: Optional[str] = None


@dataclass(slots=True)
class SkillsProfile:
    """Aggregated skills and competencies."""

    technical_skills: List[str] = field(default_factory=list)
    soft_skills: List[str] = field(default_factory=list)
    languages: Mapping[str, str] = field(default_factory=dict)
    tools_and_platforms: List[str] = field(default_factory=list)
    leadership_experience: Optional[str] = None
    certifications: List[Certification] = field(default_factory=list)


@dataclass(slots=True)
class ReferenceContact:
    """Professional reference contact."""

    full_name: str
    relationship: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    permission_to_contact: Optional[bool] = None


@dataclass(slots=True)
class PortfolioAssets:
    """Supporting materials and links."""

    resume_url: Optional[str] = None
    cover_letter_url: Optional[str] = None
    portfolio_urls: List[str] = field(default_factory=list)
    code_repositories: List[str] = field(default_factory=list)
    design_portfolios: List[str] = field(default_factory=list)
    additional_documents: List[str] = field(default_factory=list)


@dataclass(slots=True)
class LegalAndCompliance:
    """Employment eligibility and compliance disclosures."""

    eligible_to_work: Optional[bool] = None
    requires_sponsorship: Optional[bool] = None
    criminal_history_disclosure: Optional[str] = None
    background_check_consent: Optional[bool] = None
    reference_check_consent: Optional[bool] = None
    gender_identity: Optional[str] = None
    race_ethnicity: Optional[str] = None
    veteran_status: Optional[str] = None
    disability_status: Optional[str] = None


@dataclass(slots=True)
class AvailabilityLogistics:
    """Schedule and location preferences."""

    notice_period: Optional[str] = None
    willing_to_travel: Optional[str] = None
    preferred_time_zone: Optional[str] = None
    interview_availability: Optional[str] = None


@dataclass(slots=True)
class AdditionalInformation:
    """Narrative responses and open feedback."""

    interest_in_role: Optional[str] = None
    interest_in_company: Optional[str] = None
    greatest_achievement: Optional[str] = None
    complex_problem_example: Optional[str] = None
    additional_notes: Optional[str] = None


@dataclass(slots=True)
class OptionalExtras:
    """Advanced optional applicant data."""

    personality_assessments: Mapping[str, str] = field(default_factory=dict)
    preferred_work_style: Optional[str] = None
    career_goals: Optional[str] = None
    diversity_inclusion_feedback: Optional[str] = None
    video_introduction_url: Optional[str] = None


@dataclass(slots=True)
class PersonalInformation:
    """Primary applicant identity information."""

    full_legal_name: str
    contact_email: str
    preferred_name: Optional[str] = None
    pronouns: Optional[str] = None
    date_of_birth: Optional[date] = None
    phone_number: Optional[str] = None
    address: Optional[MailingAddress] = None
    linkedin_url: Optional[str] = None
    personal_website: Optional[str] = None
    technical_profiles: List[OnlineProfile] = field(default_factory=list)
    social_media_profiles: List[OnlineProfile] = field(default_factory=list)


@dataclass(slots=True)
class PositionDetails:
    """Information about the role the applicant is pursuing."""

    position_applied_for: str
    requisition_id: Optional[str] = None
    desired_start_date: Optional[date] = None
    employment_type_preferences: List[str] = field(default_factory=list)
    work_authorization_status: Optional[str] = None
    willingness_to_relocate: Optional[str] = None
    preferred_work_arrangement: Optional[str] = None
    salary_expectation: Optional[SalaryExpectation] = None
    source_of_application: Optional[str] = None


@dataclass(slots=True)
class JobApplication:
    """Top-level job application capture for a candidate."""

    personal_information: PersonalInformation
    position_details: PositionDetails
    highest_education_level: Optional[str] = None
    education_history: List[EducationEntry] = field(default_factory=list)
    ongoing_training_programs: List[str] = field(default_factory=list)
    work_history: List[WorkExperienceEntry] = field(default_factory=list)
    skills_profile: Optional[SkillsProfile] = None
    references: List[ReferenceContact] = field(default_factory=list)
    portfolio: Optional[PortfolioAssets] = None
    legal: Optional[LegalAndCompliance] = None
    availability: Optional[AvailabilityLogistics] = None
    additional_information: Optional[AdditionalInformation] = None
    optional_extras: Optional[OptionalExtras] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)

    def to_payload(self) -> Dict[str, Any]:
        """Serialize the dataclass tree to JSON-friendly primitives."""

        return _serialize_dataclass(self)

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, dict):
            self.metadata = dict(self.metadata)

    @property
    def profile_id(self) -> Optional[str]:
        value = self.metadata.get(PROFILE_ID_METADATA_KEY)
        if value is None:
            return None
        return str(value)

    @profile_id.setter
    def profile_id(self, value: Optional[str]) -> None:
        if value is None:
            self.metadata.pop(PROFILE_ID_METADATA_KEY, None)
        else:
            self.metadata[PROFILE_ID_METADATA_KEY] = value


def _serialize_dataclass(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if is_dataclass(obj):
        result: Dict[str, Any] = {}
        for key, value in asdict(obj).items():
            result[key] = _serialize_dataclass(value)
        return result
    if isinstance(obj, Mapping):
        return {key: _serialize_dataclass(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_serialize_dataclass(item) for item in obj]
    return obj
