# Connection matching v1

`mule_hacks/backend/matching/` contains the Python algorithm, independent of
Reflex and embedding generation. **Connections → Build your puzzle** opens
`/matching` to collect puzzle pieces, optional predefined answers and select a
connection mode. Existing daily-question and poll buttons also use it.

## Setup

Stop the app, keep the same `INTERSECT_DB_PATH` as your accounts, then run:

```powershell
uv sync --cache-dir .cache/uv
.venv/Scripts/python.exe -m mule_hacks.backend.cli init
.venv/Scripts/python.exe -m mule_hacks.backend.cli prepare-matching
.venv/Scripts/python.exe -m mule_hacks.backend.cli backfill-embeddings
.venv/Scripts/reflex.exe run --env prod --single-port --backend-port 3001
```

Schema version 3 adds a separate puzzle title to the matching tables introduced
in version 2. Upgrading versions 1 or 2 backs up SQLite and preserves existing
accounts, IDs, password hashes, sessions, messages, questions, votes and groups.
Initialization never invokes the model or invents answers from legacy fields.
Backfill explicitly embeds old responses once and is resumable.

Only `prepare-matching` downloads the requested MiniLM model, into the private
project cache `.cache/matching/models`. Regular requests load it locally on CPU.
Missing model files give an actionable error; demo vectors are never substituted.
New/edited puzzle pieces and daily answers encode outside write locks, then save
their text and vector atomically. Unchanged text reuses its vector. Records store
model name, text SHA-256, dimensions and vector. Ranking never encodes text and
omits stale/missing/corrupt vectors until edited or explicitly backfilled. Text
beyond the model's token limit is rejected rather than silently truncated.

## Scoring

| Section | Default weight | Calculation |
| --- | ---: | --- |
| Puzzle | 40% | Best one-to-one semantic assignment / larger piece count |
| Questions/polls | 20% | Shared daily answers at 70%, shared poll choices at 30% |
| Groups | 20% | Jaccard of approved, non-archived memberships |
| Personal | 20% | Mean of shared categorical equality / multi-select Jaccard |

Cosine is clamped to `[0,1]`; negative/orthogonal cosine gives zero. Puzzle
matching compares all piece pairs and uses maximum-weight one-to-one assignment.
Each piece contributes once; unpaired pieces count as zero within this section.
One strong piece cannot dominate a larger puzzle. An entirely absent section is
unavailable, rather than zero. Pair scoring is symmetric before trait filtering.

Daily answers compare the same question ID only. Polls compare the same poll ID
only: same choice is one, different choice zero. Disjoint response histories are
unavailable. Neither user in any groups gives `None`; one nonempty group set
compared with an empty set gives zero. Missing/empty personal fields are omitted.
Zero scores remain available. Weights redistribute proportionally at **both**
levels. No positive-weight comparable data gives overall `None`, with no match.

`config.py` contains every weight/threshold and a validated `MatchingConfig` for
overrides. `PERSONAL_FIELDS` defines initial optional age range, status, event
interests, hobbies, personality, communication style and connection goals.
Names, email, phone, LinkedIn, role, messages and Question Board text are excluded.
Legacy moral/comfort data is not assigned an invented meaning.

## Modes

- **Similar:** `[0.75,1.00]`, highest overall score first.
- **Different:** `[0.35,0.65]`, nearest `0.50` first, with at least one anchor:
  a puzzle pair scoring `>=0.75`, shared group, same poll choice or shared
  predefined hobby/event interest/connection goal. Age/status alone is no anchor.
- **Trait:** chosen trait must score `>=0.75`, then rank by overall score. Choose
  an own saved puzzle piece (semantic overlap), daily answer (same question),
  poll answer, joined group or predefined personal answer. This is a hard
  filter, including when overall similarity is below the Similar threshold.

Ties use candidate ID. Empty strict results stay empty; requirements are not
silently relaxed. To search a free-text interest like “robotics,” save it as a
puzzle piece first, then choose it as a trait. Search never generates embeddings.

## Authenticated API

| Route/action | Input/result |
| --- | --- |
| `GET /api/matching/profile` | Own puzzle/personal inputs and predefined field definitions, without vectors |
| `GET /api/matches?mode=similar&limit=20` | Candidates; limit 1–50; optional URL-encoded JSON `trait` |
| `savePuzzlePiece` | `{id?: string, category, title, description}`; up to 8 pieces, titles up to 20 characters and descriptions up to 500. Older `text` payloads remain supported. |
| `deletePuzzlePiece` | `{id: string}`; owned pieces only |
| `savePersonalAnswers` | `{answers: {field: string \| string[] \| null}}`; merge, null/empty clears |
| `findMatches` | `{mode, trait?: {...}, limit?: number}` |
| `createConnection` | `{kind: 'match', mode, userId?: candidateId, trait?: {...}}` |

Submit actions through `POST /api/action` as `{"method": ..., "input": {...}}`.
Session, Origin and CSRF rules are unchanged. Actor IDs come from the session.
Example trait: `{"category":"personal","field":"hobbies","value":"robotics"}`.
Other trait categories use `{category,value}` with the own puzzle piece ID,
question ID, poll ID or joined group ID. Modes are `similar`, `different`, `trait`.

Candidates return `user_id`, anonymous `alias`, `overall_similarity`,
`category_scores`, `effective_weights`, `effective_subweights`, `connection_mode`,
`shared_anchors`, `match_reason`, `puzzle_details`, `comparable_counts`, `algorithm`
and, in trait mode, `trait_similarity`. Puzzle details contain matched piece IDs,
categories, strengths, weak areas and unmatched IDs, without raw peer text.

Self, blocks in both directions and existing open/ended conversation partners
are excluded. Creation rechecks current inputs/blocks in its write transaction
and saves score, explanation, mode/trait and configuration in `matchdecisionbase`.
Ranking performs no writes. Identity and phone still require separate consent;
candidate responses expose no contact details, embeddings or raw peer profiles.

Both public and private poll responses contribute to matching, including shared
anchors and poll trait filters. Result visibility only controls poll statistics:
private polls return no percentages, vote totals or option counts to ordinary
users. A match similarity score describes the pair, not the poll voting results.
Only published/closed polls and daily questions participate; archived content and
pending/rejected groups are excluded. Toggling result visibility does not change
matching scores or eligibility. Admin result access remains protected.

## Limits and tests

Semantic similarity means **topic overlap, not agreement**. “I love camping” and
“I hate camping” can be close. Reasons preserve this limitation; pure scoring
accepts a semantic comparator for future stance analysis. No compatibility claim
or sentiment system is added. Shared-data counts indicate evidence breadth; the
score is not confidence, and one shared answer can produce a high score.

V1 ranks the local community in memory. It has no vector database, approximate
search, learned weights or cached rankings. Tune thresholds with real event data.
Unit tests inject deterministic counting encoders: no download/GPU is required.
They cover all requested profile/mode cases, dominant pieces, missing weights,
ownership, persistence/backfill, privacy, blocks and version-1 migration.

Verified with 44 backend tests, 11 frontend provider tests, Ruff and Reflex
compilation. Actual CPU MiniLM produced 384-dimensional vectors. Chrome browser
checks against an isolated QA database at `http://localhost:3003/matching/`
covered saving inputs, Similar/Different/trait filtering, explanation display and
anonymous conversation creation, including private poll trait selection and matching
with percentages, totals and option counts withheld, at 1440×1000 and 390×844. No page/console errors,
framework error overlays or horizontal overflow were observed. Browser plugin
unavailable; regular Playwright was used. Screenshots are temporary QA artifacts,
outside the repository. Semantic quality across a real event population still
requires evaluation; this does not establish that the thresholds suit every event.

Model references: [MiniLM model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
and [Sentence Transformers encoding API](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html).
