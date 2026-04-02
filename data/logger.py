import pandas as pd
import os
import time

class EvolutionLogger:
    """
    Persists generational fitness and speciation metrics to CSV for external plotting.
    """
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.run_id = f"run_{int(time.time())}"
        self.fitness_log_path = os.path.join(self.log_dir, f"{self.run_id}_fitness.csv")
        self.history = []

    def log_generation(self, generation, best_fitness, avg_fitness, pop_size, species_count):
        self.history.append({
            "generation": generation,
            "best_fitness": best_fitness,
            "avg_fitness": avg_fitness,
            "pop_size": pop_size,
            "species_count": species_count
        })
        print(f"[Camada {generation}] Aptitud Máx: {best_fitness:.2f} | Promedio: {avg_fitness:.2f} | Población: {pop_size} | Especies: {species_count}")

    def save(self):
        if self.history:
            df = pd.DataFrame(self.history)
            df.to_csv(self.fitness_log_path, index=False)
            print(f"Log saved to {self.fitness_log_path}")

