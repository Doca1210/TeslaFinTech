"""Payment screening subsystem.

Architecture (see docs/design/priority_backlog.md section 2.3):

    POST /screen
        -> PaymentIntake            (intake.py)        validate + normalize
        -> ScreeningLayer plugins    (layers/)           run independently, in parallel
        -> VerdictComposer           (composer.py)       MATCH > REVIEW > NO_MATCH
        -> outputs/                                      audit, review queue, post-match workflow

List ingestion (OFAC SDN, OpenSanctions, ...) lives in app.ingestion and runs as a
separate batch/cron job. It is NOT a screening layer and is not part of this pipeline.
"""
