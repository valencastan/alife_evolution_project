import numpy as np
import sys
import os

# Append project dir so we can import modules
sys.path.append(os.path.abspath('.'))

from engine.compute_engine import ComputeEngine
from engine.neat_bridge import NeatBridge

class DummyConfig:
    class GenomeConfig:
        input_keys = list(range(-15, 0))
        output_keys = list(range(7))
    genome_config = GenomeConfig()

class DummyGenome:
    def __init__(self):
        self.nodes = {}
        self.connections = {}

W = np.zeros((10, 50, 50), dtype=np.float32)
b = np.zeros((10, 50), dtype=np.float32)

engine = ComputeEngine(W, b, num_inputs=15, num_outputs=7)

# Simulate 1 step
inputs = np.ones((10, 15), dtype=np.float32)
engine.step(inputs)

# Give reward
reward = np.zeros(10, dtype=np.float32)
reward[0] = 1.0

engine.update_learning(current_energy=np.zeros(10), reward_signal=reward, lr=0.01)

print("W_learned max absolute element:", np.max(np.abs(engine.W_learned[0])))
print("W_learned agent 1 (no reward):", np.max(np.abs(engine.W_learned[1])))
