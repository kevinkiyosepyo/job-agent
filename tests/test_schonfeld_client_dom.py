"""Execute generated JavaScript against a deterministic DOM/React fixture, no Chrome."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import schonfeld_form as form


def evaluate(expression, change=""):
    fixture = r'''
    global.Node=class {};
    global.File=require('node:buffer').File;
    global.crypto=require('node:crypto').webcrypto;
    global.window={innerWidth:100,innerHeight:100,devicePixelRatio:2};
    global.location={href:URL_JSON};
    const controls=CONTROLS_JSON, bySelector={}, nodes=[]; let current=null;
    function node(id,value) {
      return Object.assign(new Node(),{id,value,disabled:false,required:true,type:'text',tagName:'INPUT',validity:{valid:true},
        __reactProps$fixture:{value},getAttribute(n){return n==='role'?this.role||null:null},
        getBoundingClientRect(){current=this;return {left:0,top:0,width:10,height:10,bottom:10,right:10}},
        getClientRects(){return this.hidden?[]:[1]},contains(other){return this===other},
        matches(selector){return bySelector[selector]===this},closest(){return {querySelector:()=>({innerText:this.selected})}}
      });
    }
    for(const [key,[selector,operation]] of Object.entries(controls)) {
      if(key==='resume') continue;
      const e=node(key,key==='phone'?'5550100':'Fixture');
      bySelector[selector]=e;nodes.push(e);
      if(operation==='react_select_exact') {
        e.value='';e.__reactProps$fixture.value='';e.role='combobox';e.selected='Fixture';
        e.__reactFiber$fixture={memoizedProps:{selectProps:{inputId:key,value:{value:'fixture',label:'Fixture'}}},return:null};
      }
    }
    const phone=bySelector['#phone'];
    phone.__reactProps$fixture={};
    phone.__reactFiber$fixture={memoizedProps:{},return:{memoizedProps:{id:'phone',value:'5550100'},return:null}};
    const file=new File(['%PDF-fixture'], 'Resume.pdf', {type:'application/pdf'});
    const name=node('filename','');name.innerText='Resume.pdf';
    const group=node('group','');
    group.querySelectorAll=selector=>selector==='.file-upload__filename p'?[name]:[];
    group.__reactFiber$fixture={memoizedProps:{file},return:null};
    const realForm=node('form',''); realForm.querySelector=selector=>bySelector[selector]||null;
    realForm.querySelectorAll=()=>nodes;
    const submit=node('submit','');submit.tagName='BUTTON';let clicks=0;submit.click=()=>{clicks++};
    const dialogs=[];
    global.document={querySelectorAll(selector){
      if(selector==='form')return [realForm];
      if(selector==='[aria-labelledby="upload-label-resume"]')return [group];
      if(selector===SUBMIT_JSON)return [submit];
      if(selector.includes('[role="dialog"]'))return dialogs;
      return bySelector[selector]?[bySelector[selector]]:[];
    },elementFromPoint:()=>current};
    global.getComputedStyle=e=>({display:e.hidden?'none':'block',visibility:'visible',opacity:'1'});
    '''.replace("URL_JSON", json.dumps(form.URL)).replace("CONTROLS_JSON", json.dumps(form.CONTROLS)).replace("SUBMIT_JSON", json.dumps(form.SUBMIT_SELECTOR))
    program = fixture + change + "\nPromise.resolve(" + expression + ").then(result=>console.log(JSON.stringify(result))).catch(e=>{console.error(e);process.exitCode=1});"
    result = subprocess.run(["node", "-e", program], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def test_phone_uses_exact_ancestor_controlled_binding_not_plain_dom():
    observed = evaluate(form.control_expression("#phone"))
    assert observed["bound"] is True
    assert observed["binding_source"] == "react_phone_ancestor"
    mismatch = evaluate(form.control_expression("#phone"), "phone.__reactFiber$fixture.return.memoizedProps.value='999';")
    assert mismatch["bound"] is False


def test_full_dom_inventory_hashes_actual_file_and_detects_new_required_option():
    observed = evaluate(form.client_form_expression())
    assert observed["resume"]["sha256"] == hashlib.sha256(b'%PDF-fixture').hexdigest()
    assert observed["resume"]["attachment_present"] is True
    assert observed["server_saved"] is False
    assert set(observed["fields"]) == {s for k,(s,_) in form.CONTROLS.items() if k != 'resume'}
    # Optional graduation_window becoming required must not disappear behind the static map.
    assert form.CONTROLS['graduation_window'][0] in observed["completeness"]["required_selectors"]


def test_offviewport_observation_is_not_falsely_reported_as_obscured():
    observed = evaluate(form.control_expression('#first_name'), "bySelector['#first_name'].getBoundingClientRect=()=>({left:0,top:-500,width:10,height:10,bottom:-490,right:10});document.elementFromPoint=()=>null;")
    assert observed["visible"] is True
    assert observed.get("in_viewport") is False
    assert observed["unobscured"] is None


def test_submit_rechecks_exact_client_state_in_same_dom_activation():
    expected = evaluate(form.client_form_expression())
    try:
        expression = form.submit_expression(form.SUBMIT_SELECTOR, activate=True, expected_state=expected)
    except TypeError:
        pytest.fail('atomic client-state check missing from submit')
    assert evaluate('(async()=>{await ('+expression+');return clicks;})()') == 1
    with pytest.raises(subprocess.CalledProcessError):
        evaluate(expression, "bySelector['#first_name'].value='Drift';bySelector['#first_name'].__reactProps$fixture.value='Drift';")


def test_entire_worker_json_requests_fit_default_streamreader_line_limit():
    observed=evaluate(form.client_form_expression())
    for expression in [form.client_form_expression(), form.submit_expression(form.SUBMIT_SELECTOR,activate=True,expected_state=observed)]:
        guarded='(() => {if(location.href !== '+json.dumps(form.URL)+')throw new Error("drift");return ('+expression+');})()'
        payload={'action':'call','target':'A'*32,'prefix':form.URL,'method':'Runtime.evaluate','params':{'expression':guarded,'returnByValue':True,'awaitPromise':True}}
        assert len(json.dumps(payload).encode()) + 1 < 65536


@pytest.mark.parametrize('required,hidden,allowed', [(False,True,True),(True,True,False),(False,False,False)])
def test_only_hidden_nonrequired_iti_phone_search_is_not_an_answer(required,hidden,allowed):
    change="""const search=node('iti-0__search-input','');search.type='search';search.required=REQUIRED;search.hidden=HIDDEN;search.closest=()=>({querySelector:s=>s==='#phone'?phone:null});nodes.push(search);""".replace('REQUIRED',json.dumps(required)).replace('HIDDEN',json.dumps(hidden))
    observed=evaluate(form.client_form_expression(),change)
    assert ('iti-0__search-input' not in observed['completeness']['unknown_controls']) is allowed


def test_submit_refuses_value_drift_while_browser_file_hash_is_awaited():
    expected=evaluate(form.client_form_expression())
    expression=form.submit_expression(form.SUBMIT_SELECTOR,activate=True,expected_state=expected)
    change="""const originalRead=file.arrayBuffer.bind(file);file.arrayBuffer=async()=>{bySelector['#first_name'].value='Drift';bySelector['#first_name'].__reactProps$fixture.value='Drift';return originalRead();};"""
    with pytest.raises(subprocess.CalledProcessError): evaluate(expression,change)


def test_rendered_react_label_must_agree_with_real_selected_choice():
    selector=form.CONTROLS['school'][0]
    changed="bySelector["+json.dumps(selector)+"].selected='Not the bound choice';"
    assert evaluate(form.control_expression(selector),changed)['bound'] is False






