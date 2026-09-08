# Cancellation Boundary for Live Applications

Use this protocol when Kevin says `stop`, `cancel`, `forget it`, or otherwise withdraws an in-progress application instruction.

## Immediate response

1. Freeze the workflow at once. Perform no additional browser, account, email, tracker, or notification mutation.
2. Do not click cleanup/undo controls, close the tab, delete an upload, submit a partially completed profile, or continue verification unless Kevin explicitly asks for that action.
3. Cancel all remaining application checklist items. A cancellation is not a failed application and must never trigger a success notification.

## State report

Report only boundaries established by evidence:

- **Browser-local/autofilled:** fields or a resume parser may have populated the live form, but nothing is proven persisted.
- **Profile/account persisted:** claim this only after a server confirmation, authenticated candidate profile, or other exact read-back.
- **Application submitted:** claim this only after the normal confirmation contract is satisfied.

State whether `Submit Profile` and the final application submit were actually invoked. Never infer a created account or submitted application from an email/GDPR step, resume parsing, a populated form, or a navigation alone.

## Resume later

When Kevin resumes, reacquire the exact live tab and inspect the portal/server state before acting. Do not replay the last click, upload, profile submission, or final submission from memory.
