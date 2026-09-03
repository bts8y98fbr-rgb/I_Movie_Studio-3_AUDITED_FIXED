from core.ai_core.generation_queue import GenerationQueue, GenerationTask
from core.ai_core.model_policy import ModelPolicy, SelectionMode


class SpyProvider:
    def __init__(self, name):
        self.name = name
        self.generate_calls = []

    def generate(self, prompt, **kwargs):
        self.generate_calls.append((prompt, kwargs))
        return {"status": "success"}


class SpyAudit:
    def __init__(self):
        self.events = []

    def record(self, event, payload):
        self.events.append((event, payload))


def make_fixed_task(provider_name, selected_model_name, policy):
    return GenerationTask(
        task_type="video",
        prompt="Fixed policy boundary test",
        provider=SpyProvider(provider_name),
        metadata={
            "shot_model_selection": {
                "selected_model": {"name": selected_model_name},
            },
        },
        model_policy=policy,
    )


def test_fixed_policy_refuses_mismatch_before_audit_and_generation():
    policy = ModelPolicy(
        provider="Requested Provider",
        model="requested-model",
        mode=SelectionMode.FIXED,
    )
    task = make_fixed_task(
        provider_name="Executed Provider",
        selected_model_name="executed-model",
        policy=policy,
    )
    audit = SpyAudit()
    queue = GenerationQueue()
    queue._audit = lambda queued_task: audit
    queue.add_task(task)

    queue.process_next()

    assert task.provider.generate_calls == []
    assert task.status == "failed"
    assert task.result["status"] == "failed"
    assert "policy" in task.result["error"].lower()
    assert "model_selection" not in {
        event for event, _payload in audit.events
    }


def test_fixed_policy_exact_match_allows_one_provider_call():
    policy = ModelPolicy(
        provider="Requested Provider",
        model="requested-model",
        mode=SelectionMode.FIXED,
    )
    task = make_fixed_task(
        provider_name="Requested Provider",
        selected_model_name="requested-model",
        policy=policy,
    )
    queue = GenerationQueue()
    queue.add_task(task)

    queue.process_next()

    assert len(task.provider.generate_calls) == 1
    assert task.status == "done"
    assert task.result["status"] == "success"
