"""Pipeline outputs — the three boxes after the Verdict Composer in section 2.3:

    - audit_store:   persist `payments` + `screening_results` (always, every verdict)
    - review_queue:  create `review_cases` entries (REVIEW verdicts only)
    - post_match:    compliance notification workflow (MATCH verdicts only)
"""
