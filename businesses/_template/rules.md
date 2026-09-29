# Rules — REPLACE: Business name

Rules that apply only to this business. Global rules: `shared/rules/global-rules.md`.
Industry defaults: `shared/rules/industries/<industry>.md`. Client-scoped rules
(`Scope: client:<id>`) override business rules, which override industry defaults.
Non-negotiable global rules can never be overridden.

Start with what the GM tells you in the day-one interview (shared/runbooks/01-day-one-takeover.md):
report dates, sign-offs, client quirks. After that, rules arrive through the Wednesday
corrections review (`python3 -m holdco corrections review <business>`).

Format (copy this block):

    ## R-XXX-001 · Short title
    - **Applies to:** monthly-close
    - **Scope:** all            (or client:<client id>)
    - **Rule:** What the agent must do, in one or two plain sentences.
    - **Why:** So a person can judge edge cases.
    - **Check:** `{"type": "vendor_category", "match": "VENDOR", "category": "Category"}`   (optional)
    - **Source:** who said so, when
