from agentserial.models import OrderingConstraint
from agentserial.ordering import project_order


def test_projection_preserves_reachability_through_removed_operation() -> None:
    constraints = [
        OrderingConstraint(before="prepare", after="failed-write"),
        OrderingConstraint(before="failed-write", after="commit"),
    ]

    assert project_order({"prepare", "failed-write", "commit"}, constraints, {"prepare", "commit"}) == {
        ("prepare", "commit")
    }


def test_projection_keeps_transitive_order_between_retained_operations() -> None:
    constraints = [
        OrderingConstraint(before="a", after="b"),
        OrderingConstraint(before="b", after="c"),
    ]

    assert project_order({"a", "b", "c"}, constraints, {"a", "b", "c"}) == {
        ("a", "b"),
        ("a", "c"),
        ("b", "c"),
    }
