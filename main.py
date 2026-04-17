import neat
import os
import argparse
import numpy as np
import pygame

from environment.sandbox import Sandbox
from engine.neat_bridge import NeatBridge
from engine.compute_engine import ComputeEngine
from interface.visualizer import Visualizer
from interface.god_mode import GodMode
from data.logger import EvolutionLogger

import sys

def resource_path(relative_path):
    """ Obtiene la ruta absoluta de los recursos, compatible con PyInstaller """
    try:
        # PyInstaller crea una carpeta temporal y guarda la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def run_infinite(config_path, world_name, render=True):
    """
    Simulación Infinita de IpaVerse.
    NEAT evoluciona en segundo plano cada 600 ticks.
    Los nuevos genomas entran al mundo a través de la muerte/respawn (Dead Queue).
    El sandbox nunca se reinicia salvo por Big Crunch manual.
    """
    config = neat.Config(
        neat.DefaultGenome,
        neat.DefaultReproduction,
        neat.DefaultSpeciesSet,
        neat.DefaultStagnation,
        config_path
    )
    
    sandbox = Sandbox(num_agents=config.pop_size, max_capacity=180, num_food=400, width=1600, height=1200)
    neat_bridge = NeatBridge(num_inputs=16, num_outputs=7, max_nodes=100)
    
    god_mode = GodMode(sandbox)
    visualizer = Visualizer(sandbox, god_mode, fps=30, world_name=world_name) if render else None
    
    # Intentar cargar mundo preexistente
    oracle_instance = visualizer.oracle if visualizer else None
    if not oracle_instance:
        from interface.oracle import Oracle
        oracle_instance = Oracle(world_name)

    loaded_pop, tick = oracle_instance.load_world(sandbox)

    pop = loaded_pop if loaded_pop is not None else neat.Population(config)

    # Silence all NEAT default reporters for clean logging
    pop.reporters.reporters.clear()

    # Initial genome compilation (always compile from saved/fresh pop first)
    initial_genomes = list(pop.population.items())
    W, b, conn_counts = neat_bridge.compile_population(initial_genomes, config, max_capacity=180)
    compute_engine = ComputeEngine(W, b, num_inputs=16, num_outputs=7)
    compute_engine.b[:, 15] += 1.0  # Center steering (Turn Angle)
    compute_engine.b[:, 16] += 0.8  # Dynamic forward thrust
    active_conn_counts = np.zeros(180, dtype=np.int32)
    active_species_ids = np.zeros(180, dtype=np.int32)
    num_starters = len(initial_genomes)
    for i, (gid, genome) in enumerate(initial_genomes):
        if i < 180:
            active_conn_counts[i] = len(genome.nodes) + len(genome.connections)
            sid = 0
            for k, s in pop.species.species.items():
                if gid in s.members:
                    sid = k
                    break
            active_species_ids[i] = sid

    # Restore brain weights + states into the live engine (must happen after engine exists)
    if loaded_pop is not None:
        oracle_instance.load_world(sandbox, compute_engine=compute_engine)
    
    # Genome pool for dead queue (new genomes assigned on respawn)
    genome_pool_W = None
    genome_pool_b = None
    genome_pool_conns = None
    genome_pool_species = None
    genome_pool_cursor = 0
    
    reached_premium_count = np.zeros(180, dtype=np.int32)
    
    drift_timer = 0
    
    if loaded_pop is not None:
        print(f"[IPAVERSE] Relinking to existing timeline for {world_name}. Welcome back.")
    else:
        print(f"[IPAVERSE] Mundo '{world_name}' iniciado en tick {tick}. Simulación infinita activa.")
    print(f"[IPAVERSE] Cierre la ventana para volver al menú.")
    
    while True:
        inputs = sandbox.get_sensory_inputs()
        actions = compute_engine.step(inputs)
        extinct = sandbox.step(actions, active_conn_counts)
        compute_engine.update_learning(sandbox.agent_energy, reward_signal=sandbox.reward_signal, lr=0.05)
        
        # Oasis Discovery Tracking (Herbivores only)
        herbivore_mask = ~sandbox.is_carnivore & sandbox.agent_alive
        reached_premium_count[herbivore_mask & sandbox.in_premium_zone] += 1
        
        # Apply Neural Bias to new predators
        if np.any(sandbox.new_carnivores_this_tick):
            for aid in np.where(sandbox.new_carnivores_this_tick)[0]:
                compute_engine.b[aid, 15] += 1.0 # Turn Bias (Node 15)
                compute_engine.b[aid, 16] += 0.8 # Acceleration Bias (Node 16)
        
        # Handle total extinction
        if extinct or not np.any(sandbox.agent_alive):
            if render and visualizer:
                # Show extinction overlay with restart/exit options
                result = visualizer.show_extinction_screen()
                if result == "RESTART":
                    sandbox._reset_environment(config.pop_size)
                    # Recompile fresh NEAT population
                    pop = neat.Population(config)
                    initial_genomes = list(pop.population.items())
                    W, b, conn_counts = neat_bridge.compile_population(initial_genomes, config, max_capacity=180)
                    compute_engine = ComputeEngine(W, b, num_inputs=16, num_outputs=7)
                    compute_engine.b[:, 15] += 1.0  # Center steering (Turn Angle)
                    compute_engine.b[:, 16] += 0.8  # Dynamic forward thrust
                    active_conn_counts = np.zeros(180, dtype=np.int32)
                    active_species_ids = np.zeros(180, dtype=np.int32)
                    for i, (gid, genome) in enumerate(initial_genomes):
                        if i < 180:
                            active_conn_counts[i] = len(genome.nodes) + len(genome.connections)
                            sid = 0
                            for k, s in pop.species.species.items():
                                if gid in s.members:
                                    sid = k
                                    break
                            active_species_ids[i] = sid
                    genome_pool_W = None
                    genome_pool_cursor = 0
                    reached_premium_count.fill(0)
                    tick = 0
                    print(f"[IPAVERSE] Mundo '{world_name}' reiniciado.")
                    continue
                elif result == "EXIT":
                    oracle_instance.save_world(pop, sandbox, tick, compute_engine=compute_engine)
                    visualizer.close()
                    return
            else:
                oracle_instance.save_world(pop, sandbox, tick, compute_engine=compute_engine)
                return
        
        # Handle agent death/respawn brain assignment
        for parent_id, child_id in sandbox.clones_produced_this_tick:
            if genome_pool_W is not None and genome_pool_cursor < genome_pool_W.shape[0]:
                compute_engine.W[child_id] = genome_pool_W[genome_pool_cursor]
                compute_engine.b[child_id] = genome_pool_b[genome_pool_cursor]
                compute_engine.reset_learned(child_id)
                # inherit learned weights from parent if available
                compute_engine.inherit_learned(parent_id, child_id, decay=0.7)
                compute_engine.states[child_id] = 0.0
                active_conn_counts[child_id] = genome_pool_conns[genome_pool_cursor]
                active_species_ids[child_id] = genome_pool_species[genome_pool_cursor]
                reached_premium_count[child_id] = 0
                compute_engine.b[child_id, 15] += 1.0  # Center steering
                compute_engine.b[child_id, 16] += 0.8  # Dynamic forward thrust
                genome_pool_cursor += 1
            else:
                compute_engine.clone_agent(parent_id, child_id)
                compute_engine.inherit_learned(parent_id, child_id, decay=0.7)
                active_conn_counts[child_id] = active_conn_counts[parent_id]
                active_species_ids[child_id] = active_species_ids[parent_id]
                compute_engine.b[child_id, 15] += 1.0  # Center steering
                compute_engine.b[child_id, 16] += 0.8  # Dynamic forward thrust
        
        genetic_drift_active = drift_timer > 0
        
        if render and visualizer:
            visualizer.render(actions, active_conn_counts, active_species_ids, genetic_drift_active,
                              tick=tick, generation=pop.generation, compute_engine=compute_engine)
            if visualizer.should_quit:
                oracle_instance.save_world(pop, sandbox, tick, compute_engine=compute_engine)
                visualizer.close()
                return
        
        tick += 1
        if drift_timer > 0:
            drift_timer -= 1
            
        # Background NEAT genetic drift every 1200 ticks
        if tick % 1200 == 0:
            drift_timer = 90  # Show indicator for ~3 seconds
            
            # [BALANCE] Connection penalty removed (was -connections×0.05); no longer penalizes neural complexity
            fitnesses = (
                (sandbox.agent_energy * 5.0)
                + (sandbox.agent_age.astype(float) * 0.1)
                + (sandbox.kill_count.astype(float) * 50.0)
                + (sandbox.signal_assists.astype(float) * 10.0)
                + (np.minimum(reached_premium_count.astype(float), 100.0) * 1.0)
            )
            
            # Set fitness on current NEAT population
            for i, (gid, genome) in enumerate(pop.population.items()):
                if i < 50:
                    genome.fitness = float(fitnesses[i])
                else:
                    genome.fitness = 0.0
            
            # Ensure no None fitness values
            for gid, genome in pop.population.items():
                if genome.fitness is None:
                    genome.fitness = 0.0
            
            try:
                # NEAT internal reproduction cycle
                new_pop = pop.reproduction.reproduce(
                    config, pop.species, config.pop_size, pop.generation)
                pop.population = new_pop
                pop.species.speciate(config, pop.population, pop.generation)
                pop.generation += 1
                
                # Compile new genome pool for Dead Queue
                new_genomes = list(pop.population.items())
                gW, gb, gc = neat_bridge.compile_population(new_genomes, config, max_capacity=50)
                genome_pool_W = gW
                genome_pool_b = gb
                genome_pool_conns = np.zeros(50, dtype=np.int32)
                genome_pool_species = np.zeros(50, dtype=np.int32)
                for i, (gid, genome) in enumerate(new_genomes):
                    if i < 50:
                        genome_pool_conns[i] = len(genome.nodes) + len(genome.connections)
                        sid = 0
                        for k, s in pop.species.species.items():
                            if gid in s.members:
                                sid = k; break
                        genome_pool_species[i] = sid
                genome_pool_cursor = 0
                
                # Silently updated the genome pool
            except Exception as e:
                # Silently handle population recovery
                try:
                    pop = neat.Population(config)
                    pop.species.speciate(config, pop.population, pop.generation)
                    # Silently recreated population
                except:
                    pass
        
        # Oracle periodic snapshot every 1200 ticks
        if tick % 1200 == 0:
            if render and visualizer:
                alive_indices = np.where(sandbox.agent_alive)[0]
                if len(alive_indices) > 0:
                    dom, col, stats = visualizer.oracle.compute_archetype(active_conn_counts, actions, sandbox)
                    alpha_idx = alive_indices[np.argmax(sandbox.agent_age[alive_indices])]
                    visualizer.oracle.save_epoch(
                        dom, sandbox.agent_age[alpha_idx], alpha_idx, 
                        active_conn_counts[alpha_idx], int(np.max(sandbox.kill_count)),
                        extra_stats={
                            "tick": tick,
                            "generation": pop.generation,
                            "population": len(alive_indices),
                            "avg_age": int(np.mean(sandbox.agent_age[alive_indices])),
                            "stats_line": stats
                        }
                    )
            # Guardado persitente cada ciclo natural (1 year)
            oracle_instance.save_world(pop, sandbox, tick, compute_engine=compute_engine)

if __name__ == "__main__":
    parser = argparse.ArgumentParser("IpaVerse - Simulador de Vida Artificial")
    parser.add_argument("--headless", action="store_true", help="Ejecutar sin Pygame")
    args = parser.parse_args()
    
    local_dir = os.path.dirname(__file__)
    config_path = resource_path('config-feedforward')
    
    if args.headless:
        run_infinite(config_path, world_name="headless", render=False)
    else:
        from interface.menu import MainMenu
        menu = MainMenu()
        while True:
            result = menu.run()
            if result == "START":
                world_name = menu.world_name
                run_infinite(config_path, world_name, render=True)
                # Restore menu display after returning from simulation
                menu.screen = pygame.display.set_mode((menu.width, menu.height))
                pygame.display.set_caption("IpaVerse: Menú Principal")
                # Reinitialize fonts (may be invalidated)
                menu.title_font = pygame.font.SysFont("Consolas", 48, bold=True)
                menu.font = pygame.font.SysFont("Consolas", 24)
                menu.small_font = pygame.font.SysFont("Consolas", 16)
            elif result == "EXIT":
                break
