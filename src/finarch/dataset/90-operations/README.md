# Production common operation

[Step of the letter: yoga; action flow](../../../../docs/01-dataset/90-operations/README.md) · [A whole source structure](../../../../docs/01-dataset/90-operations/05-source-layout.md)

This folder owns the execution code for the documented stage. Output paths follow the existing run contract.

|File|Role|
|---|---|
|[adaptive_schedule.py](adaptive_schedule.py)|Coordinate case submission independently of case completion.|
|[audit_ea_migration.py](audit_ea_migration.py)|Read-only bounded audit of interrupted migration local ZIP records.|
|[execution_timing.py](execution_timing.py)|Local-time lifecycle records with monotonic elapsed time and replayable argv.|
|[failed_recheck.py](failed_recheck.py)|Stage internal processing and inspection|
|[failure_analysis.py](failure_analysis.py)|Confirmed, immutable failure-analysis jobs dispatched by existing schedulers.|
|[feedback_records.py](feedback_records.py)|Immutable retry feedback and verifiable references; no model calls.|
|[finish_ea_migration.py](finish_ea_migration.py)|Bounded, journaled recovery of the interrupted EA label migration.|
|[full_pipeline.py](full_pipeline.py)|Chain the existing phase schedulers; phase schedulers retain file ownership.|
|[migrate_ea_labels.py](migrate_ea_labels.py)|One-time, backed-up migration of legacy EA identifiers in project artifacts.|
|[numbered_layout.py](numbered_layout.py)|One automatic run index for the numbered artifact stages.|
|[ordered_artifacts.py](ordered_artifacts.py)|Physical filenames follow the actual calculation-call sequence.|
|[perturbation_policy.py](perturbation_policy.py)|Opt-in bounded coefficient selection, fixed targets and no provider calls.|
|[preparation_gate.py](preparation_gate.py)|Batch review boundary between preparation and variant generation.|
|[run_identity.py](run_identity.py)|Allocate date-sequence run directories in Korea time under one filesystem lock.|
|[schedule_lock.py](schedule_lock.py)|One scheduler per run. Keep the inode stable; the OS releases dead owners.|
|[schedule_settings.py](schedule_settings.py)|Load scheduling numbers from the project's hyperparameter file.|
|[stage_paths.py](stage_paths.py)|Shared stage paths for artifact writers, readers, logs and viewer navigation.|
|[stage_range.py](stage_range.py)|Validate explicit stage ranges and preserve superseded local artifacts.|
|[staging.py](staging.py)|Sequential orchestration support, not a Python/LLM/graph implementation.|
