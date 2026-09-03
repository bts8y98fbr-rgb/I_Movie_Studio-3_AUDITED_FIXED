# Local Codex Worklog

Сергей добавляет сюда результаты локального Codex. Джарвис и Copilot читают этот файл перед новыми архитектурными выводами.

## How to append

Для короткого вывода добавьте новую запись сверху под `Entries`.

Для большого полного отчёта:

1. создайте `.ai_exchange/codex_runs/YYYY-MM-DD_RUN-NNN.md`;
2. вставьте полный вывод без секретов;
3. добавьте здесь краткое резюме и ссылку;
4. укажите SHA, режим Codex, команду теста и результат.

Никогда не добавляйте `.env`, API keys, OAuth/device codes или credential URLs.

## Entries

## CODEX-RUN-20260903-008

- Mode: Codex desktop, read-only selected-model schema propagation audit with isolated governance recording
- Repository: local `I_Movie_Studio-3_AUDITED_FIXED`
- Base commit: `28711f20046f54c513356bc7344efef2adde02d0`
- Examined HEAD: `28711f20046f54c513356bc7344efef2adde02d0`
- Examined `origin/main`: `28711f20046f54c513356bc7344efef2adde02d0` after `git fetch origin main`; divergence `0/0`
- Scope: read-only trace of `ModelRouter → ShotModelSelector → ShotRenderer/render plan → GenerationEngine → GenerationTask → GenerationQueue → provider/result/storage/render consumers`
- Architecture verdict: DOUBLE NESTING CONFIRMED; the production producer emits a schema incompatible with the fixed-policy consumer and with the flat model descriptor expected by reporting contracts

### Stage 2C verification

- `DEC-APPROVED-013` is present in `.ai_exchange/DECISIONS.md`.
- Runtime commit `28711f2` contains exactly:
  - `core/movie_engine/generation_engine.py`
  - `tests/test_generation_engine_model_policy_propagation.py`
- `GenerationEngine.__init__()` accepts optional `model_policy=None`, preserves the supplied object as `self.model_policy`, and passes the identical reference to every `GenerationTask` it creates.
- The propagation test is tracked and contains the approved fixed mismatch and exact-match contracts.
- This audit did not rerun pytest; the accepted Stage 2C gates remain `2 passed` targeted and `82 passed` full regression.

### Actual producer-to-consumer schema map

#### 1. ModelRouter produces a coherent routing wrapper

- `core/ai_core/model_router.py:70-103` selects one model descriptor and resolves quality.
- `core/ai_core/model_router.py:105-114` returns:

```text
{
  status,
  selected_model: {
    name, type, quality, motion, realism, detail, profiles,
    resolutions, fps, hdr, color_depth
  },
  shot_profile,
  requested_quality,
  actual_quality,
  fallback_applied,
  notification,
  time
}
```

- Actual structure: `model_result["selected_model"]["name"]` is the stable model identity.
- Expected structure at this boundary: the wrapper above; no mismatch exists inside `ModelRouter`.
- Architectural consequence: the wrapper and the selected model descriptor are distinct concepts and must not both be named `selected_model` at successive levels.

#### 2. ShotModelSelector introduces the first schema break

- `core/ai_core/shot_model_selector.py:41-60` creates shot context and obtains the complete `model_result` wrapper.
- `core/ai_core/shot_model_selector.py:63-92` returns its own shot-selection envelope but assigns `"selected_model": model_result` at lines 89-90.
- Actual structure becomes:

```text
shot_model_selection.selected_model.selected_model.name
```

- Expected downstream structure is:

```text
shot_model_selection.selected_model.name
```

- In-memory production introspection confirmed:
  - selector `selected_model` keys are `status`, `selected_model`, `shot_profile`, `requested_quality`, `actual_quality`, `fallback_applied`, `notification`, `time`;
  - actual identity path resolves at `selected_model.selected_model.name`;
  - `selected_model.get("name")` returns `None`.
- Architectural consequence: the first proven producer break is `ShotModelSelector.select_for_shot()`, not `ModelRouter` and not `GenerationQueue`.

#### 3. ShotRenderer serializes the broken value verbatim

- `core/movie_engine/shot_renderer.py:35-38` obtains `shot_model` from the real selector.
- `core/movie_engine/shot_renderer.py:39-53` writes the unchanged object as each shot's `shot_model_selection`.
- `core/movie_engine/shot_renderer.py:55-74` serializes it into `render_plan.json` without schema validation or versioning.
- Actual render-plan path is therefore `shots[].shot_model_selection.selected_model.selected_model.name`.
- Expected render-plan path is `shots[].shot_model_selection.selected_model.name`.
- Architectural consequence: `ShotRenderer` is the natural owner of the versioned render-plan envelope and should validate the canonical schema before persistence, but it is not the origin of the malformed selection object.

#### 4. GenerationEngine and GenerationTask preserve the value

- `core/movie_engine/generation_engine.py:45-47` reads the render plan as JSON.
- `core/movie_engine/generation_engine.py:91-105` copies `shot["shot_model_selection"]` unchanged into task metadata.
- `core/movie_engine/generation_engine.py:107-116` creates the real `GenerationTask` and now propagates `model_policy` after Stage 2C.
- `core/ai_core/generation_queue.py:11-35` copies the metadata dictionary shallowly and preserves the policy reference.
- Actual and expected behavior at these boundaries is pass-through; neither module creates the double nesting.
- Architectural consequence: normalization here would conceal an upstream schema defect unless implemented as an explicit, versioned legacy compatibility adapter.

#### 5. GenerationQueue consumes a flat descriptor but passes the outer envelope to the provider

- `core/ai_core/generation_queue.py:84-95` reads `shot_model_selection` and assigns `selected_model = shot_model_selection.get("selected_model", {})`.
- `core/ai_core/generation_queue.py:97-123` reads fixed-policy identity as `selected_model.get("name")`.
- With production selector output, `selected_model` is the ModelRouter wrapper, so `selected_model_name` is `None`.
- `core/ai_core/generation_queue.py:125-135` records that wrapper, not the model descriptor, as audit `model_selection.model` for policy-less tasks.
- `core/ai_core/generation_queue.py:137-143` passes the complete outer `shot_model_selection` envelope as `provider.generate(model=...)`.
- `core/ai_core/generation_queue.py:150-164` uses the one-level `selected_model` value as fallback for `task.result["model"]` and `task.result["metadata"]["selected_model"]` only when the provider did not already set them.
- Architectural consequence: Queue has two inconsistent notions of model data: it expects a flat descriptor for identity/audit/result fallback, but sends the entire selection envelope to the backend.

#### 6. VideoProvider and storage preserve the wrong shape

- `core/ai_core/providers/video/video_provider.py:56-70` reads `kwargs["model"]` without interpreting or flattening it.
- `core/ai_core/providers/video/video_provider.py:134-147` stores the complete argument as `result["model"]`.
- `core/ai_core/providers/video/video_provider.py:152-187` stores the same complete argument as `result.metadata.selected_model`, while also retaining original `metadata.shot_model_selection`.
- `core/ai_core/result_storage.py:39-74` obtains the original task metadata and selection envelope.
- `core/ai_core/result_storage.py:77-103` and `133-168` persist that envelope as asset/registry `model`, full metadata, and result.
- `core/ai_core/asset_registry.py:67-112` preserves `asset["model"]` verbatim; registration/versioning serializes it without normalization.
- Architectural consequence: policy-less production generation succeeds but propagates the malformed nested schema into provider manifests, task results, asset files, registry records, and versions.

#### 7. Reload, report, compile, and export consumers

- `core/movie_engine/project_dashboard.py:56-92` and `core/movie_engine/project_report.py:50-104` expect `asset["model"]["name"]`.
- A production-nested asset model has no top-level `name`, so model aggregation silently omits it.
- `render/render_pipeline.py:66-77,95-154` carries task/result metadata through render results but does not inspect or flatten model identity.
- `core/movie_engine/movie_compiler.py:50-95,149-177` carries result assets into the compiled movie and reads quality/timeline, not model identity.
- `core/movie_engine/export_pipeline.py:41-96` builds tracks without inspecting model identity.
- No reload/compile/export consumer performs silent flattening. The malformed shape is retained where data is copied and ignored where model identity is not required.

### Flat and nested test contracts

- Flat canonical model descriptors are used by:
  - `tests/test_quality_routing.py:60-72,93-100` for `ModelRouter` results;
  - `tests/test_runtime_model_policy_boundary.py:23-33` for Queue fixed-policy identity;
  - `tests/test_generation_engine_model_policy_propagation.py:21-46` for Stage 2C propagation;
  - `tests/test_model_generation_flow.py:21-47` for a hand-authored render plan;
  - `tests/test_result_storage_versions.py:23-31` for storage input;
  - `tests/test_asset_metadata_enrichment.py:11-26,78-90`, `tests/test_project_dashboard.py:13-23,62-68`, and `tests/test_project_report.py:12-35,73-77` for registry/report contracts.
- The nested wrapper is explicitly assumed by `tests/test_shot_model_selection.py:18-32,46-60,74-88`, which checks `result["selected_model"]["shot_profile"]` rather than a descriptor name.
- No existing test covers the real `ShotRenderer → render plan → GenerationEngine → fixed Queue` schema path.
- Architectural consequence: current green tests validate two mutually incompatible schemas because hand-authored plans are flat while the production plan producer is nested.

### Wrapper fields and duplication

- The ModelRouter wrapper contains `status`, `requested_quality`, `actual_quality`, `fallback_applied`, `notification`, `shot_profile`, and `time` (`model_router.py:105-114`).
- ShotModelSelector already duplicates `shot_profile` at its top level and inside `shot_context` (`shot_model_selector.py:63-90`).
- ShotRenderer separately writes preset quality into each shot and render settings (`shot_renderer.py:39-64`).
- GenerationEngine independently resolves backend quality and stores `requested_quality`, `actual_quality`, `fallback_applied`, and `quality_notification` in task metadata (`generation_engine.py:71-105`).
- No downstream production consumer reads the nested ModelRouter wrapper quality fields today; direct ModelRouter tests do validate them.
- Bare flattening in ShotModelSelector would remove the only serialized copy of the ModelRouter wrapper fields from render plans. Although those fields are currently duplicated or unused downstream, discarding them silently is an information-loss risk. A future fix should explicitly preserve approved routing diagnostics as sibling metadata or deliberately version/remove them by contract.

### Runtime consequences

#### Policy-less task

- Policy enforcement is skipped because `task.model_policy` is `None`.
- Audit receives the ModelRouter wrapper as `model`, not the descriptor.
- Provider receives the entire ShotModelSelector envelope as its `model` argument.
- VideoProvider, result fallback/storage, registry, and version files preserve nested data without validation.
- Generation can report success despite semantically malformed model metadata.

#### Fixed exact or mismatch policy

- For any production-generated nested selection, Queue reads `selected_model_name=None`.
- An exact fixed provider/model choice is falsely rejected before audit and provider execution.
- A true model mismatch is also rejected, but the error reports selected model `None`, hiding the actual selected identity one level deeper.
- Thus fixed enforcement remains safe against unauthorized execution but cannot distinguish an actual mismatch from the schema mismatch.

#### Audit, provider, result, and asset consequences

- Fixed rejection prevents the `model_selection` audit and provider call, then creates a failed task result without model metadata.
- Policy-less execution records the wrapper in audit, sends the outer envelope to the provider, and persists multiple copies of the malformed structure.
- `ProjectDashboard` and `ProjectReport` expect a top-level descriptor name and silently fail to count nested production models.
- Render/compile/export preserve or ignore the malformed model data; none repairs it.

#### Existing render-plan compatibility

- Existing flat hand-authored render plans remain compatible with Queue fixed enforcement.
- Existing production-generated nested render plans remain usable only for policy-less execution and retain malformed metadata.
- After a producer-only flattening fix, old nested plans would still falsely fail fixed policy unless explicitly migrated, rejected with a schema-version error, or handled by a separately approved compatibility boundary.
- No current render-plan schema version or migration contract exists.

### Architecture options

#### Option A — fix ShotModelSelector producer

Proposed core change: `selected_model = model_result["selected_model"]`.

- Source of truth: strongest; fixes the first producer that mislabels a routing wrapper as a model descriptor.
- Blast radius: narrow production change, but existing `tests/test_shot_model_selection.py` encodes the old nested contract and must be updated in a separately approved fix stage.
- Backward compatibility: new plans become canonical; already persisted nested plans remain incompatible with fixed policies.
- Defect visibility: does not hide the upstream problem.
- Audit/provider/result impact: new data becomes flat and aligns with Queue/reporting identity expectations.
- Information risk: bare replacement drops wrapper status/quality/notification fields from selector output unless they are preserved explicitly as sibling routing metadata.
- Migration need: decide schema versioning or an explicit legacy-plan policy; do not silently reinterpret identities.
- Minimum test scope: one new end-to-end schema contract test plus updates to the existing selector tests that currently require nesting.
- Verdict: RECOMMENDED, with explicit preservation/versioning decision for useful wrapper diagnostics.

#### Option B — normalize in ShotRenderer orchestration

- Source of truth: render-plan serializer can enforce its persisted schema, but the selector continues returning a misleading internal contract.
- Blast radius: localized to plan construction and its tests.
- Backward compatibility: new plans can be flat; existing plans are unchanged and still require migration handling.
- Defect visibility: partially hides the selector defect at serialization time.
- Audit/provider/result impact: good for newly generated plans if all relevant wrapper fields are deliberately remapped.
- Information risk: ad hoc extraction can discard routing diagnostics or duplicate quality data inconsistently.
- Migration need: same legacy-plan/versioning issue as Option A.
- Minimum test scope: ShotRenderer schema test and end-to-end Queue fixed-policy test.
- Verdict: acceptable only as a schema-validation/serialization gate after the selector contract is made explicit; not preferred as the sole fix.

#### Option C — make GenerationQueue accept both structures

- Source of truth: weakest; a shared execution consumer would own compatibility for malformed producer data.
- Blast radius: affects every queued task and policy/audit/result path.
- Backward compatibility: highest for old flat and nested plans.
- Defect visibility: high risk of permanently hiding the producer contract defect.
- Audit/provider/result impact: identity lookup alone could become green while provider/audit/storage still receive wrappers; full normalization would broaden Queue responsibilities and silently rewrite persisted semantics.
- Migration need: can act as an explicitly temporary, version-aware compatibility adapter, but no version marker exists today.
- Minimum test scope: flat, nested legacy, malformed, fixed exact/mismatch, audit, provider argument, result metadata, and storage regression tests.
- Verdict: NOT RECOMMENDED as the primary fix; consider only under a separate explicit backward-compatibility decision.

### Recommended authoritative schema and ownership

Canonical model identity in every render-plan shot should be:

```text
shot_model_selection.selected_model.name: string
```

- `selected_model` must be the model descriptor, never the `ModelRouter` result wrapper.
- `ShotModelSelector` should own the canonical `shot_model_selection` value contract because it composes that object and introduces the current break.
- `ShotRenderer` should own render-plan envelope versioning/validation and refuse or explicitly migrate noncanonical persisted shapes under a separately approved compatibility policy.
- Useful routing diagnostics should be preserved as clearly named sibling metadata rather than nested under `selected_model`.

### Recommended minimal next RED stage

- New test file: `tests/test_selected_model_schema_contract.py`
- Exact count: one hermetic end-to-end contract test.
- Real production classes:
  - `QualityPolicy`, `ModelRouter`, `ShotModelSelector`, and `ShotRenderer` as producers;
  - `GenerationEngine`, `GenerationTask`, and `GenerationQueue` as transfer/consumer path;
  - real default `ProviderManager` and `ProviderRegistry` with registered `Video AI` backend.
- Permitted local controls:
  - constrain the real `ModelRouter` instance to one deterministic model descriptor named `requested-model`;
  - instance-local provider router stub returning the registered backend identity, because provider routing is not under test;
  - replace only that backend instance's `generate()` with a no-I/O call spy.
- Input: one temporary storyboard shot whose real `ShotRenderer.create_render_plan()` produces the render plan; canonical fixed policy requests the same backend and `requested-model`.
- Expected canonical structure: `shots[0]["shot_model_selection"]["selected_model"]["name"] == "requested-model"`.
- Actual current structure: identity exists only at `shots[0]["shot_model_selection"]["selected_model"]["selected_model"]["name"]`; the flat lookup is absent.
- Run the real `GenerationEngine.generate_scene(1)` before assertions so the same test observes the real Queue consequence.
- Expected RED: an exact fixed provider/model choice is falsely refused; task status/result are `failed`, provider spy count is zero, and the policy error reports selected model `None` instead of `requested-model`.
- Future GREEN contract: render-plan selected model is flat, the exact fixed policy reaches Queue, provider spy is called exactly once, and task/result finish `done`/`success`.
- Isolation: no UI, project persistence, default provider routing, PixVerse, fallback semantics, preferred/automatic policy, live provider, credentials, `.env`, or GUI participates.
- The test may write only temporary storyboard/render/result/asset artifacts under `tmp_path`; it must not use network or project assets.

### Presumed future fix and rollback scope

Recommendation only; not authorization:

- Production owner: `core/ai_core/shot_model_selector.py`.
- Test scope likely required for a GREEN regression:
  - new `tests/test_selected_model_schema_contract.py`;
  - existing `tests/test_shot_model_selection.py`, whose assertions currently codify the nested wrapper.
- `core/movie_engine/shot_renderer.py` should change only if Product Owner separately approves explicit render-plan validation/versioning or preservation of wrapper diagnostics.
- `GenerationQueue` should not normalize both forms in the minimal fix.
- Atomic rollback scope should match the finally approved production/test file list; old nested plans and diagnostic-field preservation must be decided before implementation.

### Residual risks and decisions required

- No formal typed or versioned render-plan schema exists.
- Existing persisted plans may contain either hand-authored flat or production-generated nested selections.
- Bare producer flattening can lose router status/quality/notification diagnostics.
- Queue currently passes the outer selection envelope to provider `model`, even when identity lookup expects the inner descriptor.
- VideoProvider and storage duplicate model data at several different nesting levels.
- Dashboard/report silently omit production-nested model identities.
- Model/provider identities remain string-based.
- MoviePipeline is a separate policy-less producer and does not use this render-plan path.
- UI/persistence, preferred/automatic semantics, provider routing, PixVerse, fallback, and direct LLM paths remain separate concerns.

### Scope and controls

- No production code or test was changed or created.
- No pytest suite was run.
- Only in-memory Python introspection of `ModelRouter` and `ShotModelSelector` was used; it performed no provider call and created no project asset.
- No network other than the authorized `git fetch`, no live API, credentials, `.env`, GUI, or live provider was used.
- `DECISIONS.md`, `COPILOT_TO_JARVIS.md`, documentation, ModelPolicy semantics, UI, persistence, MoviePipeline, Router, ProviderManager, ProviderRegistry, PixVerse, fallback, and Reactive Orchestrator were not changed.
- The pre-existing dirty/untracked tree remained unchanged against baseline.
- The proposed RED test and every production fix require separate explicit decisions from Sergey, Product Owner.

## CODEX-RUN-20260903-007

- Mode: Codex desktop, stage 2C hermetic GenerationEngine fixed ModelPolicy propagation RED test
- Repository: local `I_Movie_Studio-3_AUDITED_FIXED`
- Base commit: `9d293b97afd1a3da8c7bbf45c24fb31f54d1d953`
- Examined HEAD: `5837bdab493c355ad2aee636d3ee155fdb4d698f`
- Related decision: `DEC-APPROVED-012`
- Test file: only new untracked `tests/test_generation_engine_model_policy_propagation.py`
- Targeted command: `PATH="$PWD/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q tests/test_generation_engine_model_policy_propagation.py`
- Targeted result: `1 failed in 0.14s`
- RED verdict: EXPECTED — `GenerationEngine` omitted the canonical fixed policy while constructing `GenerationTask`, so the queue did not refuse a deliberate model mismatch before execution

### Observed policy and task state

- Canonical policy: `ModelPolicy(provider="Video AI", model="requested-model", mode=SelectionMode.FIXED)`
- Selected execution model identity: `executed-model`
- Actual `task.model_policy`: `None`
- Provider spy call count: `1`
- Actual task status: `done`
- Actual task result status: `success`
- Exact assertion diagnostic: `GenerationEngine omitted canonical ModelPolicy: task.model_policy=None; provider_spy_call_count=1; task.status='done'; task.result_status='success'`
- The expected fixed-policy refusal did not occur because `GenerationQueue.process_next()` received no policy on the task.

### Proven runtime path and hermeticity

```text
canonical ModelPolicy attached to engine.model_policy
    -> actual GenerationEngine.generate_scene(1)
    -> actual registered Video AI backend from ProviderManager/ProviderRegistry
    -> actual GenerationTask(model_policy=None)
    -> actual GenerationQueue.process_all()/process_next()
    -> local backend generate spy called once
```

- The test uses the actual `GenerationEngine`, `GenerationTask`, `GenerationQueue`, `ProviderManager`, and `ProviderRegistry`.
- `ProviderManager` and `ProviderRegistry` were not replaced or monkeypatched.
- The instance-local router stub was used only to select the already registered `Video AI` backend deterministically; provider routing is not the subject of this test.
- Only the registered backend instance's `generate()` method was replaced by a local call-recording spy, which returned a deterministic in-memory result.
- The render plan contains one shot and the flat boundary schema `shot_model_selection["selected_model"]["name"] = "executed-model"`.
- No network, live API, live provider request, credentials, `.env`, or GUI was used.
- The first prescribed shell invocation could not start pytest because unqualified `python` was unavailable (`exit 127`); the project-local `.venv/bin` was then placed first on `PATH`, and the targeted gate above ran normally.

### First proven propagation break

- `core/movie_engine/generation_engine.py` creates `GenerationTask` without passing `self.model_policy` (or any `model_policy`).
- Consequently, the canonical policy attached at the proposed `GenerationEngine.model_policy` boundary is lost at task construction.
- The Stage 2B fixed-policy enforcement in `GenerationQueue` remains present but is bypassed because `task.model_policy` is `None`.

### Recommended future production scope

This is a recommendation only and does not authorize a production fix:

- `core/movie_engine/generation_engine.py`
- `tests/test_generation_engine_model_policy_propagation.py`

The narrow future change should pass the identical optional canonical policy object from `GenerationEngine` into each created `GenerationTask`. Any production change requires a separate Product Owner decision.

### Residual risks outside this RED stage

- UI defines a duplicate ModelPolicy type and does not materialize the canonical policy.
- Project persistence does not save or reconstruct canonical policy.
- `MoviePipeline` remains policy-less.
- The actual ShotModelSelector path has double nesting under `selected_model`, unlike the flat execution-boundary schema used here.
- Preferred and automatic ModelPolicy semantics remain outside the queue enforcement implemented in Stage 2B.
- Direct LLM generation paths bypass `GenerationQueue`.
- PixVerse and provider availability remain outside this stage.
- Fallback semantics remain outside this stage and no fallback was added.

### Scope and controls

- Production code and existing tests were not changed.
- The only new test is local and untracked; it was not staged, committed, or pushed.
- The pre-existing dirty working tree was preserved against the recorded baseline.
- No full regression suite was run.
- No ModelPolicy semantics, Router, Registry, ProviderManager, UI, persistence, MoviePipeline, PixVerse, fallback, or Reactive Orchestrator behavior was changed.
- Stage 2C is stopped after the expected RED pending Copilot review and a separate decision from Sergey, Product Owner.

## CODEX-RUN-20260903-006

- Mode: Codex desktop, read-only ModelPolicy propagation audit with isolated governance recording
- Repository: local `I_Movie_Studio-3_AUDITED_FIXED`
- Base commit: `88b37c8ad2d077309fcb2dae214aab25be0face0`
- Examined HEAD: `88b37c8ad2d077309fcb2dae214aab25be0face0`
- Examined `origin/main`: `88b37c8ad2d077309fcb2dae214aab25be0face0` after `git fetch origin main`; divergence `0/0`
- Related decision: `DEC-APPROVED-011`
- Scope: read-only audit of canonical ModelPolicy propagation from user/project state to `GenerationQueue.process_next()` after Stage 2B
- Verdict: canonical fixed `core.ai_core.model_policy.ModelPolicy` reaches the execution boundary only when a caller explicitly attaches it to `GenerationTask`; no examined production task producer currently does so

### Published Stage 2B verification

- `DEC-APPROVED-011` is present in `.ai_exchange/DECISIONS.md`.
- Governance commit `e64d7a7` changes only `.ai_exchange/DECISIONS.md`.
- Runtime commit `88b37c8` changes only `core/ai_core/generation_queue.py` and `tests/test_runtime_model_policy_boundary.py`.
- `tests/test_runtime_model_policy_boundary.py` contains two tests: mismatch refusal and exact fixed match.
- `GenerationTask` now has an optional `model_policy`; `GenerationQueue.process_next()` enforces canonical fixed provider/model identity before the `model_selection` audit and before `provider.generate()`.

### Actual policy propagation map

#### UI and project persistence path

```text
UI provider/model/mode widgets
    -> no conversion to canonical ModelPolicy
    -> no assignment to Project.metadata
    -> no persistence/reload contract
    -> MoviePipeline(project.path) without policy
```

- `ui/main_window.py:41-62` defines a second UI-local `SelectionMode` and `ModelPolicy`, not `core.ai_core.model_policy.ModelPolicy`.
- `ui/main_window.py:90` initializes `model_policies` as an empty dictionary; no production code populates or consumes it.
- `ui/main_window.py:156-164` creates provider, model, and mode widgets, but no handler converts their values into either UI or canonical policy.
- `ui/main_window.py:253-256` creates `MoviePipeline` with only `project.path`.
- `ui/main_window.py:281-290` saves the current `Project` without copying UI model selections into project metadata.
- `core/project_manager.py:68-79` persists only the generic `Project.metadata` dictionary.
- `core/project_manager.py:99-116` reloads metadata as a plain dictionary and does not reconstruct a canonical policy.

#### Render-plan / GenerationEngine path

```text
ShotRenderer
    -> ModelRouter / ShotModelSelector
    -> render_plan.shots[].shot_model_selection
    -> GenerationEngine.generate_scene()
    -> GenerationTask(metadata=..., model_policy omitted)
    -> GenerationQueue.process_next(): task.model_policy is None
    -> fixed enforcement skipped
    -> provider.generate()
```

- `core/movie_engine/shot_renderer.py:19-22` constructs `QualityPolicy`, `ModelRouter`, and `ShotModelSelector`, but no canonical `ModelPolicy`.
- `core/movie_engine/shot_renderer.py:35-64` writes model selection into the render plan without provider/model policy.
- `core/movie_engine/generation_engine.py:11-28` accepts project path and quality only; no policy input or project-policy load exists.
- `core/movie_engine/generation_engine.py:85-108` copies `shot_model_selection` into metadata but constructs `GenerationTask` without `model_policy`.
- `core/movie_engine/generation_engine.py:109-111` queues and processes those policy-less tasks through the real `GenerationQueue`.
- `core/movie_engine/render_engine.py:17-38` delegates to `GenerationEngine` without policy and inherits the same break.

#### MoviePipeline / UI movie path

```text
MainWindow._set_current_project()
    -> MoviePipeline(project.path)
    -> concrete VideoProvider()
    -> GenerationTask(model_policy omitted, shot_model_selection absent)
    -> GenerationQueue.process_next(): fixed enforcement skipped
    -> provider.generate()
```

- `core/movie_engine/movie_pipeline.py:49-98` has no policy parameter and constructs a concrete `VideoProvider` independently of UI selection.
- `core/movie_engine/movie_pipeline.py:146-155` sends queued shots to the shared `GenerationQueue`.
- `core/movie_engine/movie_pipeline.py:258-323` constructs `GenerationTask` without `model_policy` and without `shot_model_selection`.
- This path does not silently fallback inside the queue; it bypasses user policy entirely by selecting its provider independently.

#### Other generation-like paths

- `core/ai_core/llm/llm_manager.py:64-85` selects an LLM and calls `provider.generate()` directly, bypassing `GenerationQueue`; it uses hardware-oriented `RuntimePolicy`, not canonical ModelPolicy.
- `core/ai_core/ai_director.py:344-384` uses that direct LLM path while building direction data.
- `core/ai_core/asset_generator.py:137-223` writes deterministic local asset manifests directly and does not use a provider or `GenerationQueue`; it has no ModelPolicy enforcement.
- The only production `GenerationTask` constructors found are in `GenerationEngine` and `MoviePipeline`; both omit `model_policy`.

### Execution-boundary contract and schema

- `core/ai_core/generation_queue.py:11-35` stores the optional `GenerationTask.model_policy`.
- `core/ai_core/generation_queue.py:85-107` expects model identity at `task.metadata["shot_model_selection"]["selected_model"]["name"]`.
- `core/ai_core/generation_queue.py:97-123` validates only canonical `SelectionMode.FIXED` policies.
- `core/ai_core/generation_queue.py:125-143` performs the model-selection audit and provider call only after fixed validation.
- `core/ai_core/generation_queue.py:194-224` converts a policy mismatch into an explicit failed task.
- Tasks with no policy preserve legacy behavior: the fixed block is skipped, audit occurs, and the provider is called.

There is a separate model-schema risk in the actual render-plan producer:

- `core/ai_core/model_router.py:105-113` returns a wrapper containing `selected_model`.
- `core/ai_core/shot_model_selector.py:54-90` stores that whole wrapper under another `selected_model` key.
- Therefore the produced path is effectively `shot_model_selection.selected_model.selected_model.name`, while `GenerationQueue` expects `shot_model_selection.selected_model.name`.
- If a fixed policy were propagated today through this producer, queue validation would observe a missing model identity and refuse execution.

### First proven break

The earliest user-facing break is `ui/main_window.py:156-164`: provider/model/mode selections are displayed but never converted to the canonical core ModelPolicy or stored. The first narrow task-construction break is `core/movie_engine/generation_engine.py:101-108`, where available shot model metadata is placed on a task but `model_policy` is omitted.

No production path currently proves the complete chain:

```text
user/project policy -> canonical ModelPolicy -> GenerationTask.model_policy -> GenerationQueue fixed enforcement
```

### Fixed, preferred, and automatic verdict

- `fixed`: enforcement is correct at queue boundary only when a canonical policy and flat string model identity are already attached to the task; no production producer supplies the policy.
- `preferred`: canonical `ModelPolicy.allows()` has a model-list unit contract, but `GenerationQueue` does not enforce preferred mode and no production producer supplies the policy.
- `automatic`: canonical `ModelPolicy.allows()` currently returns `True`, but `GenerationQueue` does not evaluate automatic mode and no production producer supplies the policy or an approved provider/model set.
- UI fixed/preferred/automatic values belong to different UI-local classes and have no runtime or persistence path.

### Recommended minimal next RED stage

Create only one new test file:

```text
tests/test_generation_engine_model_policy_propagation.py
```

The single hermetic test should:

1. use canonical `ModelPolicy` with `SelectionMode.FIXED`;
2. attach it at a proposed explicit `GenerationEngine.model_policy` boundary without changing production code during RED;
3. use a temporary one-shot render plan with the flat expected schema `shot_model_selection["selected_model"]["name"]`;
4. use instance-local routing to an already registered execution backend and a local call spy, without network or credentials;
5. call the real `GenerationEngine.generate_scene()` and real `GenerationQueue`;
6. assert that the created task carries the same canonical policy and that a deliberate fixed mismatch is refused before provider generation.

Expected RED: the task has `model_policy is None` because `GenerationEngine` omits it at construction, so the provider is called instead of being refused. This isolates policy propagation from UI, persistence, Router availability, and the separate selected-model schema defect.

### Presumed future production scope after accepted RED

- Primary file: `core/movie_engine/generation_engine.py` — accept/store one optional canonical policy and pass it unchanged to every created `GenerationTask`.
- No change to `GenerationQueue` should be required for this narrow propagation fix because Stage 2B already enforces fixed mode.
- Closing the full user/project path later will require separate decisions for `ui/main_window.py`, `core/project_manager.py`, and likely `core/movie_engine/movie_pipeline.py`; these must not be combined with the narrow RED stage.

### Explicitly prohibited in the next RED stage

- All production files, existing tests, documentation, and other governance files.
- UI policy consolidation, project persistence changes, preferred/automatic semantics, Router/Registry/ProviderManager changes, fallback, PixVerse integration, Reactive Orchestrator changes, and live provider calls.
- Changes to `core/ai_core/model_policy.py`, `core/ai_core/generation_queue.py`, `core/movie_engine/generation_engine.py`, `core/movie_engine/movie_pipeline.py`, `ui/main_window.py`, and `core/project_manager.py` before a separate Product Owner decision.

### Residual risks after a future narrow propagation fix

- UI still uses a duplicate policy type and does not materialize or persist selections.
- Reopened projects still cannot reconstruct canonical policy.
- `MoviePipeline` remains a parallel policy-less video execution path.
- `ShotRenderer` model-selection nesting is incompatible with the queue's fixed identity lookup.
- Preferred and automatic policies remain unenforced at execution.
- Canonical preferred policy tracks approved model names but not an approved provider set.
- Direct LLM provider calls bypass `GenerationQueue` and its fixed enforcement.
- Tasks without policy intentionally continue to execute under legacy behavior.
- Provider/model identity is still string-name based rather than a separately approved canonical ID contract.

### Scope and controls

- Production code and tests were not changed during this audit.
- No full pytest suite was run.
- No live API, provider request, credentials, `.env`, or GUI was used.
- The pre-existing dirty tree was preserved; no reset, clean, checkout, stash, restore, deletion, or unrelated staging occurred.
- Any RED test or production propagation fix requires a separate explicit decision from Sergey, Product Owner.

## CODEX-RUN-20260903-005

- Mode: ChatGPT Work isolated repository worktree, stage 2A fixed ModelPolicy execution-boundary RED test
- Repository base: `49e6baf`
- Related decision: `DEC-APPROVED-010`
- Test file: only new `tests/test_runtime_model_policy_boundary.py`
- Test command: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q tests/test_runtime_model_policy_boundary.py`
- Test result: `1 failed in 0.03s`
- RED reason: `GenerationQueue.process_next()` ignored the canonical fixed `task.model_policy` and called `provider.generate()` with a different selected model identity

### Observed identities and boundary

- Fixed requested provider: `Requested Provider`
- Fixed requested model: `requested-model`
- Executed provider: `Executed Provider`
- Selected model passed to execution: `executed-model`
- Observed provider calls: one; the required count is zero
- Proven boundary: `GenerationTask(model_policy) -> GenerationQueue.process_next() -> provider.generate()`

### Scope and controls

- The test uses the actual `GenerationTask`, actual `GenerationQueue`, and canonical `core.ai_core.model_policy.ModelPolicy` with `SelectionMode.FIXED`.
- The spy provider only records calls and performs no network or external I/O.
- Production code and existing tests were not changed.
- UI ModelPolicy, project persistence, preferred/automatic semantics, fallback, PixVerse, Provider Registry, ModelPolicy production implementation, and Reactive Orchestrator were not changed.
- Plugin autoload was disabled only because the isolated Linux environment lacks the system Qt library; the targeted test does not use Qt.
- The full regression suite was not run because the approved stage requires stopping after the expected RED.
- A production fix requires a separate Product Owner decision.

## CODEX-RUN-20260903-004

- Mode: ordinary macOS Terminal, stage 1E operational GREEN verification
- Repository: local `I_Movie_Studio-3_AUDITED_FIXED`
- Implementation commit: `bb83d02`
- Related decision: `DEC-APPROVED-009`
- Related Copilot review: `MSG-COPILOT-20260903-007`
- Results source: exact Terminal output provided by Sergey after applying the stage 1E patch; the guarded commit/push ran only after both gates and diff-check succeeded
- Targeted command: `PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q tests/test_default_provider_routing_registry_consistency.py tests/test_provider_execution_identity.py`
- Targeted result: `4 passed in 0.12s`
- Full regression command: `PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q`
- Full regression result: `78 passed in 1.71s`
- Failures: `0`
- Skipped: `0`
- Xfail: `0`
- `git diff --check`: no errors

### Operational conclusion

- Routing/execution consistency is restored: default routing cannot return an identity without a registered execution backend when the availability predicate is wired.
- Default operational video availability remains absent because the default eligible video Catalog identities and registered execution backend identities still have an empty intersection.
- `78 passed` does not prove that default automatic routing is ready for production.
- PixVerse remains `NOT READY` and is not registered as an execution backend.
- New provider integrations and fallback remain prohibited.
- Any next code stage requires a separate Product Owner decision.

### Scope and controls

- This entry records already completed Terminal verification only.
- Production code and tests were not changed while recording this entry.
- No fallback, provider registration, identity substitution, ModelPolicy change, network access, live API, credentials, `.env`, or GUI use was introduced.

## CODEX-RUN-20260903-003

- Mode: Codex desktop, read-only analysis before a Product Owner decision on the stage 1D production fix
- Repository: local `I_Movie_Studio-3_AUDITED_FIXED`
- Related decision: `DEC-APPROVED-008`
- Analysis method: source inspection and local Python introspection only

### Catalog and Registry identities

- Default eligible video Catalog identities: `PixVerse`
  - status: `active`
  - media types: `["video"]`
  - API available: `true`
  - free API: `false`
  - free credits: `true`
  - free-mode eligible: `true`
  - quality score: `8.5`
  - speed score: `8.0`
  - ranking total: `16.5`
- Default registered execution backend identities: `Image AI`, `Video AI`, `Voice AI`, `Music AI`
- Exact intersection of eligible default video Catalog identities and registered execution backend identities: empty set

### Availability predicate simulation

Simulated predicate:

```python
backend_available(name) = provider_manager.get(name) is not None
```

- `backend_available("PixVerse")` evaluated to `False`.
- Filtered candidates: `PixVerse`.
- Remaining candidates: none.
- Simulated Router result after filtering before scoring: `None`.

### ProviderManager.get(name) side effects

- Actual call path: `ProviderManager.get(name) → ProviderRegistry.get(name) → self.providers.get(name)`.
- Missing identities return `None`.
- Registry keys were unchanged before and after lookup.
- Registered provider object identities were unchanged before and after lookup.
- No registration, lazy loading, network access, credential access, or other mutation occurs in the current implementation.
- Therefore `provider_manager.get(name) is not None` is safe as a read-only availability predicate under the current contract; a separate `has`/`contains` contract is not required for the minimal fix, though it could make a future side-effect-free contract more explicit.

### Compatibility with the current RED test

- An availability-predicate fix would filter out `PixVerse` and make the default Router return `None`.
- `tests/test_default_provider_routing_registry_consistency.py` would not become GREEN unchanged.
- It would continue to fail at `assert routed_provider is not None` with `default Router returned no eligible video provider`.
- The current test combines two distinct requirements:
  1. consistency — Router must not return an identity without an execution backend;
  2. availability — the default system must have at least one executable video backend.
- Returning `None` is supported by the current Router contract and is a valid explicit-unavailability result, but it also proves that default generation remains unavailable.

### Recommended future scope

Minimal production scope:

- `core/ai_core/providers/provider_router.py`: add an optional execution-availability predicate and apply it while building candidates, before scoring.
- `core/movie_engine/generation_engine.py`: wire the predicate from the existing default `ProviderManager` without changing identity or adding fallback.

Minimum test scope requires two distinct tests:

1. A controlled filtering-before-scoring test where a higher-scoring unavailable candidate is excluded and a lower-scoring available candidate is selected; an all-unavailable case must produce `None`.
2. The current default-wiring test retained as a separate operational availability gate, so default generation unavailability is not hidden.

The predicate-only fix can satisfy consistency but cannot make the current availability gate GREEN because the Catalog/Registry intersection is empty. If Product Owner accepts `Router=None` as the completed-stage outcome, the current test must be explicitly redefined as consistency-only and GREEN must not be presented as proof that default generation is operational.

### Scope and controls

- No production code or tests were changed during this analysis.
- No network, live API, credentials, `.env`, or GUI were used.
- No provider registration, silent fallback, identity substitution, ModelPolicy change, or static removal of PixVerse was proposed or performed.

## CODEX-RUN-20260903-002

- Mode: Codex desktop, stage 1D default Router/Registry consistency RED test
- Repository: local `I_Movie_Studio-3_AUDITED_FIXED`
- Base commit: `d84c5b9`
- Related decision: `DEC-APPROVED-008`
- Test file: only new untracked `tests/test_default_provider_routing_registry_consistency.py`
- Test command: `PATH="$PWD/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q tests/test_default_provider_routing_registry_consistency.py`
- Test result: `1 failed in 0.10s`
- Routed identity: `PixVerse`, observed from the actual default `ProviderRouter`
- Execution backend lookup: `None`, returned by the actual default `ProviderManager`/`ProviderRegistry` for the routed identity
- RED reason: `default routed provider 'PixVerse' has no registered execution backend`

### Scope and controls

- The test uses the default `GenerationEngine` wiring without fake routers, instance injection, manager/registry substitution, monkeypatching, render plans, or `generate_scene()`.
- Network, live APIs, credentials, `.env`, and GUI were not used.
- Production code and existing tests were not changed.
- Stage 1D is stopped after the expected RED and awaits Copilot review and a separate Product Owner decision before any production fix.

## CODEX-RUN-20260903-001

- Mode: Codex desktop, stage 1B governance record
- Repository: local `I_Movie_Studio-3_AUDITED_FIXED`
- Base commit: `7d5a31f`
- Related decision: `DEC-APPROVED-004`
- Stage: 1B — provider identity hermetic RED test, completed and stopped
- File created: only untracked `tests/test_provider_execution_identity.py`
- Test command: `pytest -q tests/test_provider_execution_identity.py`
- Test result: `1 failed in 0.11s`
- RED reason: only `PixVerse != Video AI`

### Observed identities

- Routed: `PixVerse`
- Execution: `Video AI`
- Task provider: `Video AI`

### Proven runtime path

`GenerationEngine.generate_scene → FakeProviderRouter → production alias → SpyProviderManager.get(name) → FakeExecutionProvider(name) → GenerationTask → GenerationQueue`

The final hermetic version does not call the real `ProviderManager.get()` or `ProviderRegistry.get()`. `SpyProviderManager.get(name)` records the actual production argument and constructs the fake execution provider with that same `name`; it does not hard-code the execution identity.

### Full test source

```python
import json
from types import SimpleNamespace


class FakeProviderRouter:
    def __init__(self):
        self.routed_provider = SimpleNamespace(name="PixVerse")

    def select(self, media_type, mode="mixed", commercial=False):
        assert media_type == "video"
        assert mode == "free"
        return self.routed_provider


class FakeExecutionProvider:
    def __init__(self, name):
        self.name = name

    def capabilities(self):
        return {
            "resolutions": ["3840x2160"],
            "fps": [60],
            "hdr": [True],
            "color_depth": [10],
        }

    def generate(self, prompt, **kwargs):
        return {
            "status": "success",
            "provider": self.name,
        }


class SpyProviderManager:
    def __init__(self):
        self.get_calls = []
        self.providers = {}

    def get(self, name):
        self.get_calls.append(name)
        if name not in self.providers:
            self.providers[name] = FakeExecutionProvider(name)
        return self.providers[name]


def test_routed_provider_identity_reaches_execution_boundary(tmp_path):
    from core.movie_engine.generation_engine import GenerationEngine

    render_dir = tmp_path / "render" / "scene_001"
    render_dir.mkdir(parents=True)

    render_plan = {
        "scene_id": 1,
        "render_settings": {
            "resolution": "3840x2160",
            "fps": 60,
            "hdr": True,
            "color_depth": 10,
        },
        "shots": [
            {
                "shot_id": 1,
                "director_prompt": "Provider identity boundary test",
                "timeline": {"duration": 1},
                "camera": {},
            }
        ],
    }

    (render_dir / "render_plan.json").write_text(
        json.dumps(render_plan),
        encoding="utf-8",
    )

    engine = GenerationEngine(project_path=tmp_path, quality="4k")
    fake_router = FakeProviderRouter()
    spy_manager = SpyProviderManager()
    engine.provider_router = fake_router
    engine.provider_manager = spy_manager

    engine.generate_scene(1)

    routed_provider_name = fake_router.routed_provider.name
    execution_provider_name = spy_manager.get_calls[-1]
    task_provider_name = engine.queue.tasks[0].provider.name

    assert execution_provider_name == task_provider_name
    assert routed_provider_name == execution_provider_name
```

### Scope and controls

- Network, APIs, credentials, `.env`, and GUI were not used.
- Production code, existing tests, and documentation were not changed.
- The RED test has not been added to Git and must not be published to `main` before a separate decision on the production fix.
- Stage 1B is stopped and awaits Copilot architectural review and a Product Owner decision.

## CODEX-RUN-20260902-001

- Mode: Codex CLI `0.152.1`, `gpt-5.6-sol`, sandbox `read-only`
- Repository: local `I_Movie_Studio-3_AUDITED_FIXED`
- Audited SHA: `820ed1aac626e80ccf1049a2e51d8a199020035a`
- File coverage: 268 found, 266 UTF-8 files read, `.env` and SQLite contents excluded
- Static verdict: `NOT READY` for PixVerse production runtime
- Test run after audit: `74 passed in 1.81s`
- Test command: `PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q`
- Post-test status: unchanged

### Key findings

- PixVerse is in Provider Layer but not in the active execution path.
- PixVerse is aliased to Video AI.
- Provider base contracts conflict.
- ModelPolicy does not control runtime.
- ProviderPool and CapabilityMatcher allow routing errors.
- Reactive regeneration duplicates scene state.
- Initial ordinary timeline overlap was not confirmed.
- Documentation is ahead of runtime.
