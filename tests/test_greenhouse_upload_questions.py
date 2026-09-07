"""Synthetic reduced modern upload wrapper from a public SWE pilot; no real applicant data."""
from prepare_job import prepare_saved_html
from prepare_live_job import _questions_from_fields
from answer_coverage import build_coverage_matrix
from browser_actions import inventory_form_fields
import pytest


@pytest.mark.parametrize('old,new', [
    ('aria-labelledby="upload-label-transcript"','aria-labelledby="missing"'),
    ('aria-labelledby="upload-label-transcript"','aria-labelledby="upload-label-transcript missing"'),
    ('role="group"','role="presentation"'),
    ('class="file-upload"','class="not-file-upload"'),
    ('class="label upload-label"','class="label not-upload-label"'),
    ('id="transcript" class="visually-hidden"','class="visually-hidden"'),
    ('<button type="button">','<input id="other" type="file"><button type="button">'),
    ('<button type="button">','<div id="transcript"></div><button type="button">'),
    ('<button type="button">','<div id="upload-label-transcript"></div><button type="button">'),
    ('Academic Transcript<span class="required">*</span>','<span class="required">*</span>'),
])
def test_ambiguous_or_unsupported_wrapper_retains_raw_inventory(old,new):
    html = HTML.replace(old,new)
    report = prepare_saved_html(html_text=html,page_url=URL)
    assert report['fields'] == inventory_form_fields(html)
    assert report['submission_enabled'] is False


def test_external_label_cannot_be_borrowed_from_another_upload_group():
    label = '<div id="upload-label-transcript" class="label upload-label">Academic Transcript<span class="required">*</span></div>'
    html = label + HTML.replace(label,'')
    assert prepare_saved_html(html_text=html,page_url=URL)['fields'] == inventory_form_fields(html)


def test_nearest_unsupported_upload_group_does_not_fall_through_to_outer_group():
    html = HTML.replace('<div class="file-upload__wrapper">','<div class="file-upload">')
    assert prepare_saved_html(html_text=html,page_url=URL)['fields'] == inventory_form_fields(html)


@pytest.mark.parametrize('required,native,expected', [('false',False,False),('false',True,True),('true',False,True)])
def test_group_requirement_never_clears_native_requirement(required,native,expected):
    html = HTML.replace('aria-required="true"',f'aria-required="{required}"')
    if native:
        html = html.replace('type="file"','type="file" required')
    fields = prepare_saved_html(html_text=html,page_url=URL)['fields']
    assert fields[0]['required'] is expected
    assert fields[0]['label'] == 'Academic Transcript'


def test_adjacent_optional_upload_and_inline_punctuation_remain_separate():
    html = HTML.replace('Academic Transcript','Academic <em>Transcript</em> (PDF)')
    html += HTML.replace('transcript','portfolio').replace('aria-required="true"','aria-required="false"').replace('Academic Transcript','Portfolio')
    fields = prepare_saved_html(html_text=html,page_url=URL)['fields']
    assert fields == [
        {'name':'transcript','type':'file','label':'Academic Transcript (PDF)','required':True},
        {'name':'portfolio','type':'file','label':'Portfolio','required':False}]


def test_required_unverified_upload_blocks_read_only_preparation_review_ready():
    from prepare_live_job import prepare_live_job
    class SyntheticPage:
        target_id = 'synthetic'
        def read_only_snapshot(self):
            return {'target_id':'synthetic','url':URL,'html':HTML,'read_only':True}
    def prepare(**kwargs):
        report = prepare_saved_html(**kwargs)
        return {**report,'questions':_questions_from_fields(report)}
    result = prepare_live_job(page=SyntheticPage(), target_id='synthetic',expected_url=URL,
        expected_identity={'company':'','role':'Software Engineering Intern','requisition':''},
        profile={},prepare=prepare,coverage=build_coverage_matrix)
    assert result['review_ready'] is False
    assert result['applied_answers']['field_evidence'] == []
    assert result['submission_enabled'] is False

URL = 'https://job-boards.greenhouse.io/example/jobs/123'
HTML = '''<h1>Software Engineering Intern</h1>
<div role="group" aria-labelledby="upload-label-transcript" aria-required="true" class="file-upload">
  <div id="upload-label-transcript" class="label upload-label">Academic Transcript<span class="required">*</span></div>
  <div class="file-upload__wrapper"><div>
    <button type="button">Attach</button><label class="visually-hidden" for="transcript">Attach</label>
    <input id="transcript" class="visually-hidden" type="file" accept=".pdf,.doc">
  </div></div>
</div>'''


def test_required_upload_question_reaches_preparation_instead_of_optional_attach():
    report = prepare_saved_html(html_text=HTML,page_url=URL)
    assert report['fields'] == [{'name':'transcript','type':'file','label':'Academic Transcript','required':True}]
    questions = _questions_from_fields(report)
    coverage = build_coverage_matrix(profile={},questions=questions)
    assert [entry['question'] for entry in coverage['human_required']] == ['Academic Transcript']
    assert coverage['known'] == []
    assert coverage['optional_skip'] == []
    assert report['submission_enabled'] is False


def test_specific_control_label_is_preserved_while_group_requirement_still_applies():
    html = HTML.replace('id="transcript" class="visually-hidden"', 'id="transcript" aria-label="Most recent transcript" class="visually-hidden"')
    report = prepare_saved_html(html_text=html,page_url=URL)
    assert report['fields'] == [{'name':'transcript','type':'file','label':'Most recent transcript','required':True}]
