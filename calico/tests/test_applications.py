from __future__ import annotations

from datetime import date

from calico.applications import (
    AdditionalInformation,
    AvailabilityLogistics,
    JobApplication,
    LegalAndCompliance,
    OptionalExtras,
    PersonalInformation,
    PortfolioAssets,
    PositionDetails,
    ReferenceContact,
    SkillsProfile,
    WorkExperienceEntry,
    EducationEntry,
    Certification,
    MailingAddress,
    OnlineProfile,
    SalaryExpectation,
)


def test_job_application_serialization_round_trip() -> None:
    personal = PersonalInformation(
        full_legal_name="Ada Lovelace",
        contact_email="ada@example.com",
        preferred_name="Ada",
        pronouns="she/her",
        phone_number="123-456-7890",
        address=MailingAddress(
            street="123 Analytical Engine Way",
            city="London",
            state_or_region="",
            postal_code="N1 9GU",
            country="UK",
        ),
        linkedin_url="https://linkedin.com/in/ada",
        personal_website="https://ada.dev",
        technical_profiles=[OnlineProfile(label="GitHub", url="https://github.com/ada")],
        social_media_profiles=[OnlineProfile(label="Twitter", url="https://twitter.com/ada")],
    )

    position = PositionDetails(
        position_applied_for="Principal Engineer",
        requisition_id="ENG-001",
        desired_start_date=date(2025, 1, 6),
        employment_type_preferences=["full_time"],
        work_authorization_status="Citizen",
        willingness_to_relocate="Conditional",
        preferred_work_arrangement="Hybrid",
        salary_expectation=SalaryExpectation(minimum=180000, maximum=210000, currency="USD"),
        source_of_application="Referral",
    )

    education = [
        EducationEntry(
            institution="University of Imagination",
            degree="BSc Computer Science",
            field_of_study="Computer Science",
            graduation_date=date(2012, 6, 1),
            gpa=3.9,
            certifications=[
                Certification(name="AWS Solutions Architect", authority="AWS", obtained_date=date(2020, 5, 1)),
            ],
        )
    ]

    work_history = [
        WorkExperienceEntry(
            company="Analytical Machines Ltd",
            title="Lead Developer",
            start_date=date(2015, 1, 1),
            end_date=date(2020, 12, 31),
            location="Remote",
            responsibilities=["Developed computational algorithms"],
            achievements=["Delivered 30% performance improvements"],
            manager_name="Charles Babbage",
            manager_contact="charles@example.com",
            can_contact_manager=True,
            reason_for_leaving="Pursuing new challenges",
        )
    ]

    skills = SkillsProfile(
        technical_skills=["Python", "Distributed Systems"],
        soft_skills=["Leadership", "Communication"],
        languages={"English": "Native", "French": "Conversational"},
        tools_and_platforms=["Kubernetes", "AWS"],
        leadership_experience="Managed cross-functional teams of 10+ engineers",
    )

    references = [
        ReferenceContact(
            full_name="Grace Hopper",
            relationship="Mentor",
            company="Navy",
            title="Rear Admiral",
            email="grace@example.com",
            permission_to_contact=True,
        )
    ]

    portfolio = PortfolioAssets(
        resume_url="https://files.example.com/resume.pdf",
        cover_letter_url="https://files.example.com/cover_letter.pdf",
        portfolio_urls=["https://portfolio.example.com"],
        code_repositories=["https://github.com/ada/project"],
    )

    legal = LegalAndCompliance(
        eligible_to_work=True,
        requires_sponsorship=False,
        criminal_history_disclosure="None",
        background_check_consent=True,
        reference_check_consent=True,
        gender_identity="Woman",
        race_ethnicity="Prefer not to say",
    )

    availability = AvailabilityLogistics(
        notice_period="2 weeks",
        willing_to_travel="Up to 25%",
        preferred_time_zone="Europe/London",
        interview_availability="Weekdays after 3pm GMT",
    )

    additional = AdditionalInformation(
        interest_in_role="Excited about leading innovation",
        interest_in_company="Fond of the mission",
        greatest_achievement="Built the first mechanical algorithm",
        complex_problem_example="Created a scalable architecture for real-time analytics",
        additional_notes="Happy to provide more references",
    )

    extras = OptionalExtras(
        personality_assessments={"MBTI": "INTJ"},
        preferred_work_style="Team",
        career_goals="Drive advancements in computing",
        diversity_inclusion_feedback="Appreciate inclusive culture",
    )

    application = JobApplication(
        personal_information=personal,
        position_details=position,
        highest_education_level="Bachelors",
        education_history=education,
        ongoing_training_programs=["Executive Leadership Program"],
        work_history=work_history,
        skills_profile=skills,
        references=references,
        portfolio=portfolio,
        legal=legal,
        availability=availability,
        additional_information=additional,
        optional_extras=extras,
        metadata={"source": "unit_test"},
    )

    application.profile_id = "default-profile"
    assert application.profile_id == "default-profile"

    payload = application.to_payload()

    assert payload["personal_information"]["full_legal_name"] == "Ada Lovelace"
    assert payload["position_details"]["salary_expectation"]["minimum"] == 180000
    assert payload["education_history"][0]["certifications"][0]["name"] == "AWS Solutions Architect"
    assert payload["work_history"][0]["responsibilities"] == ["Developed computational algorithms"]
    assert payload["skills_profile"]["languages"]["French"] == "Conversational"
    assert payload["references"][0]["permission_to_contact"] is True
    assert payload["portfolio"]["resume_url"] == "https://files.example.com/resume.pdf"
    assert payload["legal"]["eligible_to_work"] is True
    assert payload["availability"]["notice_period"] == "2 weeks"
    assert payload["additional_information"]["complex_problem_example"].startswith("Created a scalable")
    assert payload["optional_extras"]["personality_assessments"]["MBTI"] == "INTJ"
    assert payload["ongoing_training_programs"] == ["Executive Leadership Program"]
    assert payload["metadata"]["source"] == "unit_test"
    assert payload["metadata"]["profile_id"] == "default-profile"
