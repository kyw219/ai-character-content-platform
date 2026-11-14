import copy
import unittest

from app.audit import build_audit_event
from app.policy import PolicyViolation, validate_request
from app.quality import QualityResult, decide_next_step
from app.workflow import build_workflow


def template():
    return {
        "3": {"inputs": {"seed": 1}},
        "6": {"inputs": {"text": "old"}},
        "7": {"inputs": {"text": "old negative"}},
        "10": {"inputs": {"strength_model": 0.1, "strength_clip": 0.1}},
    }


class PolicyTests(unittest.TestCase):
    def test_accepts_synthetic_character_request(self):
        validate_request("fictional editorial portrait", "character_01", True, True)

    def test_requires_synthetic_confirmation(self):
        with self.assertRaises(PolicyViolation):
            validate_request("fictional editorial portrait", "character_01", False, True)

    def test_requires_rights_confirmation(self):
        with self.assertRaises(PolicyViolation):
            validate_request("fictional editorial portrait", "character_01", True, False)

    def test_rejects_real_person_requests(self):
        with self.assertRaises(PolicyViolation):
            validate_request("portrait of a real person", "character_01", True, True)

    def test_rejects_invalid_character_id(self):
        with self.assertRaises(PolicyViolation):
            validate_request("fictional editorial portrait", "bad id", True, True)


class WorkflowTests(unittest.TestCase):
    def test_injects_trigger_token_once(self):
        result = build_workflow(template(), prompt="editorial portrait", trigger_token="identity-token")
        self.assertEqual(result["6"]["inputs"]["text"], "identity-token, editorial portrait")

    def test_does_not_duplicate_existing_trigger(self):
        result = build_workflow(template(), prompt="IDENTITY-TOKEN, portrait", trigger_token="identity-token")
        self.assertEqual(result["6"]["inputs"]["text"].casefold().count("identity-token"), 1)

    def test_sets_seed_strength_and_negative_prompt(self):
        result = build_workflow(
            template(), prompt="editorial portrait", negative_prompt="artifacts", seed=99, lora_strength=1.2
        )
        self.assertEqual(result["3"]["inputs"]["seed"], 99)
        self.assertEqual(result["7"]["inputs"]["text"], "artifacts")
        self.assertEqual(result["10"]["inputs"]["strength_model"], 1.2)
        self.assertEqual(result["10"]["inputs"]["strength_clip"], 1.2)

    def test_does_not_mutate_template(self):
        original = template()
        snapshot = copy.deepcopy(original)
        build_workflow(original, prompt="editorial portrait")
        self.assertEqual(original, snapshot)


class QualityTests(unittest.TestCase):
    def test_accepts_passing_candidate(self):
        self.assertEqual(decide_next_step(QualityResult(True), 0).action, "accept")

    def test_revises_failed_candidate_with_targeted_prompt(self):
        decision = decide_next_step(QualityResult(False, ("hand artifact",), "fix hand anatomy"), 1)
        self.assertEqual(decision.action, "revise")
        self.assertEqual(decision.next_prompt, "fix hand anatomy")

    def test_escalates_after_revision_limit(self):
        decision = decide_next_step(QualityResult(False, ("identity drift",), "restore identity"), 3)
        self.assertEqual(decision.action, "manual_review")


class AuditTests(unittest.TestCase):
    def test_hashes_prompt_instead_of_storing_raw_text(self):
        event = build_audit_event(
            job_id="job-1",
            character_id="character_01",
            prompt="private creative prompt",
            workflow=template(),
            seed=42,
            lora_strength=0.8,
        )
        self.assertNotIn("prompt", event)
        self.assertEqual(len(event["prompt_sha256"]), 64)

    def test_audit_event_contains_reproducibility_fields(self):
        event = build_audit_event(
            job_id="job-1",
            character_id="character_01",
            prompt="private creative prompt",
            workflow=template(),
            seed=42,
            lora_strength=0.8,
        )
        self.assertEqual(event["seed"], 42)
        self.assertEqual(event["lora_strength"], 0.8)
        self.assertEqual(len(event["workflow_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
