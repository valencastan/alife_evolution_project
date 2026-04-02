import json
import os
import time
import numpy as np

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
        print(f"[ORÁCULO] Historia actualizada: {filename}")
