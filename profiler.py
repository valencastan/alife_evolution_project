import cProfile
from memory_profiler import profile
from main import run
import os

@profile
def profile_memory(config_path):
    print("--- Memory Profiling (2 Generations) ---")
    run(config_path, render=False, generations=2)

def profile_cpu(config_path):
    print("--- CPU Profiling (2 Generations) ---")
    cProfile.run(f"run('{config_path}', render=False, generations=2)", sort='cumtime')

if __name__ == "__main__":
    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, 'config-feedforward')
    
    # Memory profiling first to catch GC spikes
    profile_memory(config_path)
    
    # CPU profiling
    profile_cpu(config_path)
