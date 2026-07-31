# 0001. Classification is human-owned; AI provides only documented, overridable drafts

Date: 2026-07-31

## Status

Accepted

## Context

The dataset's central judgement column, whether a foresight mention is
"embedded" (actually used in the analysis) or "contextual" (a superficial
citation), is interpretive and will appear in published research. Three
options were considered:

1. Fully automate the judgement with an LLM.
2. Fully manual classification by the research team.
3. Deterministic pipeline locates and excerpts every mention; an LLM
   produces clearly-marked draft verdicts; the research team confirms or
   overrides every one.

Full automation is fast but methodologically weak for publication: the
judgement is not the researchers' own, and reviewers can reasonably ask
who decided and on what basis. Full manual work is exactly the burden the
team asked to remove. A further constraint: no paid API budget, so the AI
step runs in Claude sessions (Claude Code or claude.ai) under an existing
subscription, using a documented prompt over deterministic excerpts, which
any team member can rerun on their own subscription.

## Decision

Option 3. The deterministic layer must be sufficient on its own: every
mention gets a quoted excerpt and a page-linked location so a human can
classify with no AI involved. AI verdicts live in columns explicitly named
as drafts, with a quoted-evidence justification per mention. The final
verdict columns belong to the research team. The classification prompt is
versioned in this repository.

## Consequences

- The team can honestly describe the method as AI-assisted, evidence-linked,
  human-reviewed classification.
- Every AI judgement is checkable in seconds from the review page.
- The AI step is optional, reproducible on any Claude subscription, and
  replaceable without touching the deterministic pipeline.
- Cost: the team must actually review circa 162 documents' worth of drafts,
  which is the deliberate price of owning the judgement.
