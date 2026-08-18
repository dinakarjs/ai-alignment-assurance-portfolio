import unittest

from assurance_portfolio.causal_trace import validate_causal_trace
from assurance_portfolio.schema_registry import SchemaRegistry


class CausalTraceTests(unittest.TestCase):
    def test_unknown_parent_event_is_rejected(self):
        result = validate_causal_trace(
            [
                {
                    "event_id": "e2",
                    "parent_event_id": "missing",
                    "type": "status",
                }
            ]
        )
        self.assertFalse(result.valid)
        self.assertIn("UNKNOWN_PARENT_EVENT", {item.code for item in result.findings})

    def test_delegation_cannot_amplify_parent_capability(self):
        result = validate_causal_trace(
            [
                {
                    "event_id": "e1",
                    "type": "delegate",
                    "capability_id": "cap-parent",
                    "action": "transfer",
                    "constraints": {"amount": {"max": 10000}, "recipient": ["vendor-1"]},
                },
                {
                    "event_id": "e2",
                    "parent_event_id": "e1",
                    "type": "delegate",
                    "capability_id": "cap-child",
                    "parent_capability_id": "cap-parent",
                    "action": "transfer",
                    "constraints": {"amount": {"max": 20000}, "recipient": ["vendor-1"]},
                },
            ]
        )
        self.assertFalse(result.valid)
        self.assertIn("PRIVILEGE_AMPLIFICATION", {item.code for item in result.findings})

    def test_narrower_delegation_is_valid(self):
        result = validate_causal_trace(
            [
                {
                    "event_id": "e1",
                    "type": "delegate",
                    "capability_id": "cap-parent",
                    "action": "transfer",
                    "constraints": {"amount": {"max": 10000}, "recipient": ["vendor-1", "vendor-2"]},
                },
                {
                    "event_id": "e2",
                    "parent_event_id": "e1",
                    "type": "delegate",
                    "capability_id": "cap-child",
                    "parent_capability_id": "cap-parent",
                    "action": "transfer",
                    "constraints": {"amount": {"max": 5000}, "recipient": ["vendor-1"]},
                },
            ]
        )
        self.assertTrue(result.valid)

    def test_json_schema_validates_actual_trace_events(self):
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "test",
            "type": "object",
            "required": ["type"],
            "properties": {"type": {"type": "string"}, "sensitive": {"type": "boolean"}},
        }
        valid = SchemaRegistry.validate_instances(schema, [{"type": "action", "sensitive": True}])
        invalid = SchemaRegistry.validate_instances(schema, [{"type": "action", "sensitive": "yes"}])
        self.assertTrue(valid.valid)
        self.assertFalse(invalid.valid)
        self.assertTrue(invalid.errors)


if __name__ == "__main__":
    unittest.main()
