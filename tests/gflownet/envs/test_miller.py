import common
import pytest
import torch

from gflownet.envs.crystals.miller import MillerIndices
from gflownet.utils.common import tfloat


@pytest.fixture
def hexa_rhombo():
    return MillerIndices(is_hexagonal_rhombohedral=True)


@pytest.fixture
def no_hexa_rhombo():
    return MillerIndices(is_hexagonal_rhombohedral=False)


@pytest.mark.parametrize(
    "state, state2proxy",
    [
        (
            [0, 0, 0],
            [-2.0, -2.0, -2.0],
        ),
        (
            [4, 4, 4],
            [2.0, 2.0, 2.0],
        ),
        (
            [2, 2, 2],
            [0.0, 0.0, 0.0],
        ),
        (
            [0, 2, 0],
            [-2.0, 0.0, -2.0],
        ),
        (
            [2, 1, 3],
            [0.0, -1.0, 1.0],
        ),
    ],
)
def test__state2proxy__returns_expected(
    hexa_rhombo, no_hexa_rhombo, state, state2proxy
):
    assert torch.equal(
        tfloat(state2proxy, device=hexa_rhombo.device, float_type=hexa_rhombo.float),
        hexa_rhombo.state2proxy(state),
    )
    assert torch.equal(
        tfloat(
            state2proxy, device=no_hexa_rhombo.device, float_type=no_hexa_rhombo.float
        ),
        no_hexa_rhombo.state2proxy(state),
    )


@pytest.mark.parametrize(
    "env_input, state, action, is_action_valid",
    [
        ("no_hexa_rhombo", [0, 0, 0], (0, 0, 0), True),
        ("no_hexa_rhombo", [2, 2, 2], (0, 0, 0), True),
        ("no_hexa_rhombo", [4, 4, 4], (0, 0, 0), True),
        ("no_hexa_rhombo", [3, 3, 2], (1, 0, 0), True),
        ("no_hexa_rhombo", [3, 3, 2], (0, 1, 0), True),
        ("no_hexa_rhombo", [3, 3, 2], (0, 0, 1), True),
        ("hexa_rhombo", [0, 0, 0], (0, 0, 0), False),
        ("hexa_rhombo", [2, 2, 2], (0, 0, 0), True),
        ("hexa_rhombo", [4, 4, 4], (0, 0, 0), False),
        ("hexa_rhombo", [3, 3, 2], (1, 0, 0), False),
        ("hexa_rhombo", [3, 3, 2], (0, 1, 0), False),
        ("hexa_rhombo", [3, 3, 2], (0, 0, 1), True),
    ],
)
def test_get_mask_invalid_actions_forward__masks_expected_actions(
    env_input, state, action, is_action_valid, request
):
    env = request.getfixturevalue(env_input)
    env.set_state(state, done=False)
    _, _, valid = env.step(action)
    assert is_action_valid == valid


def test__all_env_common__hexagonal_rhombohedral(hexa_rhombo):
    print("\n\nCommon tests for hexagonal or rhombohedral Miller indices\n")
    return common.test__all_env_common(hexa_rhombo)


def test__all_env_common__no_hexagonal_rhombohedral(no_hexa_rhombo):
    print("\n\nCommon tests for non-{hexagonal, rhombohedral} Miller indices\n")
    return common.test__all_env_common(no_hexa_rhombo)
