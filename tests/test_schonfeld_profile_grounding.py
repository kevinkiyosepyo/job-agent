"""Canonical accepted-profile comparisons independent of mutable answers."""
import pytest
import schonfeld_form


def profile():
    return {"name":{"first":"Fixture","last":"Person"},"contact":{"email":"fixture@example.test","phone":"555-0100"},
        "education":{"university":"University of California, San Diego","degree":"Bachelor of Science","major":"Data Science","gpa":3.236,"expected_graduation":"2028"},
        "work_authorization":True,"requires_sponsorship":False,
        "application_facts":{"education_start_month":"September","education_start_year":"2024","education_end_month":"May"}}


def answers():
    return {"first_name":"Fixture","last_name":"Person","email":"fixture@example.test","phone":"5550100","gpa":"3.236",
        "school":{"exact_option":"University of California - San Diego"},"degree":{"exact_option":"Bachelor's Degree"},
        "discipline":{"exact_option":"Other"},"current_degree":{"exact_option":"Bachelor's"},
        "education_end_year":"2028","work_authorization":{"exact_option":"Yes"},"sponsorship_now":{"exact_option":"No"},
        "sponsorship_future":{"exact_option":"No"},"education_start_month":{"exact_option":"September"},"education_start_year":"2024","education_end_month":{"exact_option":"May"}}


def test_profile_grounding_is_independent_of_answers():
    assert hasattr(schonfeld_form,'verify_profile_answers'), 'canonical profile comparisons missing'
    schonfeld_form.verify_profile_answers(profile(),answers())
    changed=answers();changed['gpa']='3.8'
    with pytest.raises(ValueError,match='canonical profile'):
        schonfeld_form.verify_profile_answers(profile(),changed)
    missing=profile();missing.pop('application_facts')
    with pytest.raises(ValueError,match='canonical profile'):
        schonfeld_form.verify_profile_answers(missing,answers())
