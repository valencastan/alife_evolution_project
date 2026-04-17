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

    def save_world(self, population, sandbox, tick, compute_engine=None):
        # ── NEAT population (pickle) ───────────────────────────────────────────────────
        pop_file = os.path.join(self.history_dir, "neat_pop.pkl")
        with open(pop_file, 'wb') as f:
            pickle.dump(population, f)

        # ── Sandbox scalar state (JSON) ───────────────────────────────────────────
        env_file = os.path.join(self.history_dir, "env_state.json")
        env_data = {
            "tick":                tick,
            "drought_active":      bool(sandbox.drought_active),
            "drought_timer":       int(sandbox.drought_timer),
            "food_rotation_timer": int(sandbox.food_rotation_timer),
            "big_crunch_progress": float(sandbox.big_crunch_progress),
        }
        with open(env_file, 'w') as f:
            json.dump(env_data, f)

        # ── All agent arrays + food (numpy .npz) ─────────────────────────────────
        arrays_file = os.path.join(self.history_dir, "sandbox_arrays.npz")
        np.savez_compressed(
            arrays_file,
            agent_positions       = sandbox.agent_positions,
            agent_angles          = sandbox.agent_angles,
            agent_velocity        = sandbox.agent_velocity,
            agent_energy          = sandbox.agent_energy,
            agent_hp              = sandbox.agent_hp,          # V2.0
            agent_alive           = sandbox.agent_alive,
            agent_age             = sandbox.agent_age,
            agent_signals         = sandbox.agent_signals,
            is_carnivore          = sandbox.is_carnivore,
            kill_count            = sandbox.kill_count,
            true_sight            = sandbox.true_sight,
            is_explorer           = sandbox.is_explorer,
            signal_assists        = sandbox.signal_assists,
            invulnerability_frames= sandbox.invulnerability_frames,
            kill_cooldown         = sandbox.kill_cooldown,
            alarm_pressure        = sandbox.alarm_pressure,
            alarm_timer           = sandbox.alarm_timer,
            bite_frames           = sandbox.bite_frames,
            food_positions        = sandbox.food_positions,
            food_active           = sandbox.food_active,
            food_centers          = sandbox.food_centers,
        )

        # ── Compute engine weights + states (numpy .npz, optional) ──────────────
        if compute_engine is not None:
            brain_file = os.path.join(self.history_dir, "brain_state.npz")
            np.savez_compressed(
                brain_file,
                W      = compute_engine.W,
                b      = compute_engine.b,
                states = compute_engine.states,
            )

        print(f"[ORÁCULO] Estado del mundo guardado exitosamente en tick {tick}.")

    def load_world(self, sandbox, compute_engine=None):
        pop_file    = os.path.join(self.history_dir, "neat_pop.pkl")
        env_file    = os.path.join(self.history_dir, "env_state.json")
        arrays_file = os.path.join(self.history_dir, "sandbox_arrays.npz")
        brain_file  = os.path.join(self.history_dir, "brain_state.npz")

        population = None
        tick       = 0

        if os.path.exists(pop_file) and os.path.exists(env_file):
            try:
                # ── NEAT population ────────────────────────────────────────────────
                with open(pop_file, 'rb') as f:
                    population = pickle.load(f)

                # ── Scalar state ───────────────────────────────────────────────────
                with open(env_file, 'r') as f:
                    env_data = json.load(f)

                tick                       = env_data.get("tick", 0)
                sandbox.drought_active     = bool(env_data.get("drought_active", False))
                sandbox.drought_timer      = int(env_data.get("drought_timer", 0))
                sandbox.food_rotation_timer= int(env_data.get("food_rotation_timer", 0))
                sandbox.big_crunch_progress= float(env_data.get("big_crunch_progress", 0.0))

                # ── Agent + food arrays ────────────────────────────────────────────
                if os.path.exists(arrays_file):
                    arrs = np.load(arrays_file)
                    sandbox.agent_positions[:]        = arrs["agent_positions"]
                    sandbox.agent_angles[:]           = arrs["agent_angles"]
                    sandbox.agent_velocity[:]         = arrs["agent_velocity"]
                    sandbox.agent_energy[:]           = arrs["agent_energy"]
                    # V2.0: backward-compatible HP restore
                    if "agent_hp" in arrs:
                        sandbox.agent_hp[:] = arrs["agent_hp"]
                    else:
                        sandbox.agent_hp[:] = sandbox.MAX_HP  # Legacy save: give full HP
                    sandbox.agent_alive[:]            = arrs["agent_alive"]
                    sandbox.agent_age[:]              = arrs["agent_age"]
                    sandbox.agent_signals[:]          = arrs["agent_signals"]
                    sandbox.is_carnivore[:]           = arrs["is_carnivore"]
                    sandbox.kill_count[:]             = arrs["kill_count"]
                    sandbox.true_sight[:]             = arrs["true_sight"]
                    sandbox.is_explorer[:]            = arrs["is_explorer"]
                    sandbox.signal_assists[:]         = arrs["signal_assists"]
                    sandbox.invulnerability_frames[:] = arrs["invulnerability_frames"]
                    sandbox.kill_cooldown[:]          = arrs["kill_cooldown"]
                    sandbox.alarm_pressure[:]         = arrs["alarm_pressure"]
                    sandbox.alarm_timer[:]            = arrs["alarm_timer"]
                    sandbox.bite_frames[:]            = arrs["bite_frames"]
                    sandbox.food_positions[:]         = arrs["food_positions"]
                    sandbox.food_active[:]            = arrs["food_active"]
                    sandbox.food_centers[:]           = arrs["food_centers"]
                else:
                    # Legacy fallback: old env_state.json embedded arrays
                    _ap = env_data.get("agent_age")
                    if _ap: sandbox.agent_age[:] = np.array(_ap, dtype=np.int32)
                    _ic = env_data.get("is_carnivore")
                    if _ic: sandbox.is_carnivore[:] = np.array(_ic, dtype=bool)
                    _kc = env_data.get("kill_count")
                    if _kc: sandbox.kill_count[:] = np.array(_kc, dtype=np.int32)
                    _ts = env_data.get("true_sight")
                    if _ts: sandbox.true_sight[:] = np.array(_ts, dtype=bool)
                    _fp = env_data.get("food_positions")
                    if _fp:
                        sandbox.food_positions[:] = np.array(_fp)
                        sandbox.food_active[:]    = np.array(env_data.get("food_active", sandbox.food_active), dtype=bool)

                # ── Brain state ─────────────────────────────────────────────────
                if compute_engine is not None and os.path.exists(brain_file):
                    brain = np.load(brain_file)
                    # Shape guard: only restore if dims match current engine
                    if (brain["W"].shape == compute_engine.W.shape and
                            brain["b"].shape == compute_engine.b.shape):
                        compute_engine.W[:]      = brain["W"]
                        compute_engine.b[:]      = brain["b"]
                        compute_engine.states[:] = brain["states"]
                    else:
                        print("[ORÁCULO] Brain shape mismatch — skipping neural restore.")

                print(f"[ORÁCULO] Mundo '{self.world_name}' restaurado exitosamente desde tick {tick}.")

            except Exception as e:
                print(f"[ERROR] Oráculo falló al cargar el mundo: {e}")
                population = None
                tick       = 0

        return population, tick
