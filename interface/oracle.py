import json
import os
import time
import numpy as np
import pickle
import itertools
import copyreg

# Fix for "cannot pickle 'itertools.count' object" on Windows Python builds
def _pickle_count(c):
    s = str(c)
    val = 0
    if s.startswith("count("):
        try:
            val = int(s[6:-1].split(',')[0])
        except ValueError:
            pass
    return (itertools.count, (val,))
copyreg.pickle(itertools.count, _pickle_count)

class Oracle:
    """
    Analyzes IpaVerse trends in real-time, deducing dominant archetypes 
    and maintaining the historic JSON "Book of History".
    Supports named worlds with per-world history directories.
    """
    def __init__(self, world_name="default"):
        self.world_name = world_name
        self.history_dir = os.path.join("history", world_name)
        os.makedirs(self.history_dir, exist_ok=True)
        self.total_deaths = 0

    def compute_archetype(self, active_conn_counts, actions, sandbox):
        alive_idx = np.where(sandbox.agent_alive)[0]
        if len(alive_idx) == 0:
            return "Vacío de Extinción", (100, 100, 100), "No hay vida."

        yellows = reds = blues = greens = legendaries = 0
        conn_mean = np.mean(active_conn_counts[alive_idx])
        speed_mean = np.mean(actions[alive_idx, 1])
        
        for idx in alive_idx:
            conns, signal, thrust = active_conn_counts[idx], actions[idx, 2], actions[idx, 1]
            if sandbox.is_carnivore[idx] and sandbox.kill_count[idx] >= 7:
                legendaries += 1
            elif conns > conn_mean + 2:
                yellows += 1
            elif sandbox.is_carnivore[idx] or signal > 0.5:
                reds += 1
            elif thrust > speed_mean + 0.2:
                blues += 1
            else:
                greens += 1
                
        counts = {"Los Sociables Inteligentes": yellows, "Los Depredadores Agresivos": reds, 
                  "Los Exploradores Rápidos": blues, "Los Herbívoros Pasivos": greens,
                  "Los Titanes Legendarios": legendaries}
        
        dom = max(counts, key=counts.get)
        colors = {"Los Sociables Inteligentes": (255,255,0), "Los Depredadores Agresivos": (255,50,50),
                  "Los Exploradores Rápidos": (50,100,255), "Los Herbívoros Pasivos": (50,255,50),
                  "Los Titanes Legendarios": (150,0,200)}
                  
        top_killer = int(np.max(sandbox.kill_count)) if len(sandbox.kill_count) > 0 else 0
        avg_age = int(np.mean(sandbox.agent_age[alive_idx]))
        num_carnivores = int(np.sum(sandbox.is_carnivore[alive_idx]))
        num_alive = len(alive_idx)
        
        stats_msg = f"Titanes:{legendaries} | Depredadores:{num_carnivores} | Edad Prom:{avg_age} | Récord:{top_killer}"
        return dom, colors[dom], stats_msg

    def save_epoch(self, dominant_archetype, peak_fitness, alpha_id, alpha_connections, blood_spilled=0, extra_stats=None):
        epoch_data = {
            "world_name": self.world_name,
            "timestamp": time.time(),
            "timestamp_readable": time.strftime("%Y-%m-%d %H:%M:%S"),
            "era_name": f"Era de {dominant_archetype}",
            "peak_fitness": float(peak_fitness),
            "alpha_id": int(alpha_id),
            "alpha_complexity": int(alpha_connections),
            "blood_spilled": int(blood_spilled)
        }
        if extra_stats:
            epoch_data.update(extra_stats)
        
        filename = os.path.join(self.history_dir, f"epoch_{int(time.time())}.json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(epoch_data, f, indent=4, ensure_ascii=False)
        # Silent history save

    def save_world(self, population, sandbox, tick):
        # Guardar Población Completa (Pickle)
        pop_file = os.path.join(self.history_dir, "neat_pop.pkl")
        with open(pop_file, 'wb') as f:
            pickle.dump(population, f)
            
        # Guardar Entorno Mínimo (JSON)
        env_file = os.path.join(self.history_dir, "env_state.json")
        env_data = {
            "tick": tick,
            "food_positions": sandbox.food_positions.tolist(),
            "food_active": sandbox.food_active.tolist(),
            "big_crunch_progress": float(sandbox.big_crunch_progress),
            "agent_age": sandbox.agent_age.tolist(),
            "is_carnivore": sandbox.is_carnivore.tolist(),
            "kill_count": sandbox.kill_count.tolist(),
            "true_sight": sandbox.true_sight.tolist()
        }
        with open(env_file, 'w') as f:
            json.dump(env_data, f)
            
        print(f"[ORÁCULO] Estado del mundo guardado exitosamente en tick {tick}.")

    def load_world(self, sandbox):
        pop_file = os.path.join(self.history_dir, "neat_pop.pkl")
        env_file = os.path.join(self.history_dir, "env_state.json")
        
        population = None
        tick = 0
        
        if os.path.exists(pop_file) and os.path.exists(env_file):
            try:
                with open(pop_file, 'rb') as f:
                    population = pickle.load(f)
                
                with open(env_file, 'r') as f:
                    env_data = json.load(f)
                    
                tick = env_data.get("tick", 0)
                food_pos = np.array(env_data.get("food_positions", sandbox.food_positions))
                food_act = np.array(env_data.get("food_active", sandbox.food_active), dtype=bool)
                
                # Inyectar posiciones de comida
                sandbox.num_food = len(food_pos)
                sandbox.food_positions = food_pos
                sandbox.food_active = food_act
                sandbox.big_crunch_progress = env_data.get("big_crunch_progress", 0.0)
                
                # Biología Restaurada
                if "agent_age" in env_data:
                    sandbox.agent_age[:] = np.array(env_data["agent_age"], dtype=np.int32)
                if "is_carnivore" in env_data:
                    sandbox.is_carnivore[:] = np.array(env_data["is_carnivore"], dtype=bool)
                if "kill_count" in env_data:
                    sandbox.kill_count[:] = np.array(env_data["kill_count"], dtype=np.int32)
                if "true_sight" in env_data:
                    sandbox.true_sight[:] = np.array(env_data["true_sight"], dtype=bool)
                
                print(f"[ORÁCULO] Mundo '{self.world_name}' restaurado exitosamente desde tick {tick}.")
            except Exception as e:
                print(f"[ERROR] Oráculo falló al cargar el mundo: {e}")
                population = None
                tick = 0
                
        return population, tick
