import json
import os
import time
import numpy as np

class Oracle:
    """
    Analyzes IpaVerse trends in real-time, deducing dominant archetypes 
    and maintaining the historic JSON "Book of History".
    """
    def __init__(self, history_dir="history"):
        self.history_dir = history_dir
        os.makedirs(self.history_dir, exist_ok=True)
        self.total_deaths = 0

    def compute_archetype(self, active_conn_counts, signals, thrusts, alive_mask):
        alive_idx = np.where(alive_mask)[0]
        if len(alive_idx) == 0:
            return "Extinct Void", (100, 100, 100)

        yellows = reds = blues = greens = 0
        conn_mean = np.mean(active_conn_counts[alive_idx])
        speed_mean = np.mean(thrusts[alive_idx])
        
        for idx in alive_idx:
            conns, signal, thrust = active_conn_counts[idx], signals[idx], thrusts[idx]
            if conns > conn_mean + 2:
                yellows += 1
            elif signal > 0.5:
                reds += 1
            elif thrust > speed_mean + 0.2:
                blues += 1
            else:
                greens += 1
                
        counts = {"The Intelligent Socialites": yellows, "The Aggressive Predators": reds, 
                  "The Fast Explorers": blues, "The Passive Grazers": greens}
        
        dom = max(counts, key=counts.get)
        colors = {"The Intelligent Socialites": (255,255,0), "The Aggressive Predators": (255,50,50),
                  "The Fast Explorers": (50,100,255), "The Passive Grazers": (50,255,50)}
                  
        return dom, colors[dom]

    def save_epoch(self, dominant_archetype, peak_fitness, alpha_id, alpha_connections):
        epoch_data = {
            "timestamp": time.time(),
            "era_name": f"Era of {dominant_archetype}",
            "peak_fitness": float(peak_fitness),
            "alpha_id": int(alpha_id),
            "alpha_complexity": int(alpha_connections)
        }
        
        filename = os.path.join(self.history_dir, f"epoch_{int(time.time())}.json")
        with open(filename, 'w') as f:
            json.dump(epoch_data, f, indent=4)
        print(f"[ORACLE] Book of History updated: {filename}")
