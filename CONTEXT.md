# Foresight in EU Impact Assessments

Research data pipeline for Laura De Vito's team: harvest all EU Commission
impact assessments (register search, dateFrom 2022-01-31), detect and classify
foresight usage in each, and produce a structured dataset.

## Language

**Impact Assessment (IA)**:
One register entry in the EU Register of Commission Documents with type
Impact assessment, identified by its SWD reference (e.g. SWD(2026)616).
One IA = one row in the dataset, regardless of how many PDFs it has.
_Avoid_: report, document (ambiguous with Part)

**Part**:
One PDF attachment belonging to an IA (part 1 is usually the main report;
later parts are annexes). All parts are downloaded and analysed; every
foresight mention is tagged with its part number.
_Avoid_: attachment, file

**Reference**:
The Commission's SWD identifier for an IA, e.g. SWD(2026)580. The primary
key of the dataset.

**Foresight Mention**:
A case-insensitive occurrence of the string "foresight" anywhere in any Part
of an IA. Drives the headline y/n column; auditable by page reference.
_Avoid_: counting related-method terms toward this column

**Mention**:
One occurrence of "foresight" at a specific location (Part, page). The unit
of classification and evidence. Each Mention carries a quoted excerpt and a
page-linked location, produced deterministically, so a human can classify it
without any AI involvement.

**AI draft verdict**:
An embedded/contextual judgement produced by Claude (in a Claude Code or
claude.ai session, not a paid API), stored in clearly-marked draft columns.
A head start for the researchers, never the final answer; Laura's team
confirms or overrides. The prompt used is documented so the step can be
rerun on their own Claude subscription.

**Embedded**:
Verdict on a Mention: foresight was actually used in the IA's analysis
(methods, scenarios, inputs that shaped the assessment). An IA is Embedded
if any of its Mentions is Embedded.
_Avoid_: calling an IA embedded from a citation alone

**Contextual**:
Verdict on a Mention: a superficial citation or passing reference (including
bibliography-only occurrences). The default verdict.

**Related-method term**:
A configurable exact-phrase list of foresight-adjacent methods (horizon
scanning, megatrends, scenario planning, Delphi, backcasting) counted in
supplementary columns, separate from Foresight Mention.

**Topic**:
One label per IA from a controlled vocabulary (12-20 policy areas) derived
from the full set of titles and confirmed with Laura, then assigned by AI.
_Avoid_: free-text topics

**Responsible service**:
The Commission department (DG) responsible for the IA, taken verbatim from
the register API (e.g. CLIMA, HOME). Deterministic cross-check on Topic.
_Avoid_: lead organisation/person

**Scope**:
The type of legal act the IA accompanies, extracted from the title into a
small enum (new/amending regulation, new/amending directive, decision,
multiple acts). Definition to be confirmed with Laura.
