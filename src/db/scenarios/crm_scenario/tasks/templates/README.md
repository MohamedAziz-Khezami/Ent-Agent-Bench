# Task templates

One YAML file = one task type at one difficulty tier. The folder is the
tier (`easy/`, `medium/`, `hard/`, `expert/`); the filename says what the
model has to do. Every value in a file is literal — no knobs hidden in
tier configs — so each file is the complete, self-contained definition of
its task.

`actions.yaml` (at this level) is different: it's the shared **menu of
verbs** the `act_on_a_*` templates sample from (`chosen: {sample:
deal_actions, k: 2}` = "pick 2 dishes off the menu").

## Anatomy of a template

Every file has the same numbered sections, in the same order:

| Section | What it is |
|---|---|
| header comment | WHAT THE MODEL IS ASKED / WHAT IT TESTS / HOW IT'S MADE VALID |
| metadata | `name`, `answer_keys`, `n_functions` (min tool calls a correct solution needs), `n_actions` |
| `params:` | **1. dice rolls** — evaluated top to bottom; later entries may reference earlier ones |
| `kernel:` | **2. rows planted into the world** (the task's data, injected into background noise) |
| `distractors:` | optional lookalike rows, deliberately confusable but never matching the anchor's description |
| `effects:` | **3. what a correct solution must have changed** (becomes `expected_added`/`expected_changed`) |
| `answer:` | **4. the correct answer** (`ground_truth`) |
| `query:` or `entity:`+`phrasings:` | **5. the question text** — either fixed, or an entity label wrapped in one of several phrasings |

## DSL cheat-sheet

| Construct | Example | Meaning |
|---|---|---|
| `{choice: [...]}` | `stage: {choice: [prospecting, proposal]}` | pick one |
| `{randint: [lo, hi]}` | `score: {randint: [5, 55]}` | random integer in range |
| `{draw: <pool>}` | `company: {draw: company}` | draw from pools.py (same pools the noise uses) |
| `{sample: <menu>, k: n}` | `chosen: {sample: deal_actions, k: 2}` | pick k actions from actions.yaml |
| `{value_between: [lo, hi]}` | `{value_between: ["threshold * 1.3", 120000]}` | deal value on the noise's 500-step grid; endpoints may be expressions |
| `{sim_date_offset: n}` | `{sim_date_offset: {randint: [-15, -1]}}` | date relative to the frozen sim clock (negative = past) |
| `{if: [{when, then}, ...]}` | branch on an earlier param | first matching `when` wins |
| `{expr: "..."}` | `{expr: "date_offset(item.due_date, 3)"}` | safe arithmetic / date math |
| `"{param}"` | `stage: "{stage}"` | placeholder; a lone placeholder keeps its type |
| `"@ref"` / `"@ref.field"` | `lead_id: "@the_lead"` | the injected row's id (or a column of it) |
| `repeat: n` | plant a GROUP of rows; `@group` refs pair element-wise between same-size groups |
| `for_each: <group>` | effects applied per row of a group (`@item`, `@item.field`) |
| `from_chosen_actions: {anchor: "@ref"}` | expand the sampled menu actions into effects on the anchor |
| `guards:` | predicates no background row may match (rarely needed — name/company reservation covers most cases) |

## The guarantees (why noise can't break a task)

1. **Identity reservation** — names/companies the kernel uses are removed
   from the noise generator's pools before the background is drawn.
2. **Reference partitioning** — background rows only reference background
   parents (a planted rep can never accidentally own noise deals).
3. **Anti-fingerprint interleaving** — planted rows get id slots shuffled
   uniformly into each table, values drawn from the same distributions as
   noise (`cheater.py` measures this stays at the guessing floor).
4. **The audit** (`python -m ...tasks.audit`) re-checks every invariant on
   every frozen world after each rebuild: golden solution passes verify(),
   anchors unique, groups closed, no-ops impossible, no generator drift.

## Workflow

```
edit templates  ->  python -m src.db.scenarios.crm_scenario.tasks.build_tasks
                ->  python -m src.db.scenarios.crm_scenario.tasks.audit
                ->  python -m src.db.scenarios.crm_scenario.tasks.cheater
```

Rebuilding regenerates all frozen `task_XXX.json` + `task_XXX.sqlite`
pairs deterministically (same seeds -> byte-identical corpus).
