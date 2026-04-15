import numpy as np

class ComputeEngine:
    """
    High-performance NumPy vectorized inference engine.
    Supports Recurrent Memory (feed_forward = False) by retaining hidden state 
    activations across matrix multiplications (ticks).
    """
    def __init__(self, W, b, num_inputs=13, num_outputs=4, max_depth=2):
        self.W = W
        self.b = b
        self.num_inputs = num_inputs
        self.num_outputs = num_outputs
        self.max_depth = max_depth
        
        self.max_capacity = W.shape[0]
        self.max_nodes = W.shape[1]
        
        # State array persists between ticks for Memory 
        self.states = np.zeros((self.max_capacity, self.max_nodes), dtype=np.float32)
        self.W_learned = np.zeros_like(W)  # synaptic deltas, per-agent
        self.prev_energy = np.zeros(W.shape[0], dtype=np.float32)  # for delta_reward

    def step(self, inputs):
        """
        inputs: shape (max_capacity, num_inputs)
        Returns: shape (max_capacity, num_outputs)
        """
        # We explicitly DO NOT zero the entire states array anymore.
        # This allows recursive feedback loops to persist (Recurrent RNN).
        self.states[:, :self.num_inputs] = inputs
        
        for _ in range(self.max_depth):
            Z = np.matmul(self.states[:, np.newaxis, :], self.W + self.W_learned).squeeze(1) + self.b
            # [REBALANCE] Leaky Memory: decay 10% per tick to prevent node saturation and preserve plasticity
            self.states *= 0.9
            # Clipped ReLU to prevent infinite recurrent explosion
            states_new = np.clip(Z, 0.0, 10.0)
            states_new[:, :self.num_inputs] = inputs
            self.states = states_new
            
        out_start = self.num_inputs
        out_end = self.num_inputs + self.num_outputs
        return self.states[:, out_start:out_end]

    def clone_agent(self, parent_idx, child_idx):
        """Duplicates brain mappings AND short-term memory mid-generation."""
        self.W[child_idx] = np.copy(self.W[parent_idx])
        self.b[child_idx] = np.copy(self.b[parent_idx])
        self.states[child_idx] = np.copy(self.states[parent_idx])

    def update_learning(self, current_energy, reward_signal=None, lr=0.001):
        """Vectorized weight update using energy delta as reward signal OR a sparse impulse."""
        if reward_signal is not None:
            delta = reward_signal
        else:
            delta = np.clip(current_energy - self.prev_energy, -5.0, 5.0)  # (capacity,)
            # Soften negative rewards (punishment is 10x weaker)
            delta = np.where(delta < 0, delta * 0.1, delta)

        # outer product: each agent's state × output slice, scaled by reward
        out_start = self.num_inputs
        out_end = self.num_inputs + self.num_outputs
        for i in range(self.W.shape[0]):  # loop over agents OK — this runs 1x/tick not per-step
            grad = np.outer(self.states[i], np.zeros(self.W.shape[2]))
            grad[:, out_start:out_end] = np.outer(
                self.states[i], self.states[i, out_start:out_end]
            ) * delta[i]
            self.W_learned[i] = np.clip(
                self.W_learned[i] + lr * grad, -4.0, 4.0
            )
        self.prev_energy[:] = current_energy

    def get_effective_W(self):
        return self.W + self.W_learned

    def inherit_learned(self, parent_idx, child_idx, decay=0.7):
        """Child inherits parent's learned weights with decay."""
        self.W_learned[child_idx] = self.W_learned[parent_idx] * decay
        self.prev_energy[child_idx] = self.prev_energy[parent_idx]

    def reset_learned(self, idx):
        self.W_learned[idx] = 0.0
        self.prev_energy[idx] = 0.0
