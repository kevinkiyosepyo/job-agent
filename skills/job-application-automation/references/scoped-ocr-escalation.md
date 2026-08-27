# Scoped OCR and Visual Escalation

Use across every ATS when DOM/accessibility state and the rendered page disagree or a verified browser action fails.

## Escalation ladder

1. Freshly verify exact target ID, URL, company/role/requisition, and current application step.
2. Inventory the control through DOM/accessibility state and perform one semantic browser/CDP action.
3. Read back the bound value and validation state. If it succeeded, stop; never duplicate the action.
4. After a verified failure or genuinely ambiguous rendered state, capture one screenshot scoped to the exact bound page—not the full desktop.
5. Use OCR/vision only to observe labels, visible values, overlays, focus, viewport/Retina scale, and control location.
6. Revalidate exact target ID/URL, visible/enabled state, viewport scale, and overlay absence.
7. Perform at most one inspected browser/CDP retry and read back state again.
8. If still blocked, retain sanitized evidence and return a stable blocker.

## Hard boundary

OCR is observation-only. It never authorizes:

- `osascript` or System Events `click at`;
- `cliclick`, pyautogui, Quartz/CGEvent global dispatch;
- full-screen coordinate conversion;
- focus stealing, Apple-menu/menu-bar interaction, System Settings, or About This Mac;
- bypass of CAPTCHA, assessment, email/identity verification, or account security.

For native browser chrome, use app-scoped `computer_use` with a fresh capture and element index; ATS page controls remain exact-target CDP/browser actions. A screenshot from an earlier viewport or target is stale evidence and must not be reused.