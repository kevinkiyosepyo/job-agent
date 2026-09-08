"""Verified Workday-over-CDP helpers.

Extracted from a confirmed live Marvell submission (req 2604505). Every function
here exists because the naive version silently failed:

  * input is discarded in hidden tabs      -> always bring_to_front() first
  * fields are keyed by id, not automation -> _el() tries id, then automation-id
  * fuzzy option matching picks BA over BS -> pick_option() is exact by default
  * coords go stale after scrollIntoView   -> pick_option() re-measures post-scroll
  * click_filter overlays swallow clicks   -> click_sel() clicks the topmost element

Requires: websocket-client. Attach to ONE exact-URL target; never sibling tabs.
"""
import json
import time


JS_HELPERS = r"""
window.__wd = {
  _el: function(key){
    return document.getElementById(key)
        || document.querySelector('[data-automation-id="'+key+'"] input, [data-automation-id="'+key+'"] textarea')
        || document.querySelector('[data-automation-id="'+key+'"]')
        || document.querySelector(key);
  },
  setText: function(key, val){
    var wrap = window.__wd._el(key);
    var el = wrap ? (wrap.matches && wrap.matches('input,textarea') ? wrap
                    : (wrap.querySelector ? wrap.querySelector('input,textarea') : null)) : null;
    if(!el) return 'missing:'+key;
    var proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype
                                          : window.HTMLInputElement.prototype;
    var native = Object.getOwnPropertyDescriptor(proto,'value').set;
    el.focus();
    native.call(el,'');
    el.dispatchEvent(new Event('input',{bubbles:true}));
    native.call(el,val);
    el.dispatchEvent(new Event('input',{bubbles:true}));
    el.dispatchEvent(new Event('change',{bubbles:true}));
    el.dispatchEvent(new Event('blur',{bubbles:true}));
    return 'ok:'+el.value;
  },
  getText: function(key){
    var wrap = window.__wd._el(key);
    var el = wrap ? (wrap.matches && wrap.matches('input,textarea') ? wrap
                    : (wrap.querySelector ? wrap.querySelector('input,textarea') : null)) : null;
    return el ? el.value : null;
  },
  coords: function(sel){
    var e = document.querySelector(sel);
    if(!e) return null;
    e.scrollIntoView({block:'center'});
    var r = e.getBoundingClientRect();
    var cx = r.left+r.width/2, cy = r.top+r.height/2;
    var top = document.elementFromPoint(cx,cy);   // click_filter overlay lives here
    var tr = top ? top.getBoundingClientRect() : r;
    return JSON.stringify({x:tr.left+tr.width/2, y:tr.top+tr.height/2,
      topId: top?(top.getAttribute('data-automation-id')||top.tagName):null});
  },
  options: function(){
    var out=[];
    document.querySelectorAll('[role="option"],[data-automation-id="promptOption"],li[role="option"]')
      .forEach(function(e){ if(e.getBoundingClientRect().width>0) out.push((e.innerText||'').trim()); });
    return JSON.stringify(out);
  },
  errors: function(){
    var s=[];
    document.querySelectorAll('[role="alert"],[data-automation-id*="rrorMessage"]').forEach(function(e){
      var x=(e.innerText||'').trim();
      if(x && !/successfully uploaded/i.test(x)) s.push(x.slice(0,160));
    });
    return JSON.stringify(s);
  },
  step: function(){
    var e=document.querySelector('[data-automation-id="progressBarActiveStep"]');
    return e?e.innerText.trim().replace(/\n/g,' '):'';
  }
};
'wd-installed'
"""


def install(tab):
    """Bring the target to front (REQUIRED) and install helpers."""
    tab.send("Page.bringToFront")
    time.sleep(0.4)
    out = tab.js(JS_HELPERS)
    vis = tab.js("document.visibilityState")
    if vis != "visible":
        raise RuntimeError(f"target still {vis}; synthetic input will be discarded")
    return out


def _real_click(tab, x, y):
    tab.send("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
    time.sleep(0.15)
    for ev in ("mousePressed", "mouseReleased"):
        tab.send("Input.dispatchMouseEvent", type=ev, x=x, y=y, button="left", clickCount=1)


def click_sel(tab, sel):
    """Click by selector at overlay-aware coordinates."""
    raw = tab.js(f"window.__wd.coords({json.dumps(sel)})")
    if not raw:
        return f"missing {sel}"
    c = json.loads(raw)
    _real_click(tab, c["x"], c["y"])
    return f"clicked {sel} (top={c['topId']})"


def pick_option(tab, want, exact=True, settle=1.3):
    """Scroll the option into view, RE-MEASURE, then click. Exact by default."""
    idx = tab.js("""(function(want, exact){
      var els=document.querySelectorAll('[role="option"],[data-automation-id="promptOption"],li[role="option"]');
      for(var i=0;i<els.length;i++){
        var txt=(els[i].innerText||'').trim();
        var hit = exact ? txt===want : txt.toLowerCase().indexOf(want.toLowerCase())>=0;
        if(hit){ els[i].scrollIntoView({block:'center'}); return i; }
      }
      return -1;
    })(%s, %s)""" % (json.dumps(want), str(exact).lower()))
    if idx == -1:
        return None
    time.sleep(settle)                      # let the scroll settle before measuring
    raw = tab.js("""(function(idx){
      var els=document.querySelectorAll('[role="option"],[data-automation-id="promptOption"],li[role="option"]');
      var e=els[idx]; if(!e) return null;
      var r=e.getBoundingClientRect();
      return JSON.stringify({x:r.left+r.width/2,y:r.top+r.height/2,text:(e.innerText||'').trim()});
    })(%d)""" % idx)
    if not raw:
        return None
    c = json.loads(raw)
    _real_click(tab, c["x"], c["y"])
    time.sleep(settle)
    return c["text"]


def select_exact(tab, button_id, candidates, settle=1.6):
    """Open a dropdown and select the first exactly-matching candidate.

    Returns the bound label. Compare it to what you intended before continuing:
    a wrong-but-plausible bind (BA instead of BS) is the failure mode here.
    """
    if isinstance(candidates, str):
        candidates = [candidates]
    getter = ("(function(){var b=document.getElementById(%s);return b?b.innerText.trim():null;})()"
              % json.dumps(button_id))
    for want in candidates:
        if tab.js(getter) == want:
            return want
        click_sel(tab, f'[id="{button_id}"]')
        time.sleep(settle)
        if pick_option(tab, want, True):
            time.sleep(settle)
            return tab.js(getter)
    return tab.js(getter)


def set_date(tab, base_id, mm, dd, yyyy, settle=1.0):
    """Workday date segments: YEAR first, MONTH last (month clears otherwise)."""
    order = (("Year", yyyy), ("Day", dd), ("Month", mm)) if dd else (("Year", yyyy), ("Month", mm))
    for seg, val in order:
        fid = f"{base_id}-dateSection{seg}-input"
        tab.js("window.__wd.setText(%s, %s)" % (json.dumps(fid), json.dumps(str(val))))
        time.sleep(settle)
    return {seg: tab.js("window.__wd.getText(%s)" % json.dumps(f"{base_id}-dateSection{seg}-input"))
            for seg in (("Month", "Day", "Year") if dd else ("Month", "Year"))}


def advance(tab, expect_change_from=None, tries=18, settle=3.0):
    """Save and Continue, then confirm the step actually changed."""
    before = expect_change_from or tab.js("window.__wd.step()")
    click_sel(tab, '[data-automation-id="pageFooterNextButton"]')
    for _ in range(tries):
        time.sleep(settle)
        step = tab.js("window.__wd.step()")
        errs = json.loads(tab.js("window.__wd.errors()"))
        if step and step != before:
            return {"advanced": True, "step": step, "errors": errs}
        if errs:
            return {"advanced": False, "step": step, "errors": errs}
    return {"advanced": False, "step": tab.js("window.__wd.step()"), "errors": ["timeout"]}
