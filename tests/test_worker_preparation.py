"""Local Node DOM fixtures only: no Chrome, browser launch, sockets, or network."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from worker_operator import WorkerTransport

URL = 'https://job-boards.greenhouse.io/fixture/jobs/123'

NODE_DOM = r'''
const readline = require('readline');
const {File} = require('node:buffer');
const crypto = require('node:crypto').webcrypto;
class DataTransfer { constructor() { this.files=[]; this.items={add:f=>this.files.push(f)}; } }
let nodes = [], events = [];
class Element {
 constructor(spec) { Object.assign(this, {tagName:'INPUT',type:'text',id:'',name:'',disabled:false,readOnly:false,visible:true,attrs:{},options:[],labels:[]}, spec); this._value = spec.value || ''; }
 getAttribute(k) { return this.attrs[k] ?? null; }
 hasAttribute(k) { return this.getAttribute(k) !== null; }
 getClientRects() { return this.visible ? [{}] : []; }
 getBoundingClientRect() { return {left:nodes.indexOf(this)*20+1,top:1,width:10,height:10}; }
 contains(e) { return e === this || this.children?.includes(e.id); }
 closest(s) { return s === '.select__control' && this.control ? document.getElementById(this.control) : null; }
 matches(s) { return false; }
 querySelectorAll(s) {
  return nodes.filter(n=>this.children?.includes(n.id)).filter(n=>
   s === '[role="option"]' ? n.attrs.role === 'option' :
   s === '.select__single-value' ? n.selectedChip === true :
   s === 'input[role="combobox"]' ? n.attrs.role === 'combobox' : false);
 }
 querySelector(s) { return this.querySelectorAll(s)[0] || null; }
 dispatchEvent(e) {
  events.push([this.id,e.type]);
  if (this.openFor && e.type==='click') document.getElementById(this.openFor).attrs['aria-expanded']='true';
  if (this.selectFor && e.type==='click') {
   const input=document.getElementById(this.selectFor);
   input._value=''; input.attrs['aria-expanded']='false';
   const control=document.getElementById(input.control);
   for (const n of control.querySelectorAll('.select__single-value')) n.innerText=this.innerText;
  }
  return true;
 }
 focus() { throw Error('fixture prohibits focus takeover'); }
 blur() { throw Error('fixture prohibits focus takeover'); }
 scrollIntoView() { throw Error('fixture prohibits scroll'); }
}
class HTMLInputElement extends Element {
 get value() { return this._value; } set value(v) { this._value=String(v); }
 get files() { return this._files || []; } set files(v) { this._files=v; }
}
class HTMLTextAreaElement extends HTMLInputElement {}
class HTMLSelectElement extends Element {
 get value() { return this._value; }
 set value(v) { this._value=String(v); for(const o of this.options) o.selected=o.value===v; }
 get selectedOptions() { return this.options.filter(o=>o.selected); }
}
const document = {
 querySelectorAll(s) {
  if (s === 'input,select,textarea,[role="combobox"]') return nodes;
  if (s === 'input[id],select[id]') return nodes.filter(n=>['INPUT','SELECT'].includes(n.tagName) && n.id);
  if (s === '[role="dialog"],[aria-modal="true"],input[type="password"]') return nodes.filter(n=>n.attrs.role==='dialog' || n.attrs['aria-modal']==='true' || n.type==='password');
  if (s === '[role="option"]') return nodes.filter(n=>n.attrs.role === 'option');
  if (s.startsWith('[id=')) { const id=JSON.parse(s.slice(4,-1)); return nodes.filter(n=>n.id===id); }
  return nodes.filter(n => s === '#' + n.id || s === '[id^="school--"]' && n.id.startsWith('school--'));
 },
 querySelector(s) { return this.querySelectorAll(s)[0] || null; },
 getElementById(id) { return nodes.find(n=>n.id===id) || null; },
 elementFromPoint(x,y) { return nodes[Math.floor(x/20)] || null; }
};
const window = {devicePixelRatio:2};
const location = {href: ''};
const getComputedStyle = e => ({display:e.visible?'block':'none',visibility:'visible',opacity:'1'});
class Event { constructor(type,options) { this.type=type; Object.assign(this,options); } }
class InputEvent extends Event {}
class MouseEvent extends Event {}
readline.createInterface({input:process.stdin}).on('line', async line => {
 try {
  const request=JSON.parse(line);
  if (request.configure) {
   location.href=request.url;
   nodes=request.configure.map(spec=>new (spec.tagName==='SELECT'?HTMLSelectElement:HTMLInputElement)(spec)); events=[];
   console.log(JSON.stringify({ok:true})); return;
  }
  if (request.state) { console.log(JSON.stringify({nodes:nodes.map(n=>({id:n.id,value:n.value,...(n.files?.length?{files:n.files.map(f=>({name:f.name,size:f.size}))}:{})})),events})); return; }
  const value=await eval(request.expression);
  console.log(JSON.stringify({result:{value}}));
 } catch(e) { console.log(JSON.stringify({exceptionDetails:{text:e.message}})); }
});
'''


class NodeWorker:
    """Emulates the inspected worker envelope while executing real adapter JS."""
    def __init__(self, controls, url=URL):
        self.url = url
        self.requests = []
        self.process = subprocess.Popen(['node', '-e', NODE_DOM], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert self.process.stdin is not None and self.process.stdout is not None and self.process.stderr is not None
        self.exchange({'configure': controls, 'url': url})

    def exchange(self, data):
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write(json.dumps(data) + '\n')
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        assert line, 'local Node fixture stopped unexpectedly'
        return json.loads(line)

    def request(self, payload):
        self.requests.append(payload)
        if payload['action'] == 'list':
            return [{'targetId':'target-1','url':self.url,'type':'page'}]
        assert payload['action'] == 'call'
        assert payload['method'] == 'Runtime.evaluate'
        assert payload['params']['returnByValue'] is True
        return {'binding': {'targetId':'target-1','url':self.url},
                'result': self.exchange({'expression':payload['params']['expression']})}

    def state(self):
        return self.exchange({'state':True})

    def close(self):
        assert self.process.stdin is not None and self.process.stdout is not None and self.process.stderr is not None
        self.process.stdin.close()
        self.process.wait(timeout=3)
        assert self.process.returncode == 0, self.process.stderr.read()
        self.process.stdout.close()
        self.process.stderr.close()


@pytest.fixture
def worker():
    peers=[]
    def create(controls, url=URL):
        peer=NodeWorker(controls, url)
        peers.append(peer)
        return peer
    yield create
    for peer in peers:
        peer.close()


def test_explicit_worker_preparation_replaces_without_append_or_focus(worker):
    peer=worker([{'id':'first_name','value':'OldOld'}])
    transport=WorkerTransport(peer, target={'id':'target-1','url':URL}, allow_mutation=True)
    with transport.bind_mutable_page_target('target-1') as page:
        page.replace_text('#first_name','Fixture')
        assert page.read_value('#first_name') == 'Fixture'
    assert peer.state() == {'nodes':[{'id':'first_name','value':'Fixture'}],
                            'events':[['first_name','input'],['first_name','change']]}


def test_duplicate_selector_blocks_before_any_mutation(worker):
    peer=worker([{'id':'first_name','value':'One'}, {'id':'first_name','value':'Two'}])
    page=WorkerTransport(peer, target={'id':'target-1','url':URL}, allow_mutation=True).bind_mutable_page_target('target-1')
    with pytest.raises(ValueError):
        page.replace_text('#first_name','Fixture')
    assert peer.state()['events'] == []
    assert [n['value'] for n in peer.state()['nodes']] == ['One','Two']


def test_worker_mutation_rejects_selectors_outside_learned_step(worker):
    peer=worker([{'id':'unlearned','value':'Preserved'}])
    page=WorkerTransport(peer, target={'id':'target-1','url':URL}, allow_mutation=True).bind_mutable_page_target('target-1')
    before=len(peer.requests)
    with pytest.raises(ValueError, match='learned'):
        page.replace_text('#unlearned','Wrong')
    assert len(peer.requests) == before
    assert peer.state()['events'] == []


@pytest.mark.parametrize('kwargs', [
    {'allow_mutation':'yes'}, {'allow_mutation':1},
    {'allow_mutation':True,'confirmation_context':{}},
    {'allow_mutation':True,'preparation_step':'unlearned'},
])
def test_invalid_mutation_authority_is_rejected_before_worker_access(worker, kwargs):
    peer=worker([])
    with pytest.raises(ValueError):
        WorkerTransport(peer, target={'id':'target-1','url':URL}, **kwargs).bind_mutable_page_target('target-1')
    assert peer.requests == []


@pytest.mark.parametrize('spec', [
    {'type':'password'}, {'type':'hidden'}, {'type':'checkbox'},
    {'attrs':{'role':'combobox'}}, {'attrs':{'autocomplete':'one-time-code'}},
    {'attrs':{'aria-label':'I consent to data processing'}},
    {'readOnly':True}, {'attrs':{'aria-disabled':'true'}},
])
def test_protected_or_wrong_typed_control_never_receives_text(worker, spec):
    peer=worker([{'id':'first_name','value':'Preserved',**spec}])
    page=WorkerTransport(peer, target={'id':'target-1','url':URL}, allow_mutation=True).bind_mutable_page_target('target-1')
    with pytest.raises(ValueError):
        page.replace_text('#first_name','Wrong')
    assert peer.state()['events'] == []
    assert peer.state()['nodes'][0]['value'] == 'Preserved'


def test_native_select_binds_exact_option_and_reads_back(worker):
    peer=worker([{'id':'authorization','tagName':'SELECT','value':'',
                  'options':[{'value':'yes','label':'Yes'},{'value':'no','label':'No'}]}])
    page=WorkerTransport(peer, target={'id':'target-1','url':URL}, allow_mutation=True).bind_mutable_page_target('target-1')
    page.select_option('#authorization','yes')
    assert page.read_selected_option('#authorization') == 'yes'
    assert peer.state()['events'] == [['authorization','input'],['authorization','change']]


def react_controls():
    return [
        {'id':'country','attrs':{'role':'combobox','aria-controls':'country-list','aria-expanded':'false'}, 'control':'country-control'},
        {'id':'country-control','tagName':'DIV','openFor':'country','children':['country','country-chip']},
        {'id':'country-chip','tagName':'DIV','selectedChip':True,'innerText':'Old'},
        {'id':'country-list','tagName':'DIV','attrs':{'role':'listbox'},'children':['right-option']},
        {'id':'wrong-option','tagName':'DIV','attrs':{'role':'option'},'innerText':'United States','selectFor':'other'},
        {'id':'right-option','tagName':'DIV','attrs':{'role':'option'},'innerText':'United States','selectFor':'country'},
    ]


def test_react_select_uses_only_the_targets_owned_listbox(worker):
    url='https://job-boards.greenhouse.io/c3ascend/jobs/123'
    peer=worker(react_controls(), url)
    page=WorkerTransport(peer, target={'id':'target-1','url':url}, allow_mutation=True).bind_mutable_page_target('target-1')
    page.react_select_exact('#country','United','United States')
    assert page.read_react_selected_option('#country') == 'United States'
    assert ['right-option','click'] in peer.state()['events']
    assert not any(event[0]=='wrong-option' for event in peer.state()['events'])


def test_repeated_education_blocks_reject_even_an_exact_contact_selector(worker):
    peer=worker([{'id':'first_name'}, {'id':'school--0'}, {'id':'school--1'}])
    page=WorkerTransport(peer, target={'id':'target-1','url':URL}, allow_mutation=True).bind_mutable_page_target('target-1')
    with pytest.raises(ValueError):
        page.replace_text('#first_name','Fixture')
    assert peer.state()['events'] == []


def test_worker_upload_chunks_exact_resume_bytes_without_session_handles(worker, tmp_path):
    import hashlib
    import browser_actions
    content=b'%PDF-1.7\n' + bytes(range(256))*300
    resume=tmp_path/'Fixture Resume.pdf'
    resume.write_bytes(content)
    peer=worker([{'id':'resume','type':'file','visible':False}])
    page=WorkerTransport(peer, target={'id':'target-1','url':URL}, allow_mutation=True,
                         approved_upload_path=str(resume)).bind_mutable_page_target('target-1')
    result=browser_actions.cdp_upload(page,'#resume',str(resume))
    assert result['verified'] is True
    assert page.read_uploaded_sha256('#resume') == hashlib.sha256(content).hexdigest()
    assert peer.state()['nodes'][0]['files'] == [{'name':resume.name,'size':len(content)}]
    assert peer.state()['events'] == [['resume','input'],['resume','change']]
    assert all(len(json.dumps(request).encode()) < 65536 for request in peer.requests)
    assert not any(request.get('method','').startswith('DOM.') for request in peer.requests)


def test_same_filename_different_bytes_is_replaced_then_preserved_by_digest(worker, tmp_path):
    import browser_actions
    resume=tmp_path/'Resume.pdf'
    resume.write_bytes(b'%PDF-1.7\nApproved content')
    peer=worker([{'id':'resume','type':'file'}])
    peer.exchange({'expression':"document.querySelector('#resume').files=[new File(['wrong'],'Resume.pdf')]"})
    page=WorkerTransport(peer, target={'id':'target-1','url':URL}, allow_mutation=True,
                         approved_upload_path=str(resume)).bind_mutable_page_target('target-1')
    assert browser_actions.cdp_upload(page,'#resume',str(resume))['verified'] is True
    assert peer.state()['events'] == [['resume','input'],['resume','change']]
    assert browser_actions.cdp_upload(page,'#resume',str(resume))['verified'] is True
    assert peer.state()['events'] == [['resume','input'],['resume','change']]


def test_active_consent_dialog_blocks_unrelated_text_mutation(worker):
    peer=worker([{'id':'first_name'}, {'id':'consent-modal','tagName':'DIV','attrs':{'role':'dialog'}}])
    page=WorkerTransport(peer, target={'id':'target-1','url':URL}, allow_mutation=True).bind_mutable_page_target('target-1')
    with pytest.raises(ValueError):
        page.replace_text('#first_name','Fixture')
    assert peer.state()['events'] == []


@pytest.mark.parametrize('operation,args', [('click_submit_once',('#submit',)), ('set_checked',('#privacy',True))])
def test_preparation_optin_never_authorizes_submit_or_active_consent(worker, operation, args):
    peer=worker([])
    page=WorkerTransport(peer, target={'id':'target-1','url':URL}, allow_mutation=True).bind_mutable_page_target('target-1')
    before=len(peer.requests)
    with pytest.raises(ValueError, match='preparation'):
        getattr(page,operation)(*args)
    assert len(peer.requests) == before
    assert not getattr(page,'_submit_attempted',False)


def test_learned_consent_semantic_is_prohibited_without_any_page_request(worker):
    url='https://job-boards.greenhouse.io/c3ascend/jobs/123'
    peer=worker([],url)
    page=WorkerTransport(peer, target={'id':'target-1','url':url}, allow_mutation=True).bind_mutable_page_target('target-1')
    before=len(peer.requests)
    with pytest.raises(ValueError, match='consent'):
        page.react_select_exact('#question_37929971002','Yes','Yes')
    assert len(peer.requests) == before


def test_missing_native_upload_api_reports_unsupported_without_assignment(worker, tmp_path):
    resume=tmp_path/'Resume.pdf'
    resume.write_bytes(b'%PDF-1.7\nOffline')
    peer=worker([{'id':'resume','type':'file'}])
    peer.exchange({'expression':'DataTransfer = undefined; true'})
    page=WorkerTransport(peer, target={'id':'target-1','url':URL}, allow_mutation=True,
                         approved_upload_path=str(resume)).bind_mutable_page_target('target-1')
    with pytest.raises(ValueError, match='unsupported'):
        page.cdp_upload('#resume',str(resume))
    assert peer.state()['events'] == []


@pytest.mark.parametrize('digest_number', [1,2])
def test_upload_rechecks_active_gate_after_async_digest_before_assignment(worker, tmp_path, digest_number):
    resume=tmp_path/'Resume.pdf'
    resume.write_bytes(b'%PDF-1.7\nOffline')
    peer=worker([{'id':'resume','type':'file'}])
    peer.exchange({'expression': '''const digest = crypto.subtle.digest.bind(crypto.subtle); let count=0;
        crypto.subtle.digest = async (...args) => {
            const value = await digest(...args);
            if (++count === NUMBER) nodes.push(new Element({id:'security-dialog',tagName:'DIV',attrs:{role:'dialog'}}));
            return value;
        }; true'''.replace('NUMBER',str(digest_number))})
    page=WorkerTransport(peer, target={'id':'target-1','url':URL}, allow_mutation=True,
                         approved_upload_path=str(resume)).bind_mutable_page_target('target-1')
    with pytest.raises(ValueError):
        page.cdp_upload('#resume',str(resume))
    if digest_number == 1:
        assert 'files' not in peer.state()['nodes'][0]
    assert peer.state()['events'] == []


def test_worker_rejects_oversized_json_before_sending_it(worker):
    from worker_operator import WorkerConnection
    peer=worker([])
    connection=WorkerConnection(peer, {'id':'target-1','url':URL})
    with pytest.raises(ValueError, match='readline'):
        connection.call('Runtime.evaluate',{'expression':json.dumps('x'*65536),'returnByValue':True})
    assert peer.requests == []


@pytest.mark.parametrize('options', [[], [{'value':'yes','disabled':True}], [{'value':'yes'},{'value':'yes'}]])
def test_missing_disabled_or_duplicate_native_option_has_no_side_effects(worker, options):
    peer=worker([{'id':'authorization','tagName':'SELECT','options':options}])
    page=WorkerTransport(peer,target={'id':'target-1','url':URL},allow_mutation=True).bind_mutable_page_target('target-1')
    with pytest.raises(ValueError):
        page.select_option('#authorization','yes')
    assert peer.state()['events'] == []


@pytest.mark.parametrize('mode', ['duplicate','disabled','unowned'])
def test_invalid_target_listbox_never_clicks_an_option(worker, mode):
    url='https://job-boards.greenhouse.io/c3ascend/jobs/123'
    controls=react_controls()
    if mode=='duplicate':
        controls.append({**controls[-1], 'id':'duplicate'})
        controls[3]['children'].append('duplicate')
    elif mode=='disabled':
        controls[-1]['attrs']['aria-disabled']='true'
    else:
        controls[0]['attrs'].pop('aria-controls')
    peer=worker(controls,url)
    page=WorkerTransport(peer,target={'id':'target-1','url':url},allow_mutation=True).bind_mutable_page_target('target-1')
    with pytest.raises(ValueError):
        page.react_select_exact('#country','United','United States')
    assert not any(event[0] in {'right-option','wrong-option','duplicate'} for event in peer.state()['events'])


@pytest.mark.parametrize('mode', ['tamper','replace'])
def test_upload_chunk_drift_never_assigns_files_and_cleans_private_buffer(worker, tmp_path, mode):
    resume=tmp_path/'Resume.pdf'
    resume.write_bytes(b'%PDF-1.7\nOffline')
    peer=worker([{'id':'resume','type':'file'}])
    original=peer.request
    def intercepted(payload):
        result=original(payload)
        if 'state.chunks.push' in payload.get('params',{}).get('expression',''):
            expression=("window[Object.getOwnPropertyNames(window).find(k=>k.startsWith('__worker_upload_'))].chunks[0][0] ^= 1"
                        if mode=='tamper' else "nodes[0]=new HTMLInputElement({id:'resume',type:'file'})")
            peer.exchange({'expression':expression})
        return result
    peer.request=intercepted
    page=WorkerTransport(peer,target={'id':'target-1','url':URL},allow_mutation=True,
                         approved_upload_path=str(resume)).bind_mutable_page_target('target-1')
    with pytest.raises(ValueError):
        page.cdp_upload('#resume',str(resume))
    assert peer.state()['events'] == []
    assert 'files' not in peer.state()['nodes'][0]
    assert peer.exchange({'expression':"Object.getOwnPropertyNames(window).filter(k=>k.startsWith('__worker_upload_'))"})['result']['value'] == []


def test_confirmation_transport_rejects_mutation_before_request(worker):
    from worker_operator import WorkerConnection
    peer=worker([])
    connection=WorkerConnection(peer,{'id':'target-1','url':URL},observation_only=True)
    with pytest.raises(ValueError,match='observation-only'):
        connection.call('Runtime.evaluate',{'expression':"document.querySelector('#first_name').value='No'",'returnByValue':True})
    assert peer.requests == []


def test_opted_in_transport_still_binds_readonly_page_for_observation(worker):
    peer=worker([])
    transport=WorkerTransport(peer,target={'id':'target-1','url':URL},allow_mutation=True)
    assert transport.bind_page_target('target-1').requires_upload_digest is False


def test_approved_upload_still_rejects_non_pdf_bytes_before_page_access(worker, tmp_path):
    resume=tmp_path/'Resume.pdf'
    resume.write_bytes(b'not a PDF')
    peer=worker([{'id':'resume','type':'file'}])
    page=WorkerTransport(peer,target={'id':'target-1','url':URL},allow_mutation=True,
                         approved_upload_path=str(resume)).bind_mutable_page_target('target-1')
    before=len(peer.requests)
    with pytest.raises(ValueError,match='PDF'):
        page.cdp_upload('#resume',str(resume))
    assert len(peer.requests)==before
