import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from research.simulation.models import Scenario

BASE_PATH = Path(__file__).resolve().parents[2] / "experiments" / "configs" / "base_scenario.json"
BASE = json.loads(BASE_PATH.read_text(encoding="utf-8"))
SCHEMA = Scenario.model_json_schema()


def mutated(fn) -> dict:
    d = copy.deepcopy(BASE)
    fn(d)
    return d


def test_base_file_loads_and_round_trips() -> None:
    s = Scenario.model_validate_json(BASE_PATH.read_text(encoding="utf-8"))
    again = Scenario.model_validate_json(s.model_dump_json())
    assert again == s
    assert again.config_hash == s.config_hash


def test_base_file_valid_against_json_schema() -> None:
    Draft202012Validator(SCHEMA).validate(BASE)


def test_hash_is_stable_and_order_insensitive() -> None:
    s = Scenario.model_validate(BASE)
    assert len(s.config_hash) == 64
    shuffled = mutated(lambda d: d.update(links=d["links"][::-1], nodes=d["nodes"][::-1]))
    assert Scenario.model_validate(shuffled).config_hash == s.config_hash


def test_hash_changes_with_content() -> None:
    other = mutated(lambda d: d.update(seed=43))
    assert Scenario.model_validate(other).config_hash != Scenario.model_validate(BASE).config_hash


# Invalid inputs rejected by BOTH the JSON Schema and the pydantic model.
SCHEMA_VISIBLE = {
    "unknown_field": lambda d: d.update(bogus=1),
    "unknown_link_field": lambda d: d["links"][0].update(bogus=1),
    "zero_capacity": lambda d: d["links"][0].update(capacity_mbps=0),
    "negative_capacity": lambda d: d["links"][0].update(capacity_mbps=-5),
    "negative_delay": lambda d: d["links"][0].update(prop_delay_ms=-1),
    "negative_weight": lambda d: d["links"][0].update(weight=-0.1),
    "zero_buffer": lambda d: d["links"][0].update(buffer_pkts=0),
    "missing_capacity": lambda d: d["links"][0].pop("capacity_mbps"),
    "bad_schema_version": lambda d: d.update(schema_version="2.0"),
    "negative_seed": lambda d: d.update(seed=-1),
    "bad_traffic_kind": lambda d: d["traffic"].update(kind="burst"),
}


@pytest.mark.parametrize("name", SCHEMA_VISIBLE)
def test_invalid_rejected_by_schema_and_model(name: str) -> None:
    bad = mutated(SCHEMA_VISIBLE[name])
    assert list(Draft202012Validator(SCHEMA).iter_errors(bad)), "JSON Schema accepted it"
    with pytest.raises(ValidationError):
        Scenario.model_validate(bad)


# Cross-reference rules only the model can enforce.
CROSS_REF = {
    "duplicate_node_id": lambda d: d["nodes"].append({"id": "a"}),
    "duplicate_link_id": lambda d: d["links"].append(dict(d["links"][0])),
    "duplicate_flow_id": lambda d: d["flows"].append(dict(d["flows"][0])),
    "invalid_edge_unknown_endpoint": lambda d: d["links"][0].update(target="ghost"),
    "self_loop": lambda d: d["links"][0].update(target="a"),
    "flow_unknown_endpoint": lambda d: d["flows"][0].update(target="ghost"),
    "flow_same_endpoints": lambda d: d["flows"][0].update(target="a"),
    "flow_starts_after_end": lambda d: d["flows"][0].update(start_s=60.0),
    "failure_unknown_link": lambda d: d["failures"][0].update(link_id="nope"),
    "failure_after_end": lambda d: d["failures"][0].update(time_s=61.0),
}


@pytest.mark.parametrize("name", CROSS_REF)
def test_cross_reference_errors(name: str) -> None:
    with pytest.raises(ValidationError):
        Scenario.model_validate(mutated(CROSS_REF[name]))


def test_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValidationError):
        Scenario.model_validate_json(
            BASE_PATH.read_text(encoding="utf-8").replace('"capacity_mbps": 100.0', '"capacity_mbps": Infinity', 1)
        )


def test_models_are_frozen() -> None:
    s = Scenario.model_validate(BASE)
    with pytest.raises(ValidationError):
        s.seed = 1  # type: ignore[misc]
