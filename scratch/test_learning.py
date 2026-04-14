import numpy as np
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from engine.compute_engine import ComputeEngine

def test_initialization():
    W = np.random.randn(50, 50, 50).astype(np.float32)
    b = np.zeros((50, 50)).astype(np.float32)
    engine = ComputeEngine(W, b, num_inputs=13, num_outputs=7)
    
    assert hasattr(engine, 'W_learned')
    assert engine.W_learned.shape == W.shape
    assert np.all(engine.W_learned == 0)
    assert hasattr(engine, 'prev_energy')
    assert engine.prev_energy.shape == (50,)
    print("Initialization test passed!")

def test_learning_update():
    W = np.zeros((50, 50, 50), dtype=np.float32)
    b = np.zeros((50, 50), dtype=np.float32)
    engine = ComputeEngine(W, b, num_inputs=13, num_outputs=7)
    
    # Mock states: agent 0 has input activation
    engine.states[0, 0] = 1.0 # state_0 = 1.0
    engine.states[0, 13] = 1.0 # output_0 (index 13) = 1.0
    
    # Mock energy increase
    current_energy = np.zeros(50, dtype=np.float32)
    current_energy[0] = 1.0 # delta = 1.0
    
    engine.update_learning(current_energy, lr=1.0) # lr=1.0 for testing
    
    # Weight from node 0 to node 13 should be updated
    # grad[0, 13] = state[0] * state[13] = 1.0 * 1.0 = 1.0
    # W_learned[0, 0, 13] = 0 + 1.0 * 1.0 = 1.0
    assert engine.W_learned[0, 0, 13] == 1.0
    assert engine.prev_energy[0] == 1.0
    print("Learning update test passed!")

def test_cloning_inheritance():
    W = np.zeros((50, 50, 50), dtype=np.float32)
    b = np.zeros((50, 50), dtype=np.float32)
    engine = ComputeEngine(W, b, num_inputs=13, num_outputs=7)
    
    engine.W_learned[0, 0, 13] = 2.0
    engine.prev_energy[0] = 10.0
    
    engine.inherit_learned(0, 1, decay=0.5)
    
    assert engine.W_learned[1, 0, 13] == 1.0
    assert engine.prev_energy[1] == 10.0
    print("Inheritance test passed!")

if __name__ == "__main__":
    test_initialization()
    test_learning_update()
    test_cloning_inheritance()
