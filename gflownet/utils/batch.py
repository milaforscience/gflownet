from copy import deepcopy
from typing import Any

import numpy as np
import torch

from gflownet.utils.common import (
    set_device,
    set_float_precision,
    tbool,
    tfloat,
    tint,
    tlong,
)


class Batch:
    """
    Class to handle GFlowNet batches.

    loss: string
        String identifier of the GFlowNet loss.

    device: str or torch.device
        torch.device or string indicating the device to use ("cpu" or "cuda")

    float_type: torch.dtype or int
        One of float torch.dtype or an int indicating the float precision (16, 32 or
        64).

    Important note: one env should correspond to only one trajectory, all env_id should
    be unique.
    """

    def __init__(self, loss: str, device: Any = "cpu", float_type: Any = 32):
        # Device
        if isinstance(device, str):
            device = set_device(device)
        self.device = device
        # Float precision
        if isinstance(float_type, int):
            float_type = set_float_precision(float_type)
        self.float = float_type
        # Loss
        self.loss = loss
        # Initialize empty batch variables
        self.envs = dict()
        self.states = []
        self.actions = []
        self.done = []
        self.env_ids = []
        self.masks_invalid_actions_forward = []
        self.masks_invalid_actions_backward = []
        self.parents = []
        self.parents_actions = []
        self.steps = []

    def __len__(self):
        return len(self.states)

    def add_to_batch(self, envs, actions, valids, train=True):
        for env in envs:
            self.envs.update({env.id: env})

        for env, action, valid in zip(envs, actions, valids):
            if not valid:
                continue
            if train:
                self.states.append(deepcopy(env.state))
                self.actions.append(action)
                self.env_ids.append(env.id)
                self.done.append(env.done)
                self.steps.append(env.n_actions)
                mask_f = env.get_mask_invalid_actions_forward()
                self.masks_invalid_actions_forward.append(mask_f)
                if self.loss == "flowmatch":
                    parents, parents_a = env.get_parents(action=action)
                    assert (
                        action in parents_a
                    ), f"""
                    Sampled action is not in the list of valid actions from parents.
                    \nState:\n{env.state}\nAction:\n{action}
                    """
                    self.parents.append(parents)
                    self.parents_actions.append(parents_a)
                if self.loss == "trajectorybalance":
                    mask_b = env.get_mask_invalid_actions_backward(
                        env.state, env.done, [action]
                    )
                    self.masks_invalid_actions_backward.append(mask_b)
            else:
                if env.done:
                    self.states.append(env.state)
                    self.env_ids.append(env.id)
                    self.steps.append(env.n_actions)

    def process_batch(self):
        self._process_states()
        self.env_ids = tlong(self.env_ids, device=self.device)
        self.steps = tlong(self.steps, device=self.device)
        self._process_trajectory_indices()
        if len(self.actions) > 0:
            self.actions = tfloat(
                self.actions, device=self.device, float_type=self.float
            )
            self.done = tbool(self.done, device=self.device)
            self.masks_invalid_actions_forward = tbool(
                self.masks_invalid_actions_forward, device=self.device
            )
            if self.loss == "flowmatch":
                self.parents_state_idx = tlong(
                    sum([[idx] * len(p) for idx, p in enumerate(self.parents)], []),
                    device=self.device,
                )
                self.parents_actions = torch.cat(
                    [
                        tfloat(x, device=self.device, float_type=self.float)
                        for x in self.parents_actions
                    ]
                )
            elif self.loss == "trajectorybalance":
                self.masks_invalid_actions_backward = tbool(
                    self.masks_invalid_actions_backward, device=self.device
                )
            self._process_parents()

    def _process_states(self):
        self.state_gfn = tfloat(self.states, device=self.device, float_type=self.float)
        states = []
        for state, env_id in zip(self.states, self.env_ids):
            states.append(self.envs[env_id].state2policy(state))
        self.states = tfloat(states, device=self.device, float_type=self.float)

    def _process_parents(self):
        if self.loss == "flowmatch":
            parents = []
            for par, env_id in zip(self.parents, self.env_ids):
                parents.append(
                    tfloat(
                        self.envs[env_id.item()].statebatch2policy(par),
                        device=self.device,
                        float_type=self.float,
                    )
                )
            self.parents = torch.cat(parents)
        elif self.loss == "trajectorybalance":
            parents = torch.zeros_like(self.states)
            for env_id, traj in self.trajectory_indicies.items():
                parents[traj[0]] = tfloat(
                    self.envs[env_id].state2policy(self.envs[env_id].source),
                    device=self.device,
                    float_type=self.float,
                )
                parents[traj[1:]] = self.states[traj[:-1]]
            self.parents = parents

    def merge(self, another_batch):
        if self.loss != another_batch.loss:
            raise Exception("Cannot merge batches with different losses")
        self.envs.update(another_batch.envs)
        self.states += another_batch.states
        self.actions += another_batch.actions
        self.done += another_batch.done
        self.env_ids += another_batch.env_ids
        self.masks_invalid_actions_forward += (
            another_batch.masks_invalid_actions_forward
        )
        self.masks_invalid_actions_backward += (
            another_batch.masks_invalid_actions_backward
        )
        self.parents += another_batch.parents
        self.parents_actions += another_batch.parents_actions
        self.steps += another_batch.steps

    def _process_trajectory_indices(self):
        trajs = {env_id: [] for env_id in self.envs.keys()}
        for idx, (env_id, step) in enumerate(zip(self.env_ids, self.steps)):
            trajs[env_id.item()].append((idx, step))
        trajs = {
            env_id: list(map(lambda x: x[0], sorted(traj, key=lambda x: x[1])))
            for env_id, traj in trajs.items()
        }
        self.trajectory_indicies = trajs

    def unpack_terminal_states(self):
        """
        For storing terminal states and trajectory actions in the buffer
        Unpacks the terminating states and trajectories of a batch and converts them
        to Python lists/tuples.
        """
        # TODO: make sure that unpacked states and trajs are sorted by traj_id (like
        # rewards will be)
        if not hasattr(self, "trajectory_indicies"):
            self.process_batch()
        traj_actions = []
        terminal_states = []
        for traj_idx in self.trajectory_indicies.values():
            traj_actions.append(self.actions[traj_idx].tolist())
            terminal_states.append(tuple(self.state_gfn[traj_idx[-1]].tolist()))
        traj_actions = [tuple([tuple(a) for a in t]) for t in traj_actions]
        return terminal_states, traj_actions

    def compute_rewards(self):
        rewards = torch.zeros(len(self.state_gfn), device=self.device, dtype=self.float)
        for env_id, env in self.envs.items():
            idx = self.env_ids == env_id
            rewards[idx] = env.reward_torchbatch(self.state_gfn[idx], self.done[idx])
        return rewards
