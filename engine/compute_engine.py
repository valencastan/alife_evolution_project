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

    def step(self, inputs):
        """
        inputs: shape (max_capacity, num_inputs)
        Returns: shape (max_capacity, num_outputs)
        """
        # We explicitly DO NOT zero the entire states array anymore.
        # This allows recursive feedback loops to persist (Recurrent RNN).
        self.states[:, :self.num_inputs] = inputs
        
        for _ in range(self.max_depth):
            Z = np.matmul(self.states[:, np.newaxis, :], self.W).squeeze(1) + self.b
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
