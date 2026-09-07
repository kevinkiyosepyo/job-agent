"""Conservatively register old intent journals before any new automatic submit.

Only registered production manifests are inspected. This is not proof that every
manual/one-off application was discovered, nor proof an unknown intent succeeded.
Journal modification time is an upper-bound observation, not an invented ATS date.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def migrate_registered_history(*, runtime_root, profile_path, account_id, ledger,
                               current_pre_intent=None):
    root=Path(runtime_root).resolve()
    profile=Path(profile_path).resolve()
    records=[]
    blockers=[]
    for path in sorted(root.glob('**/manifest.json')):
        if path.is_relative_to(root/'autonomous-controller'):
            continue
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError('untrusted manifest path')
            raw=path.read_bytes()
            manifest=json.loads(raw)
            if manifest.get('mode')!='production_live':
                continue
            if Path(manifest['profile']['path']).resolve()!=profile:
                raise ValueError('historical account profile mismatch')
            journal=Path(manifest['runtime_paths']['submit_journal'])
            if not journal.is_file():
                # Only the caller's exact already-validated manifest can be new.
                # Re-read content must still match; absence elsewhere is history.
                if (current_pre_intent is not None
                        and path == Path(current_pre_intent[0])
                        and manifest == current_pre_intent[1]
                        and not journal.exists() and not journal.is_symlink()
                        and journal.resolve().is_relative_to(path.parent.resolve())
                        and ledger.attempt_for_application(job_id=manifest['job_id'],
                            requisition=manifest['identity']['requisition'], account_id=account_id,
                            tenant=f"{manifest['identity']['platform']}:{manifest['identity']['tenant']}") is None):
                    handoff=Path(manifest['runtime_paths']['authorization_handoff'])
                    authorization_db=Path(manifest['runtime_paths']['authorization_db'])
                    # Unknown per-run authorization artifacts could contain used
                    # tokens. The shared store has already migrated consumed ones.
                    if (not handoff.exists() and not handoff.is_symlink()
                            and (authorization_db.resolve() == ledger.path.resolve()
                                 or (not authorization_db.exists() and not authorization_db.is_symlink()))):
                        continue
                raise ValueError('historical journal unavailable')
            if journal.is_symlink() or not journal.resolve().is_relative_to(path.parent.resolve()):
                raise ValueError('historical journal outside manifest scope')
            data=journal.read_bytes()
            events=[json.loads(line) for line in data.decode().splitlines() if line.strip()]
            if not all(isinstance(e,dict) and isinstance(e.get('evidence'),dict) for e in events):
                raise ValueError('malformed historical journal')
            intents=[e['evidence'] for e in events if e.get('action')=='submit' and e['evidence'].get('status')=='intent_recorded']
            if not intents:
                continue
            identity=manifest['identity'];target=manifest['target']
            expected={'job_id':manifest['job_id'],'target_id':target['id'],'page_url':target['url'],'requisition':identity['requisition']}
            if any(any(e.get(k)!=v for k,v in expected.items()) or e.get('verified') is not False for e in intents):
                raise ValueError('historical intent binding mismatch')
            key={'job_id':manifest['job_id'],'requisition':identity['requisition'],
                 'account_id':account_id,'tenant':f"{identity['platform']}:{identity['tenant']}"}
            previous=ledger.attempt_for_application(**key)
            if previous is None or previous['state']=='released':
                ledger.import_historical_attempt(**key,source_id=str(path),trusted=True,
                    evidence_sha256=hashlib.sha256(raw+b'\0'+data).hexdigest(),state='unknown',
                    attempted_at=datetime.fromtimestamp(journal.stat().st_mtime,timezone.utc))
            attempt=ledger.attempt_for_application(**key)
            records.append({'manifest':str(path),'state':attempt['state'],
                            'attempt_time_source':'journal_mtime_upper_bound','intent_count':len(intents)})
        except (ValueError, OSError, KeyError, TypeError):
            blockers.append({'manifest':str(path),'reason':'historical_evidence_requires_reconciliation'})
    unresolved=sum(record['state']!='confirmed' for record in records)
    return {'status':'blocked' if unresolved or blockers else 'registered_history_checked',
            'unresolved_count':unresolved,'records':records,'blockers':blockers,
            'complete_external_history_asserted':False}
