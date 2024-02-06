import common
import numpy as np
import pytest
import torch
from torch.distributions import Bernoulli, Beta

from gflownet.envs.cube import ContinuousCubeSingleDimIncrement
from gflownet.utils.common import tbool, tfloat


@pytest.fixture
def cube1d():
    return ContinuousCubeSingleDimIncrement(n_dim=1, n_comp=3, min_incr=0.1)


@pytest.fixture
def cube2d():
    return ContinuousCubeSingleDimIncrement(n_dim=2, n_comp=3, min_incr=0.1)


@pytest.mark.parametrize(
    "action_space",
    [
        [
            (0.0, 0.0, 0.0),
            (np.inf, np.inf, np.inf),
        ],
    ],
)
def test__get_action_space__returns_expected(cube2d, action_space):
    env = cube2d
    assert action_space == env.action_space


@pytest.mark.parametrize("env", ["cube1d", "cube2d"])
def test__get_policy_output__fixed_as_expected(env, request):
    env = request.getfixturevalue(env)
    policy_outputs = torch.unsqueeze(env.fixed_policy_output, 0)
    params = env.fixed_distr_params
    policy_output__as_expected(env, policy_outputs, params)


@pytest.mark.parametrize("env", ["cube1d", "cube2d"])
def test__get_policy_output__random_as_expected(env, request):
    env = request.getfixturevalue(env)
    policy_outputs = torch.unsqueeze(env.random_policy_output, 0)
    params = env.random_distr_params
    policy_output__as_expected(env, policy_outputs, params)


def policy_output__as_expected(env, policy_outputs, params):
    assert torch.all(
        env._get_policy_betas_weights(policy_outputs) == params["beta_weights"]
    )
    assert torch.all(
        env._get_policy_betas_alpha(policy_outputs)
        == env._beta_params_to_policy_outputs("alpha", params)
    )
    assert torch.all(
        env._get_policy_betas_beta(policy_outputs)
        == env._beta_params_to_policy_outputs("beta", params)
    )
    assert torch.all(
        env._get_policy_source_logit(policy_outputs)
        == torch.logit(torch.tensor(params["bernoulli_bts_prob"]))
    )


@pytest.mark.parametrize("env", ["cube1d", "cube2d"])
def test__mask_forward__returns_all_true_if_done(env, request):
    env = request.getfixturevalue(env)
    # Sample states
    states = env.get_uniform_terminating_states(100)
    # Iterate over state and test
    for state in states:
        env.set_state(state, done=True)
        mask = env.get_mask_invalid_actions_forward()
        assert all(mask)


@pytest.mark.parametrize("env", ["cube1d", "cube2d"])
def test__mask_backward__returns_all_true_except_eos_if_done(env, request):
    env = request.getfixturevalue(env)
    # Sample states
    states = env.get_uniform_terminating_states(100)
    # Iterate over state and test
    for state in states:
        env.set_state(state, done=True)
        mask = env.get_mask_invalid_actions_backward()
        assert sum(mask) == len(mask) - 1
        assert not mask[env.MASK_IDX_EOS]


@pytest.mark.parametrize(
    "state, mask_expected",
    [
        (
            [-1.0, 0, -1],
            [False, True, True, True, True, False],
        ),
        (
            [0.5, 0, -1],
            [False, True, True, True, False, False],
        ),
        (
            [0.9, 0, -1],
            [False, True, True, True, False, False],
        ),
        (
            [0.95, 0, -1],
            [False, True, True, True, False, True],
        ),
        (
            [-1.0, 1, 0],
            [True, False, True, False, True, True],
        ),
        (
            [0.5, 1, 0],
            [True, False, True, True, True, True],
        ),
        (
            [-1.0, 2, 0],
            [True, True, False, True, True, False],
        ),
    ],
)
def test__mask_forward__1d__returns_expected(cube1d, state, mask_expected):
    #
    env = cube1d
    mask = env.get_mask_invalid_actions_forward(state)
    assert mask == mask_expected


@pytest.mark.parametrize(
    "state, mask_expected",
    [
        (
            [-1.0, -1.0, 0, -1],
            [False, True, True, True, True, False, False],
        ),
        (
            [0.5, -1.0, 0, -1],
            [False, True, True, True, True, False, False],
        ),
        (
            [0.0, 0.0, 0, -1],
            [False, True, True, True, False, False, False],
        ),
        (
            [0.9, 95, 0, -1],
            [False, True, True, True, False, False, True],
        ),
        (
            [0.93, 95, 0, -1],
            [False, True, True, True, False, True, True],
        ),
        (
            [-1.0, -1.0, 1, 0],
            [True, False, True, False, True, True, True],
        ),
        (
            [-1.0, 0.0, 1, 1],
            [True, False, True, True, True, True, True],
        ),
        (
            [0.0, 0.0, 2, 0],
            [True, True, False, True, True, False, True],
        ),
        (
            [-1.0, 0.9, 2, 1],
            [True, True, False, True, True, True, False],
        ),
    ],
)
def test__mask_forward__2d__returns_expected(cube2d, state, mask_expected):
    env = cube2d
    mask = env.get_mask_invalid_actions_forward(state)
    assert mask == mask_expected


@pytest.mark.parametrize(
    "state, mask_expected",
    [
        (
            [-1.0, 0, -1],
            [True, True, True, True, True, True],
        ),
        (
            [0.0, 0, -1],
            [True, True, False, True, True, False],
        ),
        (
            [0.09, 0, -1],
            [True, True, False, True, True, False],
        ),
        (
            [0.9, 0, -1],
            [True, True, False, True, True, False],
        ),
        (
            [-1.0, 1, 0],
            [False, True, True, True, True, False],
        ),
        (
            [0.5, 1, 0],
            [False, True, True, True, True, False],
        ),
        (
            [0.0, 2, 0],
            [True, False, True, False, True, True],
        ),
        (
            [0.09, 2, 0],
            [True, False, True, False, True, True],
        ),
        (
            [0.1, 2, 0],
            [True, False, True, True, True, True],
        ),
        (
            [0.9, 2, 0],
            [True, False, True, True, True, True],
        ),
    ],
)
def test__mask_backward__1d__returns_expected(cube1d, state, mask_expected):
    env = cube1d
    mask = env.get_mask_invalid_actions_backward(state)
    assert mask == mask_expected


@pytest.mark.parametrize(
    "state, mask_expected",
    [
        (
            [-1.0, -1.0, 0, -1],
            [True, True, True, True, True, True, True],
        ),
        (
            [0.0, -1.0, 0, -1],
            [True, True, False, True, True, False, True],
        ),
        (
            [0.09, 0.0, 0, -1],
            [True, True, False, True, True, False, False],
        ),
        (
            [0.9, 0.95, 0, -1],
            [True, True, False, True, True, False, False],
        ),
        (
            [0.9, -1.0, 1, 0],
            [False, True, True, True, True, False, True],
        ),
        (
            [0.5, 0.09, 1, 1],
            [False, True, True, True, True, True, False],
        ),
        (
            [0.0, -1.0, 2, 0],
            [True, False, True, False, True, True, True],
        ),
        (
            [0.5, 0.09, 2, 1],
            [True, False, True, False, True, True, True],
        ),
        (
            [0.1, -1.0, 2, 0],
            [True, False, True, True, True, True, True],
        ),
        (
            [0.9, 0.5, 2, 1],
            [True, False, True, True, True, True, True],
        ),
    ],
)
def test__mask_backward__2d__returns_expected(cube2d, state, mask_expected):
    env = cube2d
    mask = env.get_mask_invalid_actions_backward(state)
    assert mask == mask_expected


@pytest.mark.parametrize(
    "state, increments_rel, state_expected",
    [
        ([0.3], [0.0], [0.4]),
        ([0.5], [0.0], [0.6]),
        ([0.0], [0.1794], [0.26146]),
        ([0.0], [0.9589], [0.96301]),
        ([0.3], [1.0], [1.0]),
        ([0.5], [1.0], [1.0]),
        ([0.3], [0.5], [0.7]),
        ([0.5], [0.5], [0.8]),
        ([0.27], [0.12], [0.4456]),
        ([0.85], [0.76], [0.988]),
    ],
)
def test__relative_to_absolute_increments__2d_forward__returns_expected(
    cube2d, state, increments_rel, state_expected
):
    env = cube2d
    # Convert to tensors
    states = tfloat([state], float_type=env.float, device=env.device)
    increments_rel = tfloat([increments_rel], float_type=env.float, device=env.device)
    states_expected = tfloat([state_expected], float_type=env.float, device=env.device)
    # Get absolute increments
    increments_abs = env.relative_to_absolute_increments(
        states, increments_rel, is_backward=False
    )
    states_next = states + increments_abs
    assert torch.all(torch.isclose(states_next, states_expected))


@pytest.mark.parametrize(
    "state, increments_rel, state_expected",
    [
        ([1.0], [0.0], [0.9]),
        ([1.0], [1.0], [0.0]),
        ([1.0], [0.1794], [0.73854]),
        ([1.0], [0.9589], [0.03699]),
        ([0.3], [0.0], [0.2]),
        ([0.5], [0.0], [0.4]),
        ([0.3], [1.0], [0.0]),
        ([0.5], [1.0], [0.0]),
    ],
)
def test__relative_to_absolute_increments__2d_backward__returns_expected(
    cube2d, state, increments_rel, state_expected
):
    env = cube2d
    # Convert to tensors
    states = tfloat([state], float_type=env.float, device=env.device)
    increments_rel = tfloat([increments_rel], float_type=env.float, device=env.device)
    states_expected = tfloat([state_expected], float_type=env.float, device=env.device)
    # Get absolute increments
    increments_abs = env.relative_to_absolute_increments(
        states, increments_rel, is_backward=True
    )
    states_next = states - increments_abs
    assert torch.all(torch.isclose(states_next, states_expected))


@pytest.mark.parametrize(
    "state, action, state_expected",
    [
        # Valid actions
        ([-1.0, -1.0, 0, -1], (0, 0, 0), [-1.0, -1.0, 1, 0]),
        ([-1.0, -1.0, 0, -1], (0, 1, 0), [-1.0, -1.0, 1, 1]),
        ([0.3, 0.5, 0, -1], (np.inf, np.inf, np.inf), [0.3, 0.5, 0, -1]),
        ([-1.0, -1.0, 1, 0], (1, 0.0, 1), [0.0, -1.0, 2, 0]),
        ([-1.0, -1.0, 1, 1], (1, 1.0, 1), [-1.0, 1.0, 2, 1]),
        ([0.0, 0.0, 1, 0], (1, 0.1794, 0), [0.1794, 0.0, 2, 0]),
        ([0.0, 0.0, 1, 1], (1, 0.9589, 0), [0.0, 0.9589, 2, 1]),
        ([0.3, 0.5, 1, 0], (1, 0.5, 0), [0.8, 0.5, 2, 0]),
        ([0.3, 0.5, 1, 1], (1, 0.5, 0), [0.3, 1.0, 2, 1]),
        ([0.4456, 0.85, 2, 0], (2, 0, 0), [0.4456, 0.85, 0, -1]),
        ([0.27, 0.988, 2, 1], (2, 1, 0), [0.27, 0.988, 0, -1]),
        # Invalid actions
        ([-1.0, -1.0, 0, -1], (0, 2, 0), [-1.0, -1.0, 0, -1]),
        ([-1.0, -1.0, 0, -1], (1, 0.5, 0), [-1.0, -1.0, 0, -1]),
        ([-1.0, -1.0, 0, -1], (2, 0, 0), [-1.0, -1.0, 0, -1]),
        ([-1.0, -1.0, 0, -1], (np.inf, np.inf, np.inf), [-1.0, -1.0, 0, -1]),
        ([0.95, 0.95, 0, -1], (0, 0, 0), [0.95, 0.95, 0, -1]),
        ([0.3, 0.5, 1, 0], (0, 0, 0), [0.3, 0.5, 1, 0]),
        ([0.3, 0.5, 1, 0], (2, 0, 0), [0.3, 0.5, 1, 0]),
        ([0.3, 0.5, 1, 0], (1, 0.8, 0), [0.3, 0.5, 1, 0]),
        ([0.3, 0.5, 1, 0], (np.inf, np.inf, np.inf), [0.3, 0.5, 1, 0]),
        ([0.3, 0.5, 2, 0], (0, 0, 0), [0.3, 0.5, 2, 0]),
        ([0.3, 0.5, 2, 0], (1, 0.3, 0), [0.3, 0.5, 2, 0]),
        ([0.3, 0.5, 2, 0], (2, 1, 0), [0.3, 0.5, 2, 0]),
        ([0.3, 0.5, 2, 0], (np.inf, np.inf, np.inf), [0.3, 0.5, 2, 0]),
    ],
)
def test__step_forward__2d__returns_expected(cube2d, state, action, state_expected):
    env = cube2d
    env.set_state(state)
    state_new, action, valid = env.step(action)
    assert env.isclose(state_new, state_expected)


@pytest.mark.parametrize(
    "state, action, state_expected",
    [
        # Valid actions
        ([0.3, 0.5, 0, -1], (2, 0, 0), [0.3, 0.5, 2, 0]),
        ([0.3, 0.5, 0, -1], (2, 1, 0), [0.3, 0.5, 2, 1]),
        ([-1.0, -1.0, 1, 0], (0, 0, 0), [-1.0, -1.0, 0, -1]),
        ([-1.0, -1.0, 1, 1], (0, 1, 0), [-1.0, -1.0, 0, -1]),
        ([0.3, 0.5, 2, 0], (1, 0.1, 0), [0.2, 0.5, 1, 0]),
        ([0.3, 0.5, 2, 1], (1, 0.1, 0), [0.3, 0.4, 1, 1]),
        ([0.3, 0.5, 2, 0], (1, 0.3, 0), [0.0, 0.5, 1, 0]),
        ([0.3, 0.5, 2, 1], (1, 0.5, 0), [0.3, 0.0, 1, 1]),
        ([0.3, 0.5, 2, 0], (1, 0.3, 1), [-1.0, 0.5, 1, 0]),
        ([0.3, 0.5, 2, 1], (1, 0.5, 1), [0.3, -1.0, 1, 1]),
        # Invalid actions
        ([-1.0, -1.0, 0, -1], (0, 0, 0), [-1.0, -1.0, 0, -1]),
        ([-1.0, -1.0, 0, -1], (1, 0.5, 0), [-1.0, -1.0, 0, -1]),
        ([-1.0, -1.0, 0, -1], (2, 0, 0), [-1.0, -1.0, 0, -1]),
        ([-1.0, -1.0, 0, -1], (np.inf, np.inf, np.inf), [-1.0, -1.0, 0, -1]),
        ([0.3, 0.5, 0, -1], (2, 2, 0), [0.3, 0.5, 0, -1]),
        ([0.3, 0.5, 1, 0], (0, 1, 0), [0.3, 0.5, 1, 0]),
        ([0.3, 0.5, 1, 0], (1, 0.1, 0), [0.3, 0.5, 1, 0]),
        ([0.3, 0.5, 1, 0], (1, 0.1, 1), [0.3, 0.5, 1, 0]),
        ([0.3, 0.5, 1, 0], (2, 0, 1), [0.3, 0.5, 1, 0]),
        ([0.3, 0.5, 1, 0], (np.inf, np.inf, np.inf), [0.3, 0.5, 1, 0]),
        ([0.3, 0.5, 2, 0], (0, 0, 0), [0.3, 0.5, 2, 0]),
        ([0.3, 0.5, 2, 0], (1, 0.6, 0), [0.3, 0.5, 2, 0]),
        ([0.3, 0.5, 2, 0], (2, 0, 0), [0.3, 0.5, 2, 0]),
        ([0.3, 0.5, 2, 0], (np.inf, np.inf, np.inf), [0.3, 0.5, 2, 0]),
    ],
)
def test__step_backward__2d__returns_expected(cube2d, state, action, state_expected):
    env = cube2d
    env.set_state(state)
    state_new, action, valid = env.step_backwards(action)
    assert env.isclose(state_new, state_expected)


@pytest.mark.parametrize(
    "states",
    [
        [[-1.0, 1, 0], [0.0, 1, 0], [0.3, 1, 0], [0.27, 1, 0], [0.56, 1, 0]],
        [[0.12, 1, 0], [0.56, 1, 0], [0.9, 1, 0], [0.0, 1, 0], [0.16, 1, 0]],
        [[0.05, 1, 0], [0.56, 1, 0], [0.85, 1, 0], [0.2, 1, 0], [0.01, 1, 0]],
        [[0.0, 1, 0], [0.0, 1, 0], [0.3, 1, 0], [0.27, 1, 0], [0.56, 1, 0]],
        [[0.12, 1, 0], [0.56, 1, 0], [0.9, 1, 0], [0.0, 1, 0], [0.16, 1, 0]],
    ],
)
def test__sample_increments_forward__1d__returns_expected(cube1d, states):
    env = cube1d
    n_states = len(states)

    # Get masks
    masks = tbool(
        [env.get_mask_invalid_actions_forward(s) for s in states], device=env.device
    )
    # Define Beta distribution with low variance and get confident range
    n_samples = 10000
    alpha = 10.0
    alphas = alpha * torch.ones(n_samples)
    beta = 1.0
    betas = beta * torch.ones(n_samples)
    beta_distr = Beta(alphas, betas)
    samples = beta_distr.sample()
    mean_incr_rel = 0.9 * samples.mean()
    min_incr_rel = 0.9 * samples.min()
    max_incr_rel = 1.1 * samples.max()

    # Estimate confident intervals of absolute actions
    states_torch = tfloat(states, float_type=env.float, device=env.device)[:, :1]
    is_source = torch.all(states_torch == -1.0, dim=1)
    is_near_edge = states_torch > 1.0 - env.min_incr
    increments_min = torch.full_like(
        states_torch, min_incr_rel, dtype=env.float, device=env.device
    )
    increments_max = torch.full_like(
        states_torch, max_incr_rel, dtype=env.float, device=env.device
    )
    increments_min[~is_source] = env.relative_to_absolute_increments(
        states_torch[~is_source], increments_min[~is_source], is_backward=False
    )
    increments_max[~is_source] = env.relative_to_absolute_increments(
        states_torch[~is_source], increments_max[~is_source], is_backward=False
    )

    # Reconfigure environment
    env.n_comp = 1

    # Build policy outputs
    params = env.fixed_distr_params
    params["beta_alpha"] = alpha
    params["beta_beta"] = beta
    params["bernoulli_eos_prob"] = 0.0
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))
    # Sample actions
    actions, _ = env.sample_actions_batch(
        policy_outputs, masks, states, is_backward=False
    )
    actions_tensor = tfloat(actions, float_type=env.float, device=env.device)
    assert torch.all(actions_tensor[:, 1] >= increments_min[:, 0])
    assert torch.all(actions_tensor[:, 1] <= increments_max[:, 0])


@pytest.mark.parametrize(
    "states, force_bts",
    [
        (
            [[1.0, 2, 0], [1.0, 2, 0], [0.3, 2, 0], [0.27, 2, 0], [0.56, 2, 0]],
            [False, False, False, False, False],
        ),
        (
            [[0.12, 2, 0], [0.56, 2, 0], [0.9, 2, 0], [0.0, 2, 0], [0.16, 2, 0]],
            [False, False, False, False, False],
        ),
        (
            [[0.05, 2, 0], [0.56, 2, 0], [0.95, 2, 0], [0.2, 2, 0], [0.01, 2, 0]],
            [False, False, False, False, False],
        ),
        (
            [[0.0001, 2, 0], [0.001, 2, 0], [0.3, 2, 0], [0.27, 2, 0], [0.56, 2, 0]],
            [False, False, False, True, False],
        ),
        (
            [[0.12, 2, 0], [0.56, 2, 0], [0.9, 2, 0], [1.0, 2, 0], [0.16, 2, 0]],
            [False, True, True, True, False],
        ),
        (
            [[0.05, 2, 0], [0.56, 2, 0], [0.95, 2, 0], [0.92, 2, 0], [0.01, 2, 0]],
            [False, False, False, True, True],
        ),
    ],
)
def test__sample_actions_backward__1d__returns_expected(cube1d, states, force_bts):
    env = cube1d
    n_states = len(states)
    force_bts = tbool(force_bts, device=env.device)
    # Get masks
    masks = tbool(
        [env.get_mask_invalid_actions_backward(s) for s in states], device=env.device
    )
    states_torch = tfloat(states, float_type=env.float, device=env.device)[:, :1]
    # Define Beta distribution with low variance and get confident range
    n_samples = 10000
    alpha = 10
    alphas = alpha * torch.ones(n_samples)
    beta = 1.0
    betas = beta * torch.ones(n_samples)
    beta_distr = Beta(alphas, betas)
    samples = beta_distr.sample()
    mean_incr_rel = 0.9 * samples.mean()
    min_incr_rel = 0.9 * samples.min()
    max_incr_rel = 1.1 * samples.max()
    # Define Bernoulli parameters for BTS with deterministic probability
    prob_force_bts = 1.0
    prob_force_nobts = 0.0
    # Estimate confident intervals of absolute actions
    increments_min = torch.full_like(
        states_torch, min_incr_rel, dtype=env.float, device=env.device
    )
    increments_max = torch.full_like(
        states_torch, max_incr_rel, dtype=env.float, device=env.device
    )
    increments_min = env.relative_to_absolute_increments(
        states_torch, increments_min, is_backward=True
    )
    increments_max = env.relative_to_absolute_increments(
        states_torch, increments_max, is_backward=True
    )
    # Get BTS actions
    is_near_edge = states_torch < env.min_incr
    is_bts_forced = torch.any(is_near_edge, dim=1)
    is_bts = torch.logical_or(is_bts_forced, force_bts)
    increments_min[is_bts] = states_torch[is_bts]
    increments_max[is_bts] = states_torch[is_bts]
    # Reconfigure environment
    env.n_comp = 1
    # Build policy outputs
    params = env.fixed_distr_params
    params["beta_alpha"] = alpha
    params["beta_beta"] = beta
    params["bernoulli_bts_prob"] = prob_force_nobts
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))
    policy_outputs[force_bts, -3] = torch.logit(torch.tensor(prob_force_bts))
    # Sample actions
    actions, _ = env.sample_actions_batch(
        policy_outputs, masks, states, is_backward=True
    )
    actions_tensor = tfloat(actions, float_type=env.float, device=env.device)
    actions_bts = actions_tensor[:, 1] == states_torch[:, 0]
    assert torch.all(actions_bts == is_bts)
    assert torch.all(actions_tensor[:, 1] >= increments_min[:, 0])
    assert torch.all(actions_tensor[:, 1] <= increments_max[:, 0])


@pytest.mark.parametrize(
    "states, actions",
    [
        (
            [[0.1, 0.2, 0, -1], [0.3, 0.5, 0, -1], [0.93, 0.95, 0, -1]],
            [
                [np.inf, np.inf, np.inf],
                [np.inf, np.inf, np.inf],
                [np.inf, np.inf, np.inf],
            ],
        ),
        (
            [[1.0, 1.0, 0, -1], [0.01, 0.01, 0, -1], [0.001, 0.1, 0, -1]],
            [
                [np.inf, np.inf, np.inf],
                [np.inf, np.inf, np.inf],
                [np.inf, np.inf, np.inf],
            ],
        ),
    ],
)
def test__get_logprobs_forward__2d__eos_actions_return_expected(
    cube2d, states, actions
):
    """
    The only valid action from 'near-edge' states is EOS, thus the the log probability
    should be zero, regardless of the action and the policy outputs
    """
    env = cube2d
    n_states = len(states)
    states_torch = tfloat(states, float_type=env.float, device=env.device)[:, :2]
    actions = tfloat(actions, float_type=env.float, device=env.device)
    # Get masks
    masks = tbool(
        [env.get_mask_invalid_actions_forward(s) for s in states], device=env.device
    )
    # Get EOS forced
    is_near_edge = states_torch > 1.0 - env.min_incr
    is_eos_forced = torch.any(is_near_edge, dim=1)
    # Define Bernoulli parameter for EOS
    prob_eos = 0.5
    distr_eos = Bernoulli(probs=prob_eos)
    logprob_eos = distr_eos.log_prob(torch.tensor(1.0))
    # Build policy outputs
    params = env.fixed_distr_params
    params["bernoulli_eos_prob"] = prob_eos
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))
    # Get log probs
    logprobs = env.get_logprobs(
        policy_outputs, actions, masks, states_torch, is_backward=False
    )
    assert torch.all(logprobs[is_eos_forced] == 0.0)
    assert torch.all(torch.isclose(logprobs[~is_eos_forced], logprob_eos, atol=1e-6))


@pytest.mark.parametrize(
    "states, actions",
    [
        (
            [[0.1, 0.2, 0, -1], [0.3, 0.5, 0, -1], [0.90, 0.90, 0, -1]],
            [
                [0, 0, 0],
                [0, 1, 0],
                [0, 0, 0],
            ],
        ),
        (
            [[0.5, 0.5, 0, -1], [0.01, 0.01, 0, -1], [0.001, 0.1, 0, -1]],
            [
                [0, 1, 0],
                [0, 0, 0],
                [0, 1, 0],
            ],
        ),
    ],
)
def test__get_logprobs_forward__2d__all_actions_from_source_uniform_policy_prob1(
    cube2d, states, actions
):
    """
    With Uniform increment policy, selecting either dimension must have the same
    probability when both are valid
    """
    env = cube2d
    n_states = len(states)
    states_torch = tfloat(states, float_type=env.float, device=env.device)
    actions = tfloat(actions, float_type=env.float, device=env.device)
    # Get masks
    masks = tbool(
        [env.get_mask_invalid_actions_forward(s) for s in states], device=env.device
    )

    # Build policy outputs
    params = env.fixed_distr_params
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))

    # Get log probs
    logprobs = env.get_logprobs(
        policy_outputs, actions, masks, states_torch, is_backward=False
    )
    assert torch.all(torch.isclose(logprobs, logprobs[0], atol=1e-6))


@pytest.mark.parametrize(
    "states, actions",
    [
        (
            [[0.1, 0.2, 2, 0], [0.3, 0.5, 2, 1], [0.90, 0.90, 2, 0]],
            [
                [2, 0, 0],
                [2, 1, 0],
                [2, 0, 0],
            ],
        ),
        (
            [[0.5, 0.5, 2, 1], [0.01, 0.01, 2, 0], [0.001, 0.1, 2, 1]],
            [
                [2, 1, 0],
                [2, 0, 0],
                [2, 1, 0],
            ],
        ),
    ],
)
def test__get_logprobs_forward__2d__all_deselect_actions_prob1(cube2d, states, actions):
    """
    When deselect actions are valid, they are the only valid actions and so their
    logprobs should always be 0.
    """
    env = cube2d
    n_states = len(states)
    states_torch = tfloat(states, float_type=env.float, device=env.device)
    actions = tfloat(actions, float_type=env.float, device=env.device)
    # Get masks
    masks = tbool(
        [env.get_mask_invalid_actions_forward(s) for s in states], device=env.device
    )

    # Build policy outputs
    params = env.fixed_distr_params
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))

    # Get log probs
    logprobs = env.get_logprobs(
        policy_outputs, actions, masks, states_torch, is_backward=False
    )
    assert torch.all(logprobs == 0.0)


@pytest.mark.parametrize(
    "states, actions",
    [
        (
            [[-1.0, 1, 0], [0.0, 1, 0], [0.3, 1, 0]],
            [[1, 0.1, 0.0], [1, 0.1, 0.0], [1, 0.1, 0.0]],
        ),
        (
            [[0.12, 1, 0], [0.56, 1, 0], [0.9, 1, 0]],
            [[1, 0.3585, 0.0], [1, 0.3, 0.0], [1, 0.1001, 0.0]],
        ),
        (
            [[0.05, 1, 0], [0.56, 1, 0], [0.85, 1, 0]],
            [[1, 0.3585, 1.0], [1, 0.3, 1.0], [1, 0.1001, 1.0]],
        ),
        (
            [[0.0, 1, 0], [0.0, 1, 0], [0.3, 1, 0]],
            [[1, 0.3585, 0.0], [1, 0.1, 0.0], [1, 0.1, 0.0]],
        ),
        (
            [[0.12, 1, 0], [0.56, 1, 0], [0.9, 1, 0]],
            [[1, 0.2, 0.0], [1, 0.001, 1.0], [1, 0.5, 0.0]],
        ),
    ],
)
def test__get_logprobs_forward__2d__finite(cube2d, states, actions):
    env = cube2d
    n_states = len(states)
    states_torch = tfloat(states, float_type=env.float, device=env.device)
    actions = tfloat(actions, float_type=env.float, device=env.device)
    # Get masks
    masks = tbool(
        [env.get_mask_invalid_actions_forward(s) for s in states], device=env.device
    )
    # Build policy outputs
    params = env.fixed_distr_params
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))
    # Get log probs
    logprobs = env.get_logprobs(
        policy_outputs, actions, masks, states_torch, is_backward=False
    )
    assert torch.all(torch.isfinite(logprobs))


@pytest.mark.parametrize(
    "states, actions",
    [
        (
            [
                [0.95, 0.95, 0, -1],
                [0.85, 0.95, 0, -1],
                [0.95, -1.0, 0, -1],
                [0.2, 0.2, 1, 0],
                [0.5, 0.5, 1, 1],
                [-1.0, -1.0, 1, 0],
                [-1.0, -1.0, 1, 1],
            ],
            [
                [np.inf, np.inf, np.inf],
                [0, 0, 0],
                [0, 1, 0],
                [1, 0.5, 0],
                [1, 0.3, 0],
                [1, 0.3, 1],
                [1, 0.5, 1],
            ],
        ),
    ],
)
def test__get_logprobs_forward__2d__is_finite(cube2d, states, actions):
    env = cube2d
    n_states = len(states)
    states_torch = tfloat(states, float_type=env.float, device=env.device)
    actions = tfloat(actions, float_type=env.float, device=env.device)
    # Get masks
    masks = tbool(
        [env.get_mask_invalid_actions_forward(s) for s in states], device=env.device
    )
    # Get EOS forced
    is_near_edge = states_torch > 1.0 - env.min_incr
    is_eos_forced = torch.any(is_near_edge, dim=1)
    # Define Bernoulli parameter for EOS
    prob_eos = 0.5
    distr_eos = Bernoulli(probs=prob_eos)
    logprob_eos = distr_eos.log_prob(torch.tensor(1.0))
    # Build policy outputs
    params = env.fixed_distr_params
    params["bernoulli_eos_prob"] = prob_eos
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))
    # Get log probs
    logprobs = env.get_logprobs(
        policy_outputs, actions, masks, states_torch, is_backward=False
    )
    assert torch.all(torch.isfinite(logprobs))


@pytest.mark.parametrize(
    "states, actions",
    [
        (
            [
                [0.3, 0.3, 2, 0],
                [0.5, 0.5, 2, 1],
                [1.0, 1.0, 2, 0],
                [0.05, 0.2, 2, 1],
                [0.05, 0.05, 2, 0],
            ],
            [
                [1, 0.2, 0.0],
                [1, 0.2, 0.0],
                [1, 0.5, 0.0],
                [1, 0.2, 1.0],
                [1, 0.05, 1.0],
            ],
        ),
    ],
)
def test__get_logprobs_backward__2d__is_finite(cube2d, states, actions):
    env = cube2d
    n_states = len(states)
    states_torch = tfloat(states, float_type=env.float, device=env.device)
    actions = tfloat(actions, float_type=env.float, device=env.device)
    # Get masks
    masks = tbool(
        [env.get_mask_invalid_actions_backward(s) for s in states], device=env.device
    )
    # Define Bernoulli parameter for BTS
    prob_bts = 0.5
    distr_bts = Bernoulli(probs=prob_bts)
    logprob_bts = distr_bts.log_prob(torch.tensor(1.0))
    # Build policy outputs
    params = env.fixed_distr_params
    params["bernoulli_bts_prob"] = prob_bts
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))
    # Get log probs
    logprobs = env.get_logprobs(
        policy_outputs, actions, masks, states_torch, is_backward=True
    )
    assert torch.all(torch.isfinite(logprobs))


@pytest.mark.parametrize(
    "states, actions",
    [
        (
            [[0.02, 0.01, 2, 0], [0.01, 0.2, 2, 0], [0.3, 0.01, 2, 1]],
            [[1, 0.02, 1.0], [1, 0.01, 1.0], [1, 0.01, 1.0]],
        ),
        (
            [[0.0, 0.0, 2, 0], [0.0, 0.09, 2, 1], [0.3, 0.0, 2, 1]],
            [[1, 0.0, 1.0], [1, 0.09, 1.0], [1, 0.0, 1.0]],
        ),
    ],
)
def test__get_logprobs_backward__2d__nearedge_returns_prob1(cube2d, states, actions):
    """
    The only valid backward action from 'near-edge' states is BTS, thus the the log
    probability of BTS actions should be zero.
    """
    env = cube2d
    n_states = len(states)
    states_torch = tfloat(states, float_type=env.float, device=env.device)
    actions = tfloat(actions, float_type=env.float, device=env.device)
    # Get masks
    masks = tbool(
        [env.get_mask_invalid_actions_backward(s) for s in states], device=env.device
    )
    # Build policy outputs
    params = env.fixed_distr_params
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))
    # Add noise to policy outputs
    policy_outputs += torch.randn(policy_outputs.shape)
    # Get log probs
    logprobs = env.get_logprobs(
        policy_outputs, actions, masks, states_torch, is_backward=True
    )
    assert torch.all(logprobs == 0.0)


@pytest.mark.parametrize(
    "states, actions",
    [
        (
            [[0.1, 0.2, 2, 0], [0.3, 0.5, 2, 0], [0.5, 0.95, 2, 0]],
            [[1, 0.1, 1], [1, 0.3, 1], [1, 0.5, 1]],
        ),
        (
            [[0.99, 0.99, 2, 1], [0.01, 0.01, 2, 1], [0.001, 0.1, 2, 1]],
            [[1, 0.99, 1], [1, 0.01, 1], [1, 0.1, 1]],
        ),
        (
            [[1.0, 1.0, 2, 0], [0.0, 0.0, 2, 0]],
            [[1, 1.0, 1], [1, 0.0, 1]],
        ),
    ],
)
def test__get_logprobs_backward__2d__bts_actions_return_expected(
    cube2d, states, actions
):
    """
    The only valid action from 'near-edge' states is BTS, thus the log probability
    should be zero, regardless of the action and the policy outputs
    """
    env = cube2d
    n_states = len(states)
    states_torch = tfloat(states, float_type=env.float, device=env.device)
    values_to_decrement = states_torch[
        torch.arange(n_states), states_torch[:, -1].int()
    ]
    actions = tfloat(actions, float_type=env.float, device=env.device)

    # Get masks
    masks = tbool(
        [env.get_mask_invalid_actions_backward(s) for s in states], device=env.device
    )
    # Get BTS forced
    is_bts_forced = values_to_decrement < env.min_incr

    # Define Bernoulli parameter for BTS
    prob_bts = 0.5
    distr_bts = Bernoulli(probs=prob_bts)
    logprob_bts = distr_bts.log_prob(torch.tensor(1.0))

    # Build policy outputs
    params = env.fixed_distr_params
    params["bernoulli_bts_prob"] = prob_bts
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))

    # Get log probs
    logprobs = env.get_logprobs(
        policy_outputs, actions, masks, states_torch, is_backward=True
    )
    assert torch.all(logprobs[is_bts_forced] == 0.0)
    assert torch.all(torch.isclose(logprobs[~is_bts_forced], logprob_bts, atol=1e-6))


@pytest.mark.parametrize(
    "states, actions",
    [
        (
            [[0.3, 0.3, 2, 0], [0.5, 0.5, 2, 0], [0.8, 0.8, 2, 0]],
            [[1, 0.2, 0.0], [1, 0.2, 0.0], [1, 0.2, 0.0]],
        ),
        (
            [[1.0, 1.0, 2, 1], [1.0, 1.0, 2, 1], [1.0, 1.0, 2, 1]],
            [[1, 0.2, 0.0], [1, 0.2, 0.0], [1, 0.2, 0.0]],
        ),
        (
            [[1.0, 1.0, 2, 0], [0.5, 0.5, 2, 0], [0.3, 0.3, 2, 0]],
            [[1, 0.1, 0.0], [1, 0.1, 0.0], [1, 0.1, 0.0]],
        ),
    ],
)
def test__get_logprobs_backward__2d__notnan(cube2d, states, actions):
    env = cube2d
    n_states = len(states)
    states_torch = tfloat(states, float_type=env.float, device=env.device)
    values_to_decrement = states_torch[
        torch.arange(n_states), states_torch[:, -1].int()
    ]
    actions = tfloat(actions, float_type=env.float, device=env.device)

    # Get masks
    masks = tbool(
        [env.get_mask_invalid_actions_backward(s) for s in states], device=env.device
    )
    # Get BTS forced
    is_bts_forced = values_to_decrement < env.min_incr

    # Define Bernoulli parameter for BTS
    prob_bts = 0.5
    distr_bts = Bernoulli(probs=prob_bts)
    logprob_bts = distr_bts.log_prob(torch.tensor(1.0))

    # Build policy outputs
    params = env.fixed_distr_params
    params["bernoulli_bts_prob"] = prob_bts
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))

    # Get log probs
    logprobs = env.get_logprobs(
        policy_outputs, actions, masks, states_torch, is_backward=True
    )
    assert torch.all(logprobs[is_bts_forced] == 0.0)
    assert torch.all(torch.isfinite(logprobs))


@pytest.mark.parametrize(
    "states, actions",
    [
        (
            [[0.1, 0.2, 1, 0], [0.3, 0.5, 1, 1], [0.90, 0.90, 1, 0]],
            [
                [0, 0, 0],
                [0, 1, 0],
                [0, 0, 0],
            ],
        ),
        (
            [[0.5, 0.5, 1, 1], [0.01, 0.01, 1, 0], [0.001, 0.1, 1, 1]],
            [
                [0, 1, 0],
                [0, 0, 0],
                [0, 1, 0],
            ],
        ),
    ],
)
def test__get_logprobs_backward__2d__all_select_prob1(cube2d, states, actions):
    """
    When select actions are valid, they are the only valid actions and so their
    logprobs should always be 0.
    """
    env = cube2d
    n_states = len(states)
    states_torch = tfloat(states, float_type=env.float, device=env.device)
    actions = tfloat(actions, float_type=env.float, device=env.device)
    # Get masks
    masks = tbool(
        [env.get_mask_invalid_actions_backward(s) for s in states], device=env.device
    )

    # Build policy outputs
    params = env.fixed_distr_params
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))

    # Get log probs
    logprobs = env.get_logprobs(
        policy_outputs, actions, masks, states_torch, is_backward=True
    )
    # import pdb; pdb.set_trace()
    assert torch.all(logprobs == 0.0)


@pytest.mark.parametrize(
    "states, actions",
    [
        (
            [[0.1, 0.2, 0, -1], [0.3, 0.5, 0, -1], [0.90, 0.90, 0, -1]],
            [
                [2, 0, 0],
                [2, 1, 0],
                [2, 0, 0],
            ],
        ),
        (
            [[0.5, 0.5, 0, -1], [0.01, 0.01, 0, -1], [0.001, 0.1, 0, -1]],
            [
                [2, 1, 0],
                [2, 0, 0],
                [2, 1, 0],
            ],
        ),
    ],
)
def test__get_logprobs_backward__2d__all_deselec_actions_same_prob(
    cube2d, states, actions
):
    """
    When deselect actions are valid, they are the only valid actions and so their
    logprobs should always be 0.
    """
    env = cube2d
    n_states = len(states)
    states_torch = tfloat(states, float_type=env.float, device=env.device)
    actions = tfloat(actions, float_type=env.float, device=env.device)
    # Get masks
    masks = tbool(
        [env.get_mask_invalid_actions_backward(s) for s in states], device=env.device
    )

    # Build policy outputs
    params = env.fixed_distr_params
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))

    # Get log probs
    logprobs = env.get_logprobs(
        policy_outputs, actions, masks, states_torch, is_backward=True
    )
    assert torch.all(torch.isclose(logprobs, logprobs[0], atol=1e-6))


def test__continuous_env_common__cube1d(cube1d):
    return common.test__continuous_env_common(cube1d)


def test__continuous_env_common__cube2d(cube2d):
    return common.test__continuous_env_common(cube2d)
