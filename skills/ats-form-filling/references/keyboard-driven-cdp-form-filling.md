# Driving ATS forms by keyboard over CDP (occluded-window safe)

Mouse-coordinate automation of React-backed ATS forms fails in ways that look like
a broken session but are not. This file records the keyboard-only technique that
works regardless of window occlusion, plus the coordinate rules that apply when
the window really is visible.

## Symptom: the session looks dead but is fine

When another application covers the automation browser window, macOS reports:

```javascript
document.visibilityState  // "hidden"
document.hasFocus()       // true
```

In that state the OS never paints popup menus, so **mouse clicks on a react-select
open nothing** — option queries return `[]` — and coordinate clicks below the fold
are rejected as offscreen. Nothing is broken; the input channel is just wrong.

**Readiness check must accept either signal:**

```python
def front(t, attempts=4):
    for i in range(attempts):
        t.send("Page.bringToFront")
        time.sleep(0.6 + 0.4 * i)
        if t.js("document.visibilityState") == "visible":
            return True
        if t.js("document.hasFocus()") is True:   # occluded but focused: usable
            return True
    raise RuntimeError("target neither visible nor focused")
```

Requiring `visible` alone strands a fully working session. Do not respond to this
by trying to raise or resize the window — that fights the user for their screen.

## Keyboard patterns (work occluded)

### Option-backed control (react-select)

Focus the input via JS, open with `ArrowDown`, type to filter, commit with `Enter`:

```python
t.js("(function(id){var e=document.getElementById(id);"
     "e.scrollIntoView({block:'center'}); e.focus();})(%s)" % json.dumps(fid))
for typ in ("rawKeyDown", "keyUp"):
    t.send("Input.dispatchKeyEvent", type=typ, key="ArrowDown", code="ArrowDown",
           windowsVirtualKeyCode=40, nativeVirtualKeyCode=40)
t.send("Input.insertText", text=exact_option_label)   # filters to one row
for typ, extra in (("rawKeyDown", {}), ("char", {"text": "\r"}), ("keyUp", {})):
    t.send("Input.dispatchKeyEvent", type=typ, key="Enter",
           windowsVirtualKeyCode=13, nativeVirtualKeyCode=13, **extra)
```

### Text field

Clear with the native prototype setter (so React registers the change), focus via
JS, then type with trusted `Input.insertText`. No coordinates, so no offscreen
failures:

```javascript
var proto = e.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype
                                     : HTMLInputElement.prototype;
Object.getOwnPropertyDescriptor(proto, 'value').set.call(e, '');
e.dispatchEvent(new Event('input',  {bubbles: true}));
e.dispatchEvent(new Event('change', {bubbles: true}));
```

Skipping the clear causes values to **append** — the source of doubled names such
as `KevinKevin`.

### Submit

Focus the button via JS and press `Enter`. A keyboard activation on a focused
button is a trusted user gesture; `element.click()` is not, and a coordinate click
fails whenever the button sits below the fold:

```python
t.js("(function(){var b=[...document.querySelectorAll('button')]"
     ".find(x=>/submit application|^submit$/i.test(x.innerText.trim()) && !x.disabled);"
     "if(b){b.scrollIntoView({block:'center'}); b.focus();} return !!b;})()")
# then dispatch Enter as above
```

## Reading bound state correctly

Read an option-backed control's value from **its own subtree** — walk up from the
input to the first ancestor containing `[class*="singleValue"]`. Collecting all
`singleValue` nodes globally and matching by index leaks adjacent questions'
values and produces false "verified" results (observed: a School field reported as
holding `Bachelor's Degree`, which actually belonged to the Degree control).

A control that **displays** a value while its inner input still fails
`checkValidity()` never committed. Repair it by focusing, pressing `Backspace` a
few times to clear the selection, then re-picking.

## When the window IS visible: coordinate rules

- CDP mouse events cannot reach negative viewport coordinates. After working a
  control low on the page, earlier fields sit at e.g. `y = -1243`; a click there is
  **silently dropped** with no error and the field stays empty.
- Always `scrollIntoView({block:'center'})`, sleep, then **re-measure**
  `getBoundingClientRect()` before dispatching. Coordinates captured before a
  scroll are stale.
- React-select inputs are 3–4px wide; clicking their own rect misses. Either use
  the keyboard path above, or walk up to the first ancestor with
  `width > 60 && height > 20` and click that.

## Validity gates and checkbox groups

`e.willValidate && !e.checkValidity()` over every `input,textarea,select` is the
authoritative completeness check — it catches id-less inner inputs that no label
query finds. But every unchecked sibling in a required checkbox group also reports
invalid, so a naive gate blocks submission forever. Treat a group as satisfied
when any input sharing the `question_<id>[]` prefix is checked:

```javascript
if (e.type === 'checkbox') {
  var base = (e.id || '').split('[]')[0];
  var any = false;
  document.querySelectorAll('input[type=checkbox]').forEach(function (c) {
    if ((c.id || '').indexOf(base) === 0 && c.checked) any = true;
  });
  if (any) return;   // satisfied, not an error
}
```

## Other durable gotchas

- **A vanished file input is not a failed upload.** Many ATS forms remove
  `input[type=file]` after a successful attachment. Confirm by the rendered
  filename text, never by the input's continued existence.
- **Conditional required fields can appear only after a submit attempt.** When
  Submit yields no confirmation and no obvious error, read `[role=alert]` text and
  inspect the enclosing container's class — one posting hid a required essay that
  turned out to be a *file upload* (`div.file-upload`), not a textarea.
- **Some ATSs keep no server-side draft.** Reloading to recover a broken control
  discards every entered value. Complete the form in one pass.
- Interpreter note: CDP helper scripts need `websocket-client`. Invoke the
  interpreter that actually has it rather than assuming the shell default.
