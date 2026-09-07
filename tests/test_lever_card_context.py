"""Synthetic reduced Lever card context; no employer or applicant data."""
from lever_handler import inspect_html


def test_generic_option_prompt_retains_separate_scoped_card_heading():
    html = '''<div data-qa="additional-cards"><h4 data-qa="card-name">How did you hear about us?</h4>
      <li class="application-question"><div class="application-label">Select One</div>
        <label><input type="radio" name="source" value="event" required>Company Event</label>
        <label><input type="radio" name="source" value="other" required>Other</label></li></div>'''
    report = inspect_html(html, page_url='https://jobs.lever.co/example/1/apply')
    group = report['choice_groups'][0]
    assert group.get('card_heading') == 'How did you hear about us?'
    assert group['label'] == 'Select One'
    assert [field.get('card_heading') for field in report['fields']] == ['How did you hear about us?'] * 2
    assert group['options'] == [{'label':'Company Event','value':'event','disabled':False}, {'label':'Other','value':'other','disabled':False}]
    assert group['required'] is True
    assert group['bound_values_verified'] is False


def _question(name='one'):
    return f'<li class="application-question"><div class="application-label">Select One</div><label><input type="radio" name="{name}" value="no">No</label></li>'


def test_sibling_cards_do_not_exchange_context_or_merge_prompts():
    html = ''.join('<div data-qa="additional-cards"><h4 data-qa="card-name">'+text+'</h4>'+_question(name)+'</div>'
                   for name, text in [('one','First card'),('two','Second card')])
    report = inspect_html(html, page_url='https://jobs.lever.co/example/1/apply')
    assert [group['card_heading'] for group in report['choice_groups']] == ['First card','Second card']
    assert [group['label'] for group in report['choice_groups']] == ['Select One','Select One']


def test_ambiguous_or_outside_headings_do_not_supply_context():
    for headers in ['<h4 data-qa="card-name">A</h4><h4 data-qa="card-name">B</h4>',
                    '<h4>Unmarked heading</h4>', '<div><h4 data-qa="card-name">Nested</h4></div>',
                    '<h4 data-qa="card-name"> </h4>']:
        html = '<h4 data-qa="card-name">Outside</h4><div data-qa="additional-cards">'+headers+_question()+'</div>'
        report = inspect_html(html, page_url='https://jobs.lever.co/example/1/apply')
        assert 'card_heading' not in report['fields'][0]
        assert 'card_heading' not in report['choice_groups'][0]


def test_context_preserves_inline_punctuation_without_importing_hidden_template_value():
    html = '<div data-qa="additional-cards"><h4 data-qa="card-name">Academic (<b>current</b>) level</h4><input type="hidden" value="Made-up prompt">'+_question()+'</div>'
    report = inspect_html(html, page_url='https://jobs.lever.co/example/1/apply')
    assert report['choice_groups'][0]['card_heading'] == 'Academic (current) level'
    assert report['fields'][0]['type'] == 'hidden'
    assert 'card_heading' not in report['fields'][0]
