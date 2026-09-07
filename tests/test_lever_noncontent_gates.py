"""Synthetic regressions; no employer data, browser, or real gate clearance."""
import pytest
from lever_handler import inspect_html

URL = 'https://jobs.lever.co/example/synthetic/apply'
FORM = '<h1>Software Engineer Intern</h1><label for="n">Full name</label><input id="n" name="name" required>'


@pytest.mark.parametrize('non_content', [
    '<style>.g-recaptcha div,.h-captcha-spacing {display:block;}</style>',
    '<script>const captchaId = "synthetic";</script>',
])
def test_script_and_style_text_do_not_establish_static_captcha_gate(non_content):
    result = inspect_html(non_content + FORM, page_url=URL)
    assert result['manual_gate'] is None
    assert result['page_type'] == 'application'
    assert result['fields'] == inspect_html(FORM, page_url=URL)['fields']


@pytest.mark.parametrize('markup', [
    '<style>.g-recaptcha{}</style><p>Please complete CAPTCHA</p>',
    '<p>Please complete hCAPTCHA</p><script>const captchaId = null;</script>',
    '<script>const text = "<style>captcha";</script><p>reCAPTCHA required</p>',
    '</style><p aria-hidden="true">Please complete CAPTCHA</p>',
])
def test_ordinary_challenge_text_is_still_a_static_gate_candidate(markup):
    result = inspect_html(FORM + markup, page_url=URL)
    assert result['manual_gate'] == {'type': 'captcha', 'detail': 'CAPTCHA detected'}


def test_prepare_snapshot_retains_all_non_gate_results_and_submission_disabled():
    from prepare_job import prepare_saved_html
    expected = prepare_saved_html(html_text=FORM, page_url=URL,
                                  expected_resume_basename='Synthetic.pdf')
    result = prepare_saved_html(html_text='<style>.g-recaptcha{}</style>' + FORM,
                                page_url=URL, expected_resume_basename='Synthetic.pdf')
    assert result == expected
    assert result['submission_enabled'] is False
    assert result['uploaded_resume_verified'] is False
    assert result['confirmation_text'] is None
