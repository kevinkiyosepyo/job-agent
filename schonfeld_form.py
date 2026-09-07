"""Schonfeld 8171772 controls learned from the saved untouched form.

Education IDs may renumber after parsing: every prefix must be unique at use.
This is a one-page React form, not a learned server-saved Review surface.
"""
import json

URL = "https://job-boards.greenhouse.io/schonfeld/jobs/8171772"

CONTROLS = {
    "first_name": ("#first_name", "replace_text"),
    "last_name": ("#last_name", "replace_text"),
    "email": ("#email", "replace_text"),
    "country": ("#country", "react_select_exact"),
    "phone": ("#phone", "replace_tel_local_digits"),
    "location": ("#candidate-location", "react_select_exact"),
    "resume": ("#resume", "cdp_upload"),
    "school": ("input[id^='school--']", "react_select_exact"),
    "degree": ("input[id^='degree--']", "react_select_exact"),
    "discipline": ("input[id^='discipline--']", "react_select_exact"),
    "education_start_month": ("input[id^='start-month--']", "react_select_exact"),
    "education_start_year": ("input[id^='start-year--']", "replace_text"),
    "education_end_month": ("input[id^='end-month--']", "react_select_exact"),
    "education_end_year": ("input[id^='end-year--']", "replace_text"),
    "linkedin": ("#question_68930281", "replace_text"),
    "website": ("#question_68930282", "replace_text"),
    "gpa": ("#question_68930283", "replace_text"),
    "current_degree": ("#question_68930284", "react_select_exact"),
    "graduation_window": ("#question_68930285", "react_select_exact"),
    "work_authorization": ("#question_68930286", "react_select_exact"),
    "sponsorship_now": ("#question_68930287", "react_select_exact"),
    "sponsorship_future": ("#question_68930288", "react_select_exact"),
    "gender": ("input[id='963']", "react_select_exact"),
    "hispanic_latino": ("input[id='1240']", "react_select_exact"),
    "race": ("input[id='1241']", "react_select_exact"),
}
REQUIRED = [key for key in CONTROLS if key not in {
    "linkedin", "website", "graduation_window", "gender", "hispanic_latino", "race",
}]
MAPPING = {
    "version": 1, "platform": "greenhouse", "tenant": "schonfeld",
    "hostname": "job-boards.greenhouse.io", "path_prefix": "/schonfeld/jobs/8171772",
    "exact_url": URL,
    "steps": {
        "application": {
            "controls": {key: {"selector": selector, "operation": operation}
                         for key, (selector, operation) in CONTROLS.items()},
            "required_fields": REQUIRED, "required_conditions": [], "next_step": "review",
        },
        "review": {
            "controls": {"submit": {"selector": ".application--submit button[type='submit']", "operation": "submit"}},
            "required_fields": [], "required_conditions": ["authoritative_review"], "next_step": None,
        },
    },
}


def control_expression(selector: str) -> str:
    if selector not in {item[0] for item in CONTROLS.values()}:
        raise ValueError("unknown Schonfeld control")
    return r"""(() => {
        const matches = [...document.querySelectorAll(SELECTOR)];
        if (matches.length !== 1) return {count: matches.length};
        const element = matches[0], style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        const in_viewport = typeof window === 'undefined' ? true : rect.top + rect.height > 0 && rect.left + rect.width > 0 && rect.top < window.innerHeight && rect.left < window.innerWidth;
        const visible = style.display !== 'none' && style.visibility !== 'hidden'
            && Number(style.opacity) !== 0 && element.getClientRects().length > 0;
        const top = visible ? document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2) : null;
        const propsKey = Object.keys(element).find(key => key.startsWith('__reactProps$'));
        const props = propsKey ? element[propsKey] : null;
        let value = element.value, choice = null;
        let bound = Boolean(props && Object.hasOwn(props, 'value') && String(props.value) === element.value);
        let binding_source = bound ? 'react_input_props' : 'unverified';
        if (element.id === 'phone' && !bound) {
            const fiberKey = Object.keys(element).find(key => key.startsWith('__reactFiber$'));
            let fiber = fiberKey ? element[fiberKey] : null;
            for (let depth=0; fiber && depth<20; depth++,fiber=fiber.return) {
                const p=fiber.memoizedProps;
                if (p && (p.id==='phone' || p.inputProps?.id==='phone') && typeof p.value==='string') {
                    bound = p.value.replace(/\D/g,'') === element.value.replace(/\D/g,'') && !!p.value;
                    binding_source = bound ? 'react_phone_ancestor' : 'unverified';
                    break;
                }
            }
        }
        if (element.getAttribute('role') === 'combobox') {
            const fiberKey = Object.keys(element).find(key => key.startsWith('__reactFiber$'));
            let fiber = fiberKey ? element[fiberKey] : null;
            for (let depth = 0; fiber && depth < 40; depth++, fiber = fiber.return) {
                const select = fiber.memoizedProps?.selectProps;
                if (select?.inputId === element.id) {
                    const selected = select.value;
                    choice = Array.isArray(selected) ? selected : selected ? [selected] : [];
                    break;
                }
            }
            const selected = element.closest('.select__control')?.querySelector('.select__single-value');
            value = selected ? selected.innerText.trim() : '';
            bound = bound && element.value === '' && Boolean(value) && Array.isArray(choice)
                && choice.length === 1 && choice[0]?.value !== undefined && Boolean(choice[0]?.label)
                && (choice[0].label === value || (element.id === 'country' && /^\+\d+$/.test(value) && choice[0].label.endsWith(' ' + value)));
        }
        return {count: matches.length, value, choice, bound, binding_source,
            required: element.required === true || element.getAttribute('aria-required') === 'true',
            in_viewport,
            valid: (!element.validity || element.validity.valid) && element.getAttribute('aria-invalid') !== 'true',
            visible, enabled: !element.disabled && element.getAttribute('aria-disabled') !== 'true',
            unobscured: in_viewport ? top === element || element.contains(top) : null};
    })()""".replace("SELECTOR", json.dumps(selector))


def verify_profile_answers(profile: dict, answers: dict) -> None:
    """Check accepted canonical facts; a mutable answer file cannot approve itself.

    application_facts is the accepted profile's explicit extension for facts not
    present in the legacy profile (e.g. education start dates/option labels).
    Root canonical facts always win over that extension.
    """
    facts = dict(profile.get("application_facts", {}))
    name, contact, education = profile.get("name", {}), profile.get("contact", {}), profile.get("education", {})
    sources = {
        "first_name": name.get("first"), "last_name": name.get("last"),
        "email": contact.get("email"), "phone": contact.get("phone"),
        "school": education.get("university"), "degree": education.get("degree"),
        "current_degree": education.get("degree"), "discipline": education.get("major"),
        "gpa": education.get("gpa"), "education_end_year": education.get("expected_graduation"),
        "education_start_month": education.get("start_month"), "education_start_year": education.get("start_year"),
        "education_end_month": education.get("end_month"),
        "gender": profile.get("gender"), "race": profile.get("race_ethnicity"),
        "linkedin": profile.get("links", {}).get("linkedin"), "website": profile.get("links", {}).get("website"),
        "resume": profile.get("resume", {}).get("primary"),
    }
    for field, source in (("work_authorization", "work_authorization"), ("sponsorship_now", "requires_sponsorship"), ("sponsorship_future", "requires_sponsorship")):
        value = profile.get(source)
        sources[field] = ("Yes" if value else "No") if isinstance(value, bool) else None
    facts.update({field: value for field, value in sources.items() if value is not None})
    aliases = {
        "school": {"University of California, San Diego": "University of California - San Diego"},
        "degree": {"Bachelor of Science": "Bachelor's Degree"},
        "current_degree": {"Bachelor of Science": "Bachelor's"},
        # Learned fallback: this exact tenant's discipline list has no Data Science.
        "discipline": {"Data Science": "Other"},
    }
    for field, answer in answers.items():
        expected = facts.get(field)
        actual = answer.get("exact_option") if isinstance(answer, dict) else answer
        if expected is not None:
            expected = aliases.get(field, {}).get(str(expected), str(expected))
        if field == "phone" and isinstance(actual, str) and isinstance(expected, str):
            actual, expected = "".join(c for c in actual if c.isdigit()), "".join(c for c in expected if c.isdigit())
        if expected is None or actual != expected:
            raise ValueError(f"canonical profile fact missing or conflicting for {field}")


SUBMIT_SELECTOR = ".application--submit button[type='submit']"


def submit_expression(selector: str, *, activate: bool = False, expected_state: dict | None = None) -> str:
    if selector != SUBMIT_SELECTOR:
        raise ValueError("unknown one-page Submit selector")
    if activate and not isinstance(expected_state, dict):
        raise ValueError("fresh reviewed client state required before activation")
    state_check = ""
    if activate:
        expected = {k:v for k,v in expected_state.items() if k != 'observed_at'}
        state_check = """
            const actual = await (READ_FORM);
            delete actual.observed_at;
            const stable = v => Array.isArray(v) ? v.map(stable) : v && typeof v==='object'
                ? Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])])) : v;
            if (JSON.stringify(stable(actual)) !== JSON.stringify(stable(EXPECTED))) throw new Error('client form drift before activation');
        """.replace("READ_FORM", client_form_expression()).replace("EXPECTED", json.dumps(expected))
    return """(/* schonfeld:submit */ async () => {
        STATE_CHECK
        const nodes = [...document.querySelectorAll(SELECTOR)], button = nodes[0];
        const visible = !!button && button.getClientRects().length > 0
            && getComputedStyle(button).display !== 'none' && getComputedStyle(button).visibility !== 'hidden';
        const enabled = !!button && !button.disabled && button.getAttribute('aria-disabled') !== 'true';
        const modal = [...document.querySelectorAll('[role="dialog"],[aria-modal="true"]')].some(e => e.getClientRects().length);
        const result = {unique:nodes.length===1,visible,enabled:enabled&&!modal,role:button?.tagName==='BUTTON'?'button':'unknown'};
        ACTIVATE
        return result;
    })()""".replace("SELECTOR", json.dumps(selector)).replace("STATE_CHECK", state_check).replace("ACTIVATE", """
        if (!result.unique || !result.visible || !result.enabled || result.role !== 'button') throw new Error('Submit no longer safe');
        button.click();
    """ if activate else "")


def client_form_expression() -> str:
    """One read-only DOM/React inventory; hash the actual browser File, never a name."""
    shared_reader = control_expression("#first_name").removeprefix("(() => {").removesuffix("})()")
    shared_reader = shared_reader.replace(json.dumps("#first_name"), "selector")
    return r"""(/* schonfeld:client-bound */ async () => {
        const controls = CONTROLS_JSON, required = REQUIRED_JSON;
        const readControl = selector => {SHARED_READER};
        const states = Object.fromEntries(Object.entries(controls).filter(([key])=>key!=='resume').map(([key,[selector]])=>[key,readControl(selector)]));
        const shown = e => {const s=getComputedStyle(e); return e.getClientRects().length>0 && s.display!=='none' && s.visibility!=='hidden' && Number(s.opacity)!==0;};
        const forms = [...document.querySelectorAll('form')].filter(f => f.querySelector('#first_name'));
        const form = forms.length === 1 ? forms[0] : null;
        const fields = {}, bindings = {}, questions = [];
        const requiredSelectors = [];
        for (const [key, [selector, operation]] of Object.entries(controls)) {
            if (key === 'resume') continue;
            const state = states[key];
            const isRequired = required.includes(key) || state.required === true;
            if (isRequired) requiredSelectors.push(selector);
            if (state.value) fields[selector] = operation === 'replace_tel_local_digits' ? state.value.replace(/\D/g,'') : state.value;
            bindings[selector] = {count:state.count,bound:state.bound,valid:state.valid,visible:state.visible,enabled:state.enabled,choice:state.choice};
            questions.push({id:key,required:isRequired,answered:!!state.value,verified:state.bound===true&&state.valid===true});
        }
        const unknown = [], invalid = [];
        for (const element of form ? form.querySelectorAll('input,select,textarea') : []) {
            const key = Object.keys(controls).find(k => element.matches(controls[k][0]));
            if (element.validity?.valid === false || element.getAttribute('aria-invalid')==='true') invalid.push(element.id || element.name || 'unidentified');
            if (key || element.type==='hidden') continue;
            if (/^iti-\d+__search-input$/.test(element.id) && element.type==='search' && !element.required
                && element.getAttribute('aria-required') !== 'true' && !shown(element)
                && element.closest('.iti')?.querySelector('#phone') === form.querySelector('#phone')) continue;
            if (/^g-recaptcha-response/.test(element.name || element.id) && !shown(element)) continue;
            if (element.id==='cover_letter' && !element.required && !element.files?.length) continue;
            unknown.push(element.id || element.name || 'unidentified');
        }
        const gates = [];
        if ([...document.querySelectorAll('[role="dialog"],[aria-modal="true"],iframe[src*="/bframe"],iframe[src*="hcaptcha.com/captcha"]')].some(shown)) gates.push('visible_modal_or_challenge');
        if ([...document.querySelectorAll('[role="alert"],.field-error,.input-error,.select__error')].some(e=>shown(e)&&e.textContent.trim())) gates.push('visible_validation_error');
        const groups=[...document.querySelectorAll('[aria-labelledby="upload-label-resume"]')];
        let resume={basename:'',sha256:'',verified:false,attachment_present:false,source:'live_browser_file',content_type:''};
        if (groups.length===1 && shown(groups[0])) {
            const names=[...groups[0].querySelectorAll('.file-upload__filename p')].filter(shown);
            if (names.length===1) {
                const name=names[0].innerText.trim(), files=new Set(), seen=new WeakSet(); let visits=0;
                const collect = (obj, depth=0) => {
                    if (!obj || typeof obj!=='object' || seen.has(obj) || depth>7 || ++visits>5000) return;
                    seen.add(obj);
                    if (obj instanceof File) {if(obj.name===name) files.add(obj); return;}
                    if (obj instanceof Node) return;
                    for (const descriptor of Object.values(Object.getOwnPropertyDescriptors(obj))) {
                        if ('value' in descriptor) collect(descriptor.value,depth+1);
                    }
                };
                for (const input of groups[0].querySelectorAll('input[type="file"]')) for (const f of input.files || []) collect(f);
                let element=groups[0];
                // Only the attachment's React ancestry; no page-wide state or secret extraction.
                const fiberKey=Object.keys(element).find(k=>k.startsWith('__reactFiber$'));
                let fiber=fiberKey?element[fiberKey]:null;
                for(let depth=0;fiber&&depth<16;depth++,fiber=fiber.return) {
                    collect(fiber.memoizedProps); collect(fiber.memoizedState);
                    if(fiber.stateNode===form) break;
                }
                if (files.size===1) {
                    const file=[...files][0];
                    const digest=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());
                    resume={basename:name,sha256:[...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join(''),
                        verified:file.size>0&&file.type==='application/pdf',attachment_present:true,source:'live_browser_file',content_type:file.type};
                }
            }
        }
        const afterStates = Object.fromEntries(Object.entries(controls).filter(([key])=>key!=='resume').map(([key,[selector]])=>[key,readControl(selector)]));
        if (JSON.stringify(states) !== JSON.stringify(afterStates)) throw new Error('form changed during browser File validation');
        return {source:'live_client_bound_form',server_saved:false,page_url:location.href,observed_at:new Date().toISOString(),
            fields,bindings,resume,questions,parser_repairs:[],
            completeness:{verified:!!form,unknown_controls:unknown,invalid_controls:invalid,gates,required_selectors:requiredSelectors}};
    })()""".replace("CONTROLS_JSON", json.dumps(CONTROLS)).replace("REQUIRED_JSON", json.dumps(REQUIRED)).replace("SHARED_READER", shared_reader)

