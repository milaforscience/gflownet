"""
Classes to represent hyper-cube environments
"""
import itertools
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd
import torch
from sklearn.neighbors import KernelDensity
from torch.distributions import Bernoulli, Beta, Categorical, MixtureSameFamily, Uniform
from torchtyping import TensorType

from gflownet.envs.base import GFlowNetEnv
from gflownet.utils.common import copy, tbool, tfloat


class Cube(GFlowNetEnv, ABC):
    """
    Continuous (hybrid: discrete and continuous) hyper-cube environment (continuous
    version of a hyper-grid) in which the action space consists of the increment of
    dimension d, modelled by a beta distribution.

    The states space is the value of each dimension. If the value of a dimension gets
    larger than max_val, then the trajectory is ended.

    Attributes
    ----------
    n_dim : int
        Dimensionality of the hyper-cube.

    max_val : float
        Max length of the hyper-cube.

    min_incr : float
        Minimum increment in the actions, expressed as the fraction of max_val. This is
        necessary to ensure coverage of the state space.
    """

    def __init__(
        self,
        n_dim: int = 2,
        max_val: float = 1.0,
        min_incr: float = 0.1,
        n_comp: int = 1,
        beta_params_min: float = 0.1,
        beta_params_max: float = 1000.0,
        fixed_distr_params: dict = {
            "beta_weights": 1.0,
            "beta_alpha": 2.0,
            "beta_beta": 5.0,
            "bernoulli_source_logit": 1.0,
            "bernoulli_eos_logit": 1.0,
        },
        random_distr_params: dict = {
            "beta_weights": 1.0,
            "beta_alpha": 1000.0,
            "beta_beta": 1000.0,
            "bernoulli_source_logit": 1.0,
            "bernoulli_eos_logit": 1.0,
        },
        **kwargs,
    ):
        assert n_dim > 0
        assert max_val > 0.0
        assert n_comp > 0
        # Main properties
        self.n_dim = n_dim
        self.eos = self.n_dim
        self.max_val = max_val
        self.min_incr = min_incr * self.max_val
        # Parameters of the policy distribution
        self.n_comp = n_comp
        self.beta_params_min = beta_params_min
        self.beta_params_max = beta_params_max
        # Source state: position 0 at all dimensions
        self.source = [0.0 for _ in range(self.n_dim)]
        # Action from source: (n_dim, 0)
        self.action_source = (self.n_dim, 0)
        # End-of-sequence action: (n_dim + 1, 0)
        self.eos = (self.n_dim + 1, 0)
        # Conversions: only conversions to policy are implemented and the rest are the
        # same
        self.state2proxy = self.state2policy
        self.statebatch2proxy = self.statebatch2policy
        self.statetorch2proxy = self.statetorch2policy
        self.state2oracle = self.state2proxy
        self.statebatch2oracle = self.statebatch2proxy
        self.statetorch2oracle = self.statetorch2proxy
        # Base class init
        super().__init__(
            fixed_distr_params=fixed_distr_params,
            random_distr_params=random_distr_params,
            **kwargs,
        )
        self.continuous = True

    @abstractmethod
    def get_action_space(self):
        pass

    @abstractmethod
    def get_policy_output(self, params: dict) -> TensorType["policy_output_dim"]:
        pass

    @abstractmethod
    def get_mask_invalid_actions_forward(
        self,
        state: Optional[List] = None,
        done: Optional[bool] = None,
    ) -> List:
        pass

    @abstractmethod
    def get_mask_invalid_actions_backward(self, state=None, done=None, parents_a=None):
        pass

    def statetorch2policy(
        self, states: TensorType["batch", "state_dim"] = None
    ) -> TensorType["batch", "policy_input_dim"]:
        """
        Clips the states into [0, max_val] and maps them to [-1.0, 1.0]

        Args
        ----
        state : list
            State
        """
        return 2.0 * torch.clip(states, min=0.0, max=self.max_val) - 1.0

    def statebatch2policy(
        self, states: List[List]
    ) -> TensorType["batch", "state_proxy_dim"]:
        """
        Clips the states into [0, max_val] and maps them to [-1.0, 1.0]

        Args
        ----
        state : list
            State
        """
        return self.statetorch2policy(
            tfloat(states, device=self.device, float_type=self.float)
        )

    def state2policy(self, state: List = None) -> List:
        """
        Clips the state into [0, max_val] and maps it to [-1.0, 1.0]
        """
        if state is None:
            state = self.state.copy()
        return [2.0 * min(max(0.0, s), self.max_val) - 1.0 for s in state]

    def state2readable(self, state: List) -> str:
        """
        Converts a state (a list of positions) into a human-readable string
        representing a state.
        """
        return str(state).replace("(", "[").replace(")", "]").replace(",", "")

    def readable2state(self, readable: str) -> List:
        """
        Converts a human-readable string representing a state into a state as a list of
        positions.
        """
        return [el for el in readable.strip("[]").split(" ")]

    @abstractmethod
    def get_parents(
        self, state: List = None, done: bool = None, action: Tuple[int, float] = None
    ) -> Tuple[List[List], List[Tuple[int, float]]]:
        """
        Determines all parents and actions that lead to state.

        Args
        ----
        state : list
            Representation of a state

        done : bool
            Whether the trajectory is done. If None, done is taken from instance.

        action : int
            Last action performed

        Returns
        -------
        parents : list
            List of parents in state format

        actions : list
            List of actions that lead to state for each parent in parents
        """
        pass

    @abstractmethod
    def sample_actions_batch(
        self,
        policy_outputs: TensorType["n_states", "policy_output_dim"],
        sampling_method: str = "policy",
        mask_invalid_actions: TensorType["n_states", "1"] = None,
        temperature_logits: float = 1.0,
        loginf: float = 1000,
    ) -> Tuple[List[Tuple], TensorType["n_states"]]:
        """
        Samples a batch of actions from a batch of policy outputs.
        """
        pass

    def get_logprobs(
        self,
        policy_outputs: TensorType["n_states", "policy_output_dim"],
        is_forward: bool,
        actions: TensorType["n_states", 2],
        mask_invalid_actions: TensorType["batch_size", "policy_output_dim"] = None,
        loginf: float = 1000,
    ) -> TensorType["batch_size"]:
        """
        Computes log probabilities of actions given policy outputs and actions.
        """
        pass

    def step(
        self, action: Tuple[int, float]
    ) -> Tuple[List[float], Tuple[int, float], bool]:
        """
        Executes step given an action.

        Args
        ----
        action : tuple
            Action to be executed. An action is a tuple with two values:
            (dimension, increment).

        Returns
        -------
        self.state : list
            The sequence after executing the action

        action : int
            Action executed

        valid : bool
            False, if the action is not allowed for the current state, e.g. stop at the
            root state
        """
        pass


class ContinuousCube(Cube):
    """
    Continuous hyper-cube environment (continuous version of a hyper-grid) in which the
    action space consists of the increment of each dimension d, modelled by a mixture
    of Beta distributions. The states space is the value of each dimension. In order to
    ensure that all trajectories are of finite length, actions have a minimum increment
    for all dimensions determined by min_incr. If the value of any dimension is larger
    than 1 - min_incr, then that dimension can be further incremented. In order to
    ensure the coverage of the state space, the first action (from the source state) is
    not constrained by the minimum increment.

    Actions do not represent absolute increments but rather the relative increment with
    respect to the distance to the edges of the hyper-cube, from the minimum increment.
    That is, if dimension d of a state has value 0.3, the minimum increment (min_incr)
    is 0.1 and the maximum value (max_val) is 1.0, an action of 0.5 will increment the
    value of the dimension in 0.5 * (1.0 - 0.3 - 0.1) = 0.5 * 0.6 = 0.3. Therefore, the
    value of d in the next state will be 0.3 + 0.3 = 0.6.

    Attributes
    ----------
    n_dim : int
        Dimensionality of the hyper-cube.

    max_val : float
        Max length of the hyper-cube.

    min_incr : float
        Minimum increment in the actions, expressed as the fraction of max_val. This is
        necessary to ensure that trajectories have finite length.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_action_space(self):
        """
        The action space is continuous, thus not defined as such here.

        The actions are tuples of length n_dim, where the value at position d indicates
        the increment of dimension d.

        EOS is indicated by np.inf for all dimensions.

        This method defines self.eos and the returned action space is simply a
        representative (arbitrary) action with an increment of 0.0 in all dimensions,
        and EOS.
        """
        self.eos = tuple([np.inf] * self.n_dim)
        self.representative_action = tuple([0.0] * self.n_dim)
        return [self.representative_action, self.eos]

    def get_policy_output(self, params: dict) -> TensorType["policy_output_dim"]:
        """
        Defines the structure of the output of the policy model, from which an
        action is to be determined or sampled, by returning a vector with a fixed
        random policy. The environment consists of both continuous and discrete
        actions.

        Continuous actions

        For each dimension d of the hyper-cube and component c of the mixture, the
        output of the policy should return
          1) the weight of the component in the mixture
          2) the logit(alpha) parameter of the Beta distribution to sample the increment
          3) the logit(beta) parameter of the Beta distribution to sample the increment

        These parameters are the first n_dim * n_comp * 3 of the policy output such
        that the first 3 x C elements correspond to the first dimension, and so on.

        Discrete actions

        Additionally, the policy output contains one logit (pos -1) of a Bernoulli
        distribution to model the (discrete) forward probability of selecting the EOS
        action and another logit (pos -2) for the (discrete) backward probability of
        returning to the source node.

        Therefore, the output of the policy model has dimensionality D x C x 3 + 2,
        where D is the number of dimensions (self.n_dim) and C is the number of
        components (self.n_comp).
        """
        # Parameters for continuous actions
        self._len_policy_output_cont = self.n_dim * self.n_comp * 3
        policy_output_cont = torch.empty(
            self._len_policy_output_cont,
            dtype=self.float,
            device=self.device,
        )
        policy_output_cont[0::3] = params["beta_weights"]
        policy_output_cont[1::3] = params["beta_alpha"]
        policy_output_cont[2::3] = params["beta_beta"]
        # Logit for Bernoulli distribution to model EOS action
        policy_output_eos = torch.tensor(
            [params["bernoulli_eos_logit"]], dtype=self.float, device=self.device
        )
        # Logit for Bernoulli distribution to model back-to-source action
        policy_output_source = torch.tensor(
            [params["bernoulli_source_logit"]], dtype=self.float, device=self.device
        )
        # Concatenate all outputs
        policy_output = torch.cat(
            (
                policy_output_cont,
                policy_output_source,
                policy_output_eos,
            )
        )
        return policy_output

    def _get_policy_betas_weights(
        self, policy_output: TensorType["n_states", "policy_output_dim"]
    ) -> TensorType["n_states", "n_dim * n_comp"]:
        """
        Reduces a given policy output to the part corresponding to the weights of the
        mixture of Beta distributions.

        See: get_policy_output()
        """
        return policy_output[:, 0 : self._len_policy_output_cont : 3]

    def _get_policy_betas_alpha(
        self, policy_output: TensorType["n_states", "policy_output_dim"]
    ) -> TensorType["n_states", "n_dim * n_comp"]:
        """
        Reduces a given policy output to the part corresponding to the alphas of the
        mixture of Beta distributions.

        See: get_policy_output()
        """
        return policy_output[:, 1 : self._len_policy_output_cont : 3]

    def _get_policy_betas_beta(
        self, policy_output: TensorType["n_states", "policy_output_dim"]
    ) -> TensorType["n_states", "n_dim * n_comp"]:
        """
        Reduces a given policy output to the part corresponding to the betas of the
        mixture of Beta distributions.

        See: get_policy_output()
        """
        return policy_output[:, 2 : self._len_policy_output_cont : 3]

    def _get_policy_eos_logit(
        self, policy_output: TensorType["n_states", "policy_output_dim"]
    ) -> TensorType["n_states", "1"]:
        """
        Reduces a given policy output to the part corresponding to the logit of the
        Bernoulli distribution to model the EOS action.

        See: get_policy_output()
        """
        return policy_output[:, -1]

    def _get_policy_source_logit(
        self, policy_output: TensorType["n_states", "policy_output_dim"]
    ) -> TensorType["n_states", "1"]:
        """
        Reduces a given policy output to the part corresponding to the logit of the
        Bernoulli distribution to model the back-to-source action.

        See: get_policy_output()
        """
        return policy_output[:, -2]

    def get_mask_invalid_actions_forward(
        self,
        state: Optional[List] = None,
        done: Optional[bool] = None,
    ) -> List:
        """
        The action space is continuous, thus the mask is not only of invalid actions as
        in discrete environments, but also an indicator of "special cases", for example
        states from which only certain actions are possible.

        The values of True/False intend to approximately stick to the semantics in
        discrete environments, where the mask is of "invalid" actions, but it is
        important to note that a direct interpretation in this sense does not always
        apply.

        For example, the mask values of special cases are True if the special cases they
        refer to are "invalid". In other words, the values are False if the state has
        the special case.

        The forward mask has the following structure:

        - 0 : whether a continuous action is invalid. True if the value at any
          dimension is larger than 1 - min_incr, or if done is True. False otherwise.
        - 1 : special case when the state is the source state. False when the state is
          the source state, True otherwise.
        - 2 : whether EOS action is invalid. EOS is valid from any state, except the
          source state or if done is True.
        """
        state = self._get_state(state)
        done = self._get_done(done)
        mask_dim = 3
        # If done, the entire mask is True (all actions are "invalid" and no special
        # cases)
        if done:
            return [True] * mask_dim
        mask = [False] * mask_dim
        # If the state is not the source state, EOS is invalid
        if state == self.source:
            mask[2] = True
        # If the state is not the source, indicate not special case (True)
        else:
            mask[1] = True
        # If the value of any dimension is greater than 1 - min_incr, then continuous
        # actions are invalid (True).
        if any([s > 1 - self.min_incr for s in state]):
            mask[0] = True
        return mask

    def get_mask_invalid_actions_backward(self, state=None, done=None, parents_a=None):
        """
        The action space is continuous, thus the mask is not only of invalid actions as
        in discrete environments, but also an indicator of "special cases", for example
        states from which only certain actions are possible.

        In order to approximately stick to the semantics in discrete environments,
        where the mask is of "invalid" actions, that is the value is True if an action
        is invalid, the mask values of special cases are True if the special cases they
        refer to are "invalid". In other words, the values are False if the state has
        the special case.

        The backward mask has the following structure:

        - 0 : whether a continuous action is invalid. True if the value at any
          dimension is smaller than min_incr, or if done is True. False otherwise.
        - 1 : special case when back-to-source action is the only possible action.
          False if any dimension is smaller than min_incr, True otherwise.
        - 2 : whether EOS action is invalid. False only if done is True, True
          (invalid) otherwise.
        """
        state = self._get_state(state)
        done = self._get_done(done)
        mask_dim = 3
        mask = [True] * mask_dim
        # If done, only valid action is EOS.
        if done:
            mask[2] = False
            return mask
        # If any dimension is smaller than m, then back-to-source action is the only
        # possible actiona.
        if any([s < self.min_incr for s in state]):
            mask[1] = False
            return mask
        # Otherwise, continuous actions are valid
        mask[0] = False
        return mask

    def get_parents(
        self, state: List = None, done: bool = None, action: Tuple[int, float] = None
    ) -> Tuple[List[List], List[Tuple[int, float]]]:
        """
        Defined only because it is required. A ContinuousEnv should be created to avoid
        this issue.
        """
        pass

    @staticmethod
    def relative_to_absolute_increments(
        states: TensorType["n_states", "n_dim"],
        increments_rel: TensorType["n_states", "n_dim"],
        min_increments: TensorType["n_states", "n_dim"],
        max_val: float,
        is_backward: bool,
    ):
        """
        Returns a batch of absolute increments (actions) given a batch of states,
        relative increments and minimum_increments.

        Given a dimension value x, a relative increment r, a minimum increment m and a
        maximum value 1, the absolute increment a is given by:

        Forward:

        a = m + r * (1 - x - m)

        Backward:

        a = m + r * (x - m)
        """
        max_val = torch.full_like(states, max_val)
        if is_backward:
            increments_abs = min_increments + increments_rel * (states - min_increments)
        else:
            increments_abs = min_increments + increments_rel * (
                max_val - states - min_increments
            )
        return increments_abs

    @staticmethod
    def absolute_to_relative_increments(
        states: TensorType["n_states", "n_dim"],
        increments_abs: TensorType["n_states", "n_dim"],
        min_increments: TensorType["n_states", "n_dim"],
        max_val: float,
        is_backward: bool,
    ):
        """
        Returns a batch of relative increments (as sampled by the Beta distributions)
        given a batch of states, absolute increments (actions) and minimum_increments.

        Given a dimension value x, an absolute increment a, a minimum increment m and a
        maximum value 1, the relative increment r is given by:

        Forward:

        r = (a - m) / (1 - x - m)

        Backward:

        r = (a - m) / (x - m)
        """
        max_val = torch.full_like(states, max_val)
        if is_backward:
            increments_rel = (increments_abs - min_increments) / (
                states - min_increments
            )
        else:
            increments_rel = (increments_abs - min_increments) / (
                max_val - states - min_increments
            )
        return increments_rel

    def _make_increments_distribution(
        self,
        policy_outputs: TensorType["n_states", "policy_output_dim"],
    ) -> MixtureSameFamily:
        mix_logits = self._get_policy_betas_weights(policy_outputs).reshape(
            -1, self.n_dim, self.n_comp
        )
        mix = Categorical(logits=mix_logits)
        alphas = self._get_policy_betas_alpha(policy_outputs).reshape(
            -1, self.n_dim, self.n_comp
        )
        alphas = self.beta_params_max * torch.sigmoid(alphas) + self.beta_params_min
        betas = self._get_policy_betas_beta(policy_outputs).reshape(
            -1, self.n_dim, self.n_comp
        )
        betas = self.beta_params_max * torch.sigmoid(betas) + self.beta_params_min
        beta_distr = Beta(alphas, betas)
        return MixtureSameFamily(mix, beta_distr)

    def sample_actions_batch(
        self,
        policy_outputs: TensorType["n_states", "policy_output_dim"],
        mask: Optional[TensorType["n_states", "policy_output_dim"]] = None,
        states_from: List = None,
        is_backward: Optional[bool] = False,
        sampling_method: Optional[str] = "policy",
        temperature_logits: Optional[float] = 1.0,
        max_sampling_attempts: Optional[int] = 10,
    ) -> Tuple[List[Tuple], TensorType["n_states"]]:
        """
        Samples a batch of actions from a batch of policy outputs.
        """
        if not is_backward:
            return self._sample_actions_batch_forward(
                policy_outputs, mask, states_from, sampling_method, temperature_logits
            )
        else:
            return self._sample_actions_batch_backward(
                policy_outputs, mask, states_from, sampling_method, temperature_logits
            )

    def _sample_actions_batch_forward(
        self,
        policy_outputs: TensorType["n_states", "policy_output_dim"],
        mask: Optional[TensorType["n_states", "policy_output_dim"]] = None,
        states_from: List = None,
        sampling_method: Optional[str] = "policy",
        temperature_logits: Optional[float] = 1.0,
        max_sampling_attempts: Optional[int] = 10,
    ) -> Tuple[List[Tuple], TensorType["n_states"]]:
        """
        Samples a a batch of forward actions from a batch of policy outputs.

        An action indicates, for each dimension, the absolute increment of the
        dimension value. However, in order to ensure that trajectories have finite
        length, increments must have a minumum increment (self.min_incr) except if the
        originating state is the source state (special case, see
        get_mask_invalid_actions_forward()). Furthermore, absolute increments must also
        be smaller than the distance from the dimension value to the edge of the cube
        (self.max_val). In order to accomodate these constraints, first relative
        increments (in [0, 1]) are sampled from a (mixture of) Beta distribution(s),
        where 0.0 indicates an absolute increment of min_incr and 1.0 indicates an
        absolute increment of 1 - x + min_incr (going to the edge).

        Therefore, given a dimension value x, a relative increment r, a minimum
        increment m and a maximum value 1, the absolute increment a is given by:

        a = m + r * (1 - x - m)

        The continuous distribution to sample the continuous action described above
        must be mixed with the discrete distribution to model the sampling of the EOS
        action. The EOS action can be sampled from any state except from the source
        state or whether the trajectory is done. That the EOS action is invalid is
        indicated by mask[-1] being False.

        Finally, regarding the constraints on the increments, the following special
        cases are taken into account:

        - The originating state is the source state: in this case, the minimum
          increment is 0.0 instead of self.min_incr. This is to ensure that the entire
          state space can be reached. This is indicated by mask[-2] being False.
        - The value at any dimension is at a distance from the cube edge smaller than the
          minimum increment (x > 1 - m). In this case, only EOS is valid.
          This is indicated by mask[0] being True (continuous actions are invalid).
        """
        # Initialize variables
        n_states = policy_outputs.shape[0]
        is_eos = torch.zeros(n_states, dtype=torch.bool, device=self.device)
        # Determine source states
        is_source = ~mask[:, 1]
        # EOS is the only possible action if continuous actions are invalid (mask[0] is
        # True)
        is_eos_forced = mask[:, 0]
        is_eos[is_eos_forced] = True
        # Ensure that is_eos_forced does not include any source state
        assert not torch.any(torch.logical_and(is_source, is_eos_forced))
        # Sample EOS from Bernoulli distribution
        do_eos = torch.logical_and(~is_source, ~is_eos_forced)
        if torch.any(do_eos):
            is_eos_sampled = torch.zeros_like(do_eos)
            logits_eos = self._get_policy_eos_logit(policy_outputs)[do_eos]
            distr_eos = Bernoulli(logits=logits_eos)
            is_eos_sampled[do_eos] = tbool(distr_eos.sample(), device=self.device)
            is_eos[is_eos_sampled] = True
        # Sample relative increments if EOS is not the sampled or forced action
        do_increments = ~is_eos
        if torch.any(do_increments):
            if sampling_method == "uniform":
                raise NotImplementedError()
            elif sampling_method == "policy":
                distr_increments = self._make_increments_distribution(
                    policy_outputs[do_increments]
                )
            # Shape of increments_rel: [n_do_increments, n_dim]
            increments_rel = distr_increments.sample()
            # Get minimum increments
            min_increments = torch.full_like(
                increments_rel, self.min_incr, dtype=self.float, device=self.device
            )
            min_increments[is_source[do_increments]] = 0.0
            # Compute absolute increments
            states_from_do_increments = tfloat(
                states_from, float_type=self.float, device=self.device
            )[do_increments]
            increments_abs = self.relative_to_absolute_increments(
                states_from_do_increments,
                increments_rel,
                min_increments,
                self.max_val,
                is_backward=False,
            )
        # Build actions
        actions_tensor = torch.full(
            (n_states, self.n_dim), torch.inf, dtype=self.float, device=self.device
        )
        if torch.any(do_increments):
            actions_tensor[do_increments] = increments_abs
        actions = [tuple(a.tolist()) for a in actions_tensor]
        return actions, None

    def _sample_actions_batch_backward(
        self,
        policy_outputs: TensorType["n_states", "policy_output_dim"],
        mask: Optional[TensorType["n_states", "policy_output_dim"]] = None,
        states_from: List = None,
        sampling_method: Optional[str] = "policy",
        temperature_logits: Optional[float] = 1.0,
        max_sampling_attempts: Optional[int] = 10,
    ) -> Tuple[List[Tuple], TensorType["n_states"]]:
        """
        Samples a a batch of backward actions from a batch of policy outputs.

        An action indicates, for each dimension, the absolute increment of the
        dimension value. However, in order to ensure that trajectories have finite
        length, increments must have a minumum increment (self.min_incr). Furthermore,
        absolute increments must also be smaller than the distance from the dimension
        value to the edge of the cube. In order to accomodate these constraints, first
        relative increments (in [0, 1]) are sampled from a (mixture of) Beta
        distribution(s), where 0.0 indicates an absolute increment of min_incr and 1.0
        indicates an absolute increment of x (going back to the source).

        Therefore, given a dimension value x, a relative increment r, a minimum
        increment m and a maximum value 1, the absolute increment a is given by:

        a = m + r * (x - m)

        The continuous distribution to sample the continuous action described above
        must be mixed with the discrete distribution to model the sampling of the back
        to source (BST) action. While the BST action is also a continuous action, it
        needs to be modelled with a (discrete) Bernoulli distribution in order to
        ensure that this action has positive likelihood.

        Finally, regarding the constraints on the increments, the special case where
        the trajectory is done and the only possible action is EOS, is also taken into
        account.
        """
        # Initialize variables
        n_states = policy_outputs.shape[0]
        is_bts = torch.zeros(n_states, dtype=torch.bool, device=self.device)
        # EOS is the only possible action only if done is True (mask[2] is False)
        is_eos = ~mask[:, 2]
        # Back-to-source (BTS) is the only possible action if mask[1] is False
        is_bts_forced = ~mask[:, 1]
        is_bts[is_bts_forced] = True
        # Sample BTS from Bernoulli distribution
        do_bts = torch.logical_and(~is_bts_forced, ~is_eos)
        if torch.any(do_bts):
            is_bts_sampled = torch.zeros_like(do_bts)
            logits_bts = self._get_policy_source_logit(policy_outputs)[do_bts]
            distr_bts = Bernoulli(logits=logits_bts)
            is_bts_sampled[do_bts] = tbool(distr_bts.sample(), device=self.device)
            is_bts[is_bts_sampled] = True
        # Sample relative increments if actions are neither BTS nor EOS
        do_increments = torch.logical_and(~is_bts, ~is_eos)
        if torch.any(do_increments):
            if sampling_method == "uniform":
                raise NotImplementedError()
            elif sampling_method == "policy":
                distr_increments = self._make_increments_distribution(
                    policy_outputs[do_increments]
                )
            # Shape of increments_rel: [n_do_increments, n_dim]
            increments_rel = distr_increments.sample()
            # Set minimum increments
            min_increments = torch.full_like(
                increments_rel, self.min_incr, dtype=self.float, device=self.device
            )
            # Compute absolute increments
            states_from_do_increments = tfloat(
                states_from, float_type=self.float, device=self.device
            )[do_increments]
            increments_abs = self.relative_to_absolute_increments(
                states_from_do_increments,
                increments_rel,
                min_increments,
                self.max_val,
                is_backward=True,
            )
        # Build actions
        actions_tensor = torch.zeros(
            (n_states, self.n_dim), dtype=self.float, device=self.device
        )
        actions_tensor[is_eos] = torch.inf
        if torch.any(do_increments):
            actions_tensor[do_increments] = increments_abs
        if torch.any(is_bts):
            # BTS actions are equal to the originating states
            actions_bts = tfloat(
                states_from, float_type=self.float, device=self.device
            )[is_bts]
            actions_tensor[is_bts] = actions_bts
        actions = [tuple(a.tolist()) for a in actions_tensor]
        return actions, None

    def get_logprobs(
        self,
        policy_outputs: TensorType["n_states", "policy_output_dim"],
        actions: TensorType["n_states", "n_dim"],
        mask: TensorType["n_states", "3"],
        states_from: List,
        is_backward: bool,
    ) -> TensorType["batch_size"]:
        """
        Computes log probabilities of actions given policy outputs and actions.

        Args
        ----
        policy_outputs : tensor
            The output of the GFlowNet policy model.

        mask : tensor
            The mask containing information invalid actions and special cases.

        actions : tensor
            The actions (absolute increments) from each state in the batch for which to
            compute the log probability.

        states_from : tensor
            The states originating the actions, in GFlowNet format. They are required
            so as to compute the relative increments and the Jacobian.

        is_backward : bool
            True if the actions are backward, False if the actions are forward
            (default). Required, since the computation for forward and backward actions
            is different.
        """
        if is_backward:
            return self._get_logprobs_backward(
                policy_outputs, actions, mask, states_from
            )
        else:
            return self._get_logprobs_forward(
                policy_outputs, actions, mask, states_from
            )

    def _get_logprobs_forward(
        self,
        policy_outputs: TensorType["n_states", "policy_output_dim"],
        actions: TensorType["n_states", "n_dim"],
        mask: TensorType["n_states", "3"],
        states_from: List,
    ) -> TensorType["batch_size"]:
        """
        Computes log probabilities of forward actions.
        """
        # Initialize variables
        n_states = policy_outputs.shape[0]
        states_from_tensor = tfloat(
            states_from, float_type=self.float, device=self.device
        )
        is_eos = torch.zeros(n_states, dtype=torch.bool, device=self.device)
        logprobs_eos = torch.zeros(n_states, dtype=self.float, device=self.device)
        logprobs_increments_rel = torch.zeros(
            (n_states, self.n_dim), dtype=self.float, device=self.device
        )
        jacobian_diag = torch.ones(
            (n_states, self.n_dim), device=self.device, dtype=self.float
        )
        eos_tensor = tfloat(self.eos, float_type=self.float, device=self.device)
        # Determine source states
        is_source = ~mask[:, 1]
        # EOS is the only possible action if continuous actions are invalid (mask[0] is
        # True)
        is_eos_forced = mask[:, 0]
        is_eos[is_eos_forced] = True
        # Ensure that is_eos_forced does not include any source state
        assert not torch.any(torch.logical_and(is_source, is_eos_forced))
        # Get sampled EOS actions and get log probs from Bernoulli distribution
        do_eos = torch.logical_and(~is_source, ~is_eos_forced)
        if torch.any(do_eos):
            is_eos_sampled = torch.zeros_like(do_eos)
            is_eos_sampled[do_eos] = torch.all(actions[do_eos] == eos_tensor, dim=1)
            is_eos[is_eos_sampled] = True
            logits_eos = self._get_policy_eos_logit(policy_outputs)[do_eos]
            distr_eos = Bernoulli(logits=logits_eos)
            logprobs_eos[do_eos] = distr_eos.log_prob(
                is_eos_sampled[do_eos].to(self.float)
            )
        # Get log probs of relative increments if EOS was not the sampled or forced
        # action
        do_increments = ~is_eos
        if torch.any(do_increments):
            # Get absolute increments
            increments_abs = actions[do_increments]
            # Get minimum increments
            min_increments = torch.full_like(
                increments_abs, self.min_incr, dtype=self.float, device=self.device
            )
            min_increments[is_source[do_increments]] = 0.0
            # Get relative increments
            increments_rel = self.absolute_to_relative_increments(
                states_from_tensor[do_increments],
                increments_abs,
                min_increments,
                self.max_val,
                is_backward=False,
            )
            # Get logprobs
            distr_increments = self._make_increments_distribution(
                policy_outputs[do_increments]
            )
            # Clamp because increments of 0.0 or 1.0 would yield nan
            logprobs_increments_rel[do_increments] = distr_increments.log_prob(
                torch.clamp(increments_rel, min=1e-6, max=(1 - 1e-6))
            )
            # Compute diagonal of the Jacobian (see _get_jacobian_diag())
            jacobian_diag[do_increments] = self._get_jacobian_diag(
                states_from_tensor[do_increments],
                min_increments,
                self.max_val,
                is_backward=False,
            )
        # Get log determinant of the Jacobian
        log_det_jacobian = torch.sum(torch.log(jacobian_diag), dim=1)
        # Compute combined probabilities
        sumlogprobs_increments = logprobs_increments_rel.sum(axis=1)
        logprobs = logprobs_eos + sumlogprobs_increments + log_det_jacobian
        return logprobs

    def _get_logprobs_backward(
        self,
        policy_outputs: TensorType["n_states", "policy_output_dim"],
        actions: TensorType["n_states", "n_dim"],
        mask: TensorType["n_states", "3"],
        states_from: List,
    ) -> TensorType["batch_size"]:
        """
        Computes log probabilities of backward actions.
        """
        # Initialize variables
        n_states = policy_outputs.shape[0]
        states_from_tensor = tfloat(
            states_from, float_type=self.float, device=self.device
        )
        is_bts = torch.zeros(n_states, dtype=torch.bool, device=self.device)
        logprobs_bts = torch.zeros(n_states, dtype=self.float, device=self.device)
        logprobs_increments_rel = torch.zeros(
            (n_states, self.n_dim), dtype=self.float, device=self.device
        )
        jacobian_diag = torch.ones(
            (n_states, self.n_dim), device=self.device, dtype=self.float
        )
        # EOS is the only possible action only if done is True (mask[2] is False)
        is_eos = ~mask[:, 2]
        # Back-to-source (BTS) is the only possible action if mask[1] is False
        is_bts_forced = ~mask[:, 1]
        is_bts[is_bts_forced] = True
        # Get sampled BTS actions and get log probs from Bernoulli distribution
        do_bts = torch.logical_and(~is_bts_forced, ~is_eos)
        if torch.any(do_bts):
            # BTS actions are equal to the originating states
            is_bts_sampled = torch.zeros_like(do_bts)
            is_bts_sampled[do_bts] = torch.all(
                actions[do_bts] == states_from_tensor[do_bts], dim=1
            )
            is_bts[is_bts_sampled] = True
            logits_bts = self._get_policy_source_logit(policy_outputs)[do_bts]
            distr_bts = Bernoulli(logits=logits_bts)
            logprobs_bts[do_bts] = distr_bts.log_prob(
                is_bts_sampled[do_bts].to(self.float)
            )
        # Get log probs of relative increments if actions were neither BTS nor EOS
        do_increments = torch.logical_and(~is_bts, ~is_eos)
        if torch.any(do_increments):
            # Get absolute increments
            increments_abs = actions[do_increments]
            min_increments = torch.full_like(
                increments_abs, self.min_incr, dtype=self.float, device=self.device
            )
            # Get relative increments
            increments_rel = self.absolute_to_relative_increments(
                states_from_tensor[do_increments],
                increments_abs,
                min_increments,
                self.max_val,
                is_backward=True,
            )
            # Get logprobs
            distr_increments = self._make_increments_distribution(
                policy_outputs[do_increments]
            )
            # Clamp because increments of 0.0 or 1.0 would yield nan
            logprobs_increments_rel[do_increments] = distr_increments.log_prob(
                torch.clamp(increments_rel, min=1e-6, max=(1 - 1e-6))
            )
            # Compute diagonal of the Jacobian (see _get_jacobian_diag())
            jacobian_diag[do_increments] = self._get_jacobian_diag(
                states_from_tensor[do_increments],
                min_increments,
                self.max_val,
                is_backward=True,
            )
        # Get log determinant of the Jacobian
        log_det_jacobian = torch.sum(torch.log(jacobian_diag), dim=1)
        # Compute combined probabilities
        sumlogprobs_increments = logprobs_increments_rel.sum(axis=1)
        logprobs = logprobs_bts + sumlogprobs_increments + log_det_jacobian
        # Ensure that logprobs of forced EOS are 0
        logprobs[is_eos] = 0.0
        return logprobs

    @staticmethod
    def _get_jacobian_diag(
        states_from: TensorType["n_states", "n_dim"],
        min_increments: TensorType["n_states", "n_dim"],
        max_val: float,
        is_backward: bool,
    ):
        """
        Computes the diagonal of the Jacobian of the sampled actions with respect to
        the target states.

        Forward: the sampled variables are the relative increments r_f and the state
        updates (s -> s') are (assuming max_val = 1):

        s' = s + m + r_f(1 - s - m)
        r_f = (s' - s - m) / (1 - s - m)

        Therefore, the derivative of r_f wrt to s' is

        dr_f/ds' = 1 / (1 - s - m)

        Backward: the sampled variables are the relative decrements r_b and the state
        updates (s' -> s) are:

        s = s' - m - r_b(s' - m)
        r_b = (s' - s - m) / (s' - m)

        Therefore, the derivative of r_b wrt to s is

        dr_b/ds = -1 / (s' - m)

        We take the absolute value of the derivative (Jacobian).

        The derivatives of the components of r with respect to dimensions of s or s'
        other than itself are zero. Therefore, the Jacobian is diagonal and the
        determinant is the product of the diagonal.
        """
        epsilon = 1e-9
        max_val = torch.full_like(states_from, max_val)
        if is_backward:
            return 1.0 / ((states_from - min_increments) + epsilon)
        else:
            return 1.0 / ((max_val - states_from - min_increments) + epsilon)

    def _step(
        self,
        action: Tuple[float],
        backward: bool,
    ) -> Tuple[List[float], Tuple[float], bool]:
        """
        Updates self.state given a non-EOS action. This method is called by both step()
        and step_backwards(), with the corresponding value of argument backward.

        Args
        ----
        action : tuple
            Action to be executed. An action is a tuple of length n_dim, with the
            absolute increment for each dimension.

        backward : bool
            If True, perform backward step. Otherwise (default), perform forward step.

        Returns
        -------
        self.state : list
            The sequence after executing the action

        action : int
            Action executed

        valid : bool
            False, if the action is not allowed for the current state, e.g. stop at the
            root state
        """
        epsilon = 1e-9
        for dim, incr in enumerate(action):
            if backward:
                self.state[dim] -= incr
            else:
                self.state[dim] += incr
        # If state is close enough to source, set source to avoid escaping comparison
        # to source.
        if self.isclose(self.state, self.source, atol=1e-6):
            self.state = copy(self.source)
        if not all([s <= (self.max_val + epsilon) for s in self.state]):
            import ipdb

            ipdb.set_trace()
        assert all(
            [s <= (self.max_val + epsilon) for s in self.state]
        ), f"""
        State is out of cube bounds.
        \nState:\n{self.state}\nAction:\n{action}\nIncrement: {incr}
        """
        if not all([s >= (0.0 - epsilon) for s in self.state]):
            import ipdb

            ipdb.set_trace()
        assert all(
            [s >= (0.0 - epsilon) for s in self.state]
        ), f"""
        State is out of cube bounds.
        \nState:\n{self.state}\nAction:\n{action}\nIncrement: {incr}
        """
        return self.state, action, True

    # TODO: make generic for continuous environments
    def step(self, action: Tuple[float]) -> Tuple[List[float], Tuple[int, float], bool]:
        """
        Executes step given an action. An action is the absolute increment of each
        dimension.

        Args
        ----
        action : tuple
            Action to be executed. An action is a tuple of length n_dim, with the
            absolute increment for each dimension.

        Returns
        -------
        self.state : list
            The sequence after executing the action

        action : int
            Action executed

        valid : bool
            False, if the action is not allowed for the current state, e.g. stop at the
            root state
        """
        if self.done:
            return self.state, action, False
        if action == self.eos:
            assert self.state != self.source
            self.done = True
            self.n_actions += 1
            return self.state, self.eos, True
        # Otherwise perform action
        else:
            self.n_actions += 1
            self._step(action, backward=False)
            return self.state, action, True

    # TODO: make generic for continuous environments
    def step_backwards(
        self, action: Tuple[int, float]
    ) -> Tuple[List[float], Tuple[int, float], bool]:
        """
        Executes backward step given an action. An action is the absolute decrement of
        each dimension.

        Args
        ----
        action : tuple
            Action to be executed. An action is a tuple of length n_dim, with the
            absolute decrement for each dimension.

        Returns
        -------
        self.state : list
            The sequence after executing the action

        action : int
            Action executed

        valid : bool
            False, if the action is not allowed for the current state, e.g. stop at the
            root state
        """
        # If done is True, set done to False, increment n_actions and return same state
        if self.done:
            assert action == self.eos
            self.done = False
            self.n_actions += 1
            return self.state, action, True
        # Otherwise perform action
        else:
            assert action != self.eos
            self.n_actions += 1
            self._step(action, backward=True)
            return self.state, action, True

    def get_grid_terminating_states(self, n_states: int) -> List[List]:
        n_per_dim = int(np.ceil(n_states ** (1 / self.n_dim)))
        linspaces = [np.linspace(0, self.max_val, n_per_dim) for _ in range(self.n_dim)]
        states = list(itertools.product(*linspaces))
        # TODO: check if necessary
        states = [list(el) for el in states]
        return states

    def get_uniform_terminating_states(
        self, n_states: int, seed: int = None
    ) -> List[List]:
        rng = np.random.default_rng(seed)
        states = rng.uniform(low=0.0, high=self.max_val, size=(n_states, self.n_dim))
        return states.tolist()

    # TODO: make generic for all envs
    def fit_kde(self, samples, kernel="gaussian", bandwidth=0.1):
        return KernelDensity(kernel=kernel, bandwidth=bandwidth).fit(samples)

    def plot_reward_samples(
        self,
        samples,
        alpha=0.5,
        cell_min=-1.0,
        cell_max=1.0,
        dpi=150,
        max_samples=500,
        **kwargs,
    ):
        if self.n_dim != 2:
            return None
        # Sample a grid of points in the state space and obtain the rewards
        x = np.linspace(cell_min, cell_max, 201)
        y = np.linspace(cell_min, cell_max, 201)
        xx, yy = np.meshgrid(x, y)
        X = np.stack([xx, yy], axis=-1)
        states_mesh = torch.tensor(
            X.reshape(-1, 2), device=self.device, dtype=self.float
        )
        rewards = self.proxy2reward(self.proxy(states_mesh))
        # Init figure
        fig, ax = plt.subplots()
        fig.set_dpi(dpi)
        # Plot reward contour
        h = ax.contourf(xx, yy, rewards.reshape(xx.shape).cpu().numpy(), alpha=alpha)
        ax.axis("scaled")
        fig.colorbar(h, ax=ax)
        # Plot samples
        random_indices = np.random.permutation(samples.shape[0])[:max_samples]
        ax.scatter(samples[random_indices, 0], samples[random_indices, 1], alpha=alpha)
        # Figure settings
        ax.grid()
        padding = 0.05 * (cell_max - cell_min)
        ax.set_xlim([cell_min - padding, cell_max + padding])
        ax.set_ylim([cell_min - padding, cell_max + padding])
        plt.tight_layout()
        return fig

    # TODO: make generic for all envs
    def plot_kde(
        self,
        kde,
        alpha=0.5,
        cell_min=-1.0,
        cell_max=1.0,
        dpi=150,
        colorbar=True,
        **kwargs,
    ):
        if self.n_dim != 2:
            return None
        # Sample a grid of points in the state space and score them with the KDE
        x = np.linspace(cell_min, cell_max, 201)
        y = np.linspace(cell_min, cell_max, 201)
        xx, yy = np.meshgrid(x, y)
        X = np.stack([xx, yy], axis=-1)
        Z = np.exp(kde.score_samples(X.reshape(-1, 2))).reshape(xx.shape)
        # Init figure
        fig, ax = plt.subplots()
        fig.set_dpi(dpi)
        # Plot KDE
        h = ax.contourf(xx, yy, Z, alpha=alpha)
        ax.axis("scaled")
        if colorbar:
            fig.colorbar(h, ax=ax)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        # Set tight layout
        plt.tight_layout()
        return fig