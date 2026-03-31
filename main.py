import neat
import os
import argparse
import numpy as np

from environment.sandbox import Sandbox
from engine.neat_bridge import NeatBridge
from engine.compute_engine import ComputeEngine
from interface.visualizer import Visualizer
from interface.god_mode import GodMode
from data.logger import EvolutionLogger

def eval_genomes(genomes, config, sandbox, neat_bridge, max_ticks, render=False, visualizer=None):
    W, b, conn_counts = neat_bridge.compile_population(genomes, config, max_capacity=50)
    compute_engine = ComputeEngine(W, b, num_inputs=13, num_outputs=7)
    
    active_conn_counts = np.zeros(50, dtype=np.int32)
    num_starters = len(genomes)
    active_conn_counts[:num_starters] = conn_counts[:num_starters]
    
    sandbox._reset_environment(num_starters)
    
    for t in range(max_ticks):
        inputs = sandbox.get_sensory_inputs()
        actions = compute_engine.step(inputs)
        extinct = sandbox.step(actions, active_conn_counts)
        
        # Apply Mid-Gen Cloning to weights
        for pid, cid in sandbox.clones_produced_this_tick:
            compute_engine.clone_agent(pid, cid)
            active_conn_counts[cid] = active_conn_counts[pid]
            
        if render and visualizer:
            visualizer.render(actions, active_conn_counts)
            
        if extinct:
            break

    # Calculate genetic fitness based on absolute age and retained energy
    fitnesses = sandbox.agent_age + (sandbox.agent_energy * 0.1)
    for i, (genome_id, genome) in enumerate(genomes):
        genome.fitness = fitnesses[i]

def run(config_path, render=True, generations=100):
    config = neat.Config(
        neat.DefaultGenome,
        neat.DefaultReproduction,
        neat.DefaultSpeciesSet,
        neat.DefaultStagnation,
        config_path
    )
    
    pop = neat.Population(config)
    pop.add_reporter(neat.StdOutReporter(True))
    stats_reporter = neat.StatisticsReporter()
    pop.add_reporter(stats_reporter)

    sandbox = Sandbox(num_agents=config.pop_size, max_capacity=50, num_food=100, width=800, height=600)
    neat_bridge = NeatBridge(num_inputs=13, num_outputs=7, max_nodes=50)
    
    god_mode = GodMode(sandbox)
    visualizer = Visualizer(sandbox, god_mode, fps=30) if render else None
    
    logger = EvolutionLogger()
    max_ticks_per_gen = 600

    for gen in range(generations):
        def eval_func(genomes, config):
            eval_genomes(genomes, config, sandbox, neat_bridge, max_ticks_per_gen, render, visualizer)

        best_genome = pop.run(eval_func, 1)
        logger.log_generation(gen, best_genome.fitness, stats_reporter.get_fitness_mean()[-1], config.pop_size, len(pop.species.species))

    logger.save()
    if visualizer:
        visualizer.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser("ALIFE Evolution")
    parser.add_argument("--headless", action="store_true", help="Run without Pygame")
    args = parser.parse_args()
    
    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, 'config-feedforward')
    run(config_path, render=not args.headless, generations=100)
