import numpy as np

def normalize_angle(theta):
    return (theta + np.pi) % (2 * np.pi) - np.pi

class Sandbox:
    """
    IpaVerse Sandbox V2.0: Dual-Bar Biology (HP/Energy), Biome Friction Map,
    Trophic Cascades, Apex Predation locking, and Persistent Async Evolution.
    """
    # ── Energy constants ────────────────────────────────────────────────────
    MAX_ENERGY = 350.0   # V2.0: raised from 150 to support r/K reproduction thresholds
    MAX_HP     = 100.0   # V2.0: new secondary biological bar

    def __init__(self, num_agents=150, max_capacity=180, num_food=400, width=1600, height=1200):
        self.max_capacity = max_capacity
        self.num_food = num_food
        self.width = width
        self.height = height
        
        self.max_speed = 4.0
        self.vision_range = 200.0   # V2.0: scaled up for larger map (was 150)
        
        self.agent_positions = np.zeros((max_capacity, 2), dtype=np.float32)
        self.agent_angles = np.zeros(max_capacity, dtype=np.float32)
        self.agent_velocity = np.zeros((max_capacity, 2), dtype=np.float32)
        self.agent_energy = np.zeros(max_capacity, dtype=np.float32)
        self.agent_hp     = np.zeros(max_capacity, dtype=np.float32)  # V2.0: secondary biological bar
        self.agent_alive = np.zeros(max_capacity, dtype=bool)
        self.agent_age = np.zeros(max_capacity, dtype=np.int32)
        self.agent_signals = np.zeros(max_capacity, dtype=np.float32)
        
        # Apex Mechanics
        self.is_carnivore = np.zeros(max_capacity, dtype=bool)
        self.kill_count = np.zeros(max_capacity, dtype=np.int32)
        self.legendary_pulse_frames = 0
        self.true_sight = np.zeros(max_capacity, dtype=bool)
        
        # Tactical Shelters
        self.thickets = np.zeros((5, 3), dtype=np.float32) # x, y, radius — 5 thickets for larger map
        self.burrows  = np.zeros((2, 3), dtype=np.float32)  # 2 burrows for larger map

        # V2.0: Friction Map (Biomes) — list of (cx, cy, radius, friction_factor)
        self.friction_zones = []
        
        # Stealth & Defense metrics
        self.is_camouflaged = np.zeros(max_capacity, dtype=bool)
        self.is_overdriving = np.zeros(max_capacity, dtype=bool)
        self.in_thicket = np.zeros(max_capacity, dtype=bool)
        self.in_burrow = np.zeros(max_capacity, dtype=bool)
        self.burrow_time = np.zeros(max_capacity, dtype=np.int32)
        self.invulnerability_frames = np.zeros(max_capacity, dtype=np.int32)
        self.is_explorer = np.zeros(max_capacity, dtype=bool)
        self.high_speed_frames = np.zeros(max_capacity, dtype=np.int32)
        self.bite_frames    = np.zeros(max_capacity, dtype=np.int32)   # ticks biting (delayed carnivore lock)
        self.kill_cooldown  = np.zeros(max_capacity, dtype=np.int32)   # post-kill wait
        self.alarm_pressure = np.zeros(max_capacity, dtype=np.float32) # collective alarm signal
        self.alarm_timer    = np.zeros(max_capacity, dtype=np.int32)   # alarm duration
        self.signal_assists = np.zeros(max_capacity, dtype=np.int32)   # crédito por emisión de alarma útil
        self.frenzy_timer   = np.zeros(max_capacity, dtype=np.int32) 
        
        self.food_positions = np.zeros((self.num_food, 2), dtype=np.float32)
        self.food_active = np.zeros(self.num_food, dtype=bool)
        
        # Smart Food System: cluster centers dinámicos
        self.food_centers = np.column_stack([
            np.random.uniform(100, self.width - 100, 5),
            np.random.uniform(100, self.height - 100, 5)
        ]).astype(np.float32)  # 5 centros de cluster rotativos
        self.food_rotation_timer = 0
        
        # Premium Zone (Oasis) — centered on new map at start
        self.premium_pos = np.array([self.width / 2, self.height / 2], dtype=np.float32)
        self.premium_timer = 0
        
        # Drought System
        self.drought_active = False
        self.drought_timer = 0
        
        self.clones_produced_this_tick = []
        self.predation_events = [] # (x, y, killer_color)
        self.pulse_events = [] # (x, y) visually rendered refractive waves
        self.spawn_events = [] # (x, y) for spawn animation rings
        self.new_carnivores_this_tick = np.zeros(max_capacity, dtype=bool)
        self.reward_signal = np.zeros(max_capacity, dtype=np.float32)
        
        self.food_energy = np.zeros(self.num_food, dtype=np.float32) + 50.0  # V2.0: cluster baseline raised
        
        self._spawn_geography()
        
        self.sensory_inputs = np.zeros((max_capacity, 16), dtype=np.float32)  # V2.0: +1 for HP input
        
        self.big_crunch = False
        self.big_crunch_progress = 0.0
        self.oracle_deaths = 0
        
        self._reset_environment(num_agents)

    def _reset_environment(self, num_agents):
        self.agent_positions.fill(0.0)
        self.agent_angles.fill(0.0)
        self.agent_velocity.fill(0.0)
        self.agent_energy.fill(0.0)
        self.agent_hp.fill(0.0)         # V2.0: reset HP
        self.agent_alive.fill(False)
        self.agent_age.fill(0)
        self.agent_signals.fill(0.0)
        self.is_carnivore.fill(False)
        self.kill_count.fill(0)
        self.legendary_pulse_frames = 0
        self.is_camouflaged.fill(False)
        self.is_overdriving.fill(False)
        self.in_thicket.fill(False)
        self.in_burrow.fill(False)
        self.burrow_time.fill(0)
        self.invulnerability_frames.fill(100)
        self.is_explorer.fill(False)
        self.high_speed_frames.fill(0)
        self.bite_frames.fill(0)
        self.kill_cooldown.fill(0)
        self.alarm_pressure.fill(0.0)
        self.alarm_timer.fill(0)
        self.true_sight.fill(False)
        self.clones_produced_this_tick.clear()
        self.pulse_events.clear()
        self.spawn_events.clear()
        self.new_carnivores_this_tick.fill(False)
        self.frenzy_timer.fill(0)
        self.agent_positions[:num_agents, 0] = np.random.uniform(0, self.width, num_agents)
        self.agent_positions[:num_agents, 1] = np.random.uniform(0, self.height, num_agents)
        self.agent_angles[:num_agents] = np.random.uniform(0, 2*np.pi, num_agents)
        self.agent_energy[:num_agents] = self.MAX_ENERGY * 0.50  # Start at 50% energy
        self.agent_hp[:num_agents]     = self.MAX_HP              # V2.0: full HP on spawn
        self.agent_alive[:num_agents] = True

        self.food_active.fill(False)
        self._spawn_food(self.num_food)
    def _spawn_geography(self):
        # V2.0: 5 thickets distributed across the larger map
        for i in range(5):
            self.thickets[i] = [
                np.random.uniform(150, self.width - 150),
                np.random.uniform(150, self.height - 150),
                np.random.uniform(50, 80)
            ]
        # V2.0: 2 burrows
        for i in range(2):
            self.burrows[i] = [
                np.random.uniform(200, self.width - 200),
                np.random.uniform(200, self.height - 200),
                np.random.uniform(25, 35)
            ]
        # V2.0: Friction zones (Pantanos) — 3 biomes, fixed per geography seed
        self.friction_zones = []
        # Distribute across quadrants for spatial pressure
        quadrant_centers = [
            (self.width * 0.25, self.height * 0.25),
            (self.width * 0.75, self.height * 0.50),
            (self.width * 0.30, self.height * 0.75),
        ]
        for (qx, qy) in quadrant_centers:
            cx = qx + np.random.uniform(-100, 100)
            cy = qy + np.random.uniform(-80, 80)
            radius = np.random.uniform(120, 200)
            self.friction_zones.append((cx, cy, radius, 0.70))  # 0.70 factor = 30% velocity penalty
        self.predation_events.clear()

    def _spawn_food(self, amount, overwrite=False):
        """Spawn food clusters vectorizados. Respeta drought_active y usa food_centers rotativos."""
        if self.drought_active:
            return  # Sequía activa: bloqueo total de spawn de comida
        
        inactive_indices = np.where(~self.food_active)[0]
        spawns_needed = min(amount, len(inactive_indices))
        if overwrite:
            spawns_needed = amount
            if spawns_needed > len(inactive_indices):
                extra = spawns_needed - len(inactive_indices)
                active = np.where(self.food_active)[0]
                to_override = np.random.choice(active, min(extra, len(active)), replace=False)
                inactive_indices = np.concatenate([inactive_indices, to_override])
                
        if spawns_needed > 0:
            spawn_idx = np.random.choice(inactive_indices, spawns_needed, replace=False)
            n = len(spawn_idx)
            
            num_premium = int(np.ceil(0.7 * n))
            num_cluster = n - num_premium
            
            cx = np.zeros(n, dtype=np.float32)
            cy = np.zeros(n, dtype=np.float32)
            r  = np.zeros(n, dtype=np.float32)
            ang = np.random.uniform(0, 2 * np.pi, size=n)
            
            if num_premium > 0:
                cx[:num_premium] = self.premium_pos[0]
                cy[:num_premium] = self.premium_pos[1]
                r[:num_premium] = np.sqrt(np.random.uniform(0, 1, size=num_premium)) * 120.0
                
            if num_cluster > 0:
                center_assignments = np.random.randint(0, len(self.food_centers), size=num_cluster)
                cx[num_premium:] = self.food_centers[center_assignments, 0]
                cy[num_premium:] = self.food_centers[center_assignments, 1]
                r[num_premium:] = np.random.normal(0, 30.0, size=num_cluster)
            
            self.food_positions[spawn_idx, 0] = np.clip(cx + r * np.cos(ang), 0, self.width)
            self.food_positions[spawn_idx, 1] = np.clip(cy + r * np.sin(ang), 0, self.height)
            self.food_active[spawn_idx] = True
            
            # Oasis Energy: food spawned within 150px is worth 90.0 (V2.0 scaled)
            dists_to_oasis = np.linalg.norm(self.food_positions[spawn_idx] - self.premium_pos, axis=1)
            self.food_energy[spawn_idx] = np.where(dists_to_oasis < 150.0, 90.0, 50.0)

    def get_sensory_inputs(self):
        self.sensory_inputs.fill(0.0)
        alive_mask = self.agent_alive
        if not np.any(alive_mask): return self.sensory_inputs
        
        active_ids = np.where(alive_mask)[0]
        A = len(active_ids)
        pos = self.agent_positions[active_ids]
        angles = self.agent_angles[active_ids]
        
        self.sensory_inputs[active_ids, 0:9] = 1.0 
        
        def categorize_rays(rel_angles, distances, start_idx):
            valid = distances < self.vision_range
            m_c = valid & (rel_angles >= -np.pi/8) & (rel_angles <= np.pi/8)
            m_r = valid & (rel_angles >= -3*np.pi/8) & (rel_angles < -np.pi/8)
            m_l = valid & (rel_angles > np.pi/8) & (rel_angles <= 3*np.pi/8)
            for k, mask in enumerate([m_l, m_c, m_r]):
                dist_masked = np.where(mask, distances, np.inf)
                min_dist = np.min(dist_masked, axis=1)
                found = min_dist != np.inf
                norm_val = 1.0 - (min_dist[found] / self.vision_range)
                self.sensory_inputs[active_ids[found], start_idx + k] = norm_val

        active_food = self.food_positions[self.food_active]
        if len(active_food) > 0:
            diffs_f = active_food[np.newaxis, :, :] - pos[:, np.newaxis, :]
            dist_f = np.linalg.norm(diffs_f, axis=2)
            ang_f = normalize_angle(np.arctan2(diffs_f[:,:,1], diffs_f[:,:,0]) - angles[:, np.newaxis])
            categorize_rays(ang_f, dist_f, 3)
            
        if A > 1:
            diffs_a = pos[np.newaxis, :, :] - pos[:, np.newaxis, :]
            dist_a = np.linalg.norm(diffs_a, axis=2)
            np.fill_diagonal(dist_a, np.inf)
            ang_a = normalize_angle(np.arctan2(diffs_a[:,:,1], diffs_a[:,:,0]) - angles[:, np.newaxis])
            
            # ── Thicket Ambush Stealth ──────────────────────────────────────
            # If target is a predator in a thicket, perceived distance is 3.3x larger
            perceived_dist_a = dist_a.copy()
            bush_pred_global = self.is_carnivore & self.in_thicket
            # Map global bush predators to active_ids indices for the matrix column
            active_is_bush_pred = bush_pred_global[active_ids]
            perceived_dist_a[:, active_is_bush_pred] /= 0.3
            
            # ── Context Aware Vision ─────────────────────────────────────────
            # Herbivores only see Carnivores. Carnivores only see Herbivores.
            is_carn = self.is_carnivore[active_ids]
            target_mask = is_carn[:, np.newaxis] != is_carn[np.newaxis, :]
            perceived_dist_a[~target_mask] = np.inf
            
            categorize_rays(ang_a, perceived_dist_a, 6)
            # ────────────────────────────────────────────────────────────────
            
            # Input 11: Blood Scent (Max energy of neighbors within 120 units)
            energy_matrix = np.tile(self.agent_energy[active_ids], (A, 1))
            scent_mask = dist_a < 120.0
            visible_energies = np.where(scent_mask, energy_matrix, 0.0)
            self.sensory_inputs[active_ids, 11] = np.max(visible_energies, axis=1) / 150.0
            
            # Input 12: Target Velocity (Track the context-aware target)
            closest_idx = np.argmin(perceived_dist_a, axis=1)
            valid_closest = perceived_dist_a[np.arange(len(perceived_dist_a)), closest_idx] < np.inf
            
            for index, aid in enumerate(active_ids):
                if valid_closest[index]:
                    local_c_id = closest_idx[index]
                    global_c_id = active_ids[local_c_id]
                    vel_mag = np.linalg.norm(self.agent_velocity[global_c_id])
                    self.sensory_inputs[aid, 12] = np.clip(vel_mag / self.max_speed, 0.0, 1.0)
            
        for i, sector_offset in enumerate([np.pi/4, 0, -np.pi/4]):
            ray_angles = angles + sector_offset
            px = pos[:, 0] + np.cos(ray_angles) * self.vision_range
            py = pos[:, 1] + np.sin(ray_angles) * self.vision_range
            hit_wall = (px < 0) | (px > self.width) | (py < 0) | (py > self.height)
            self.sensory_inputs[active_ids[hit_wall], i] = 1.0 
            
        self.sensory_inputs[active_ids, 9] = self.agent_energy[active_ids] / self.MAX_ENERGY
        
        if A > 1:
            sig_emissions = self.agent_signals[active_ids]
            decay = np.maximum(0, 1.0 - (dist_a / 300.0))
            received = np.dot(decay, sig_emissions)
            self.sensory_inputs[active_ids, 10] = np.clip(received, 0.0, 1.0)
        
        # Collective alarm pressure overlays input 10 (predation proximity warning)
        self.sensory_inputs[active_ids, 10] = np.maximum(
            self.sensory_inputs[active_ids, 10],
            self.alarm_pressure[active_ids]
        )
        
        # ── Scent Vector & Compass (Inputs 14 & 15) ────────────────────────
        herbivores = np.where(~self.is_carnivore & self.agent_alive)[0]
        pred_active_mask = self.is_carnivore[active_ids]
        herb_active_mask = ~self.is_carnivore[active_ids]
        
        # Predator Scent: pointing to herbivore CoM
        if len(herbivores) > 0 and np.any(pred_active_mask):
            com = np.mean(self.agent_positions[herbivores], axis=0)
            diffs = com - pos
            dists = np.linalg.norm(diffs, axis=1, keepdims=True) + 1e-5
            units = diffs / dists
            self.sensory_inputs[active_ids[pred_active_mask], 13:15] = units[pred_active_mask]
            
        # Herbivore Compass: pointing to the Oasis
        if np.any(herb_active_mask):
            diffs_oasis = self.premium_pos - pos
            dists_oasis = np.linalg.norm(diffs_oasis, axis=1, keepdims=True) + 1e-5
            units_oasis = diffs_oasis / dists_oasis
            self.sensory_inputs[active_ids[herb_active_mask], 13:15] = units_oasis[herb_active_mask]
        # ──────────────────────────────────────────────────────────────────

        # V2.0 Input 15: Normalized HP — allows brain to develop hp-aware strategies
        self.sensory_inputs[active_ids, 15] = self.agent_hp[active_ids] / self.MAX_HP

        return self.sensory_inputs

    @property
    def in_premium_zone(self):
        """Boolean mask of agents within 120px of the Oasis center."""
        dists = np.linalg.norm(self.agent_positions - self.premium_pos, axis=1)
        return dists < 120.0

    def step(self, actions, active_conn_counts):
        self.clones_produced_this_tick.clear()
        self.predation_events.clear()
        self.pulse_events.clear()
        self.spawn_events.clear()
        self.new_carnivores_this_tick.fill(False)
        self.reward_signal = np.zeros(self.max_capacity, dtype=np.float32)
        alive_mask = self.agent_alive
        alive_indices = np.where(alive_mask)[0]
        
        # ── Smart Food System ──────────────────────────────────────────────
        self.food_rotation_timer += 1
        if self.food_rotation_timer >= 800:
            self.food_rotation_timer = 0
            # Rotación de centros: nuevas zonas de recursos (vectorizado)
            self.food_centers = np.column_stack([
                np.random.uniform(100, self.width  - 100, 5),
                np.random.uniform(100, self.height - 100, 5)
            ]).astype(np.float32)
        
        # ── Drought System ─────────────────────────────────────────────────
        self.drought_timer += 1
        if not self.drought_active and self.drought_timer >= 5000:   # cada ~167s a 30 FPS
            self.drought_active = True
            self.drought_timer = 0
        elif self.drought_active:
            if self.drought_timer >= 400:                             # dura ~13s a 30 FPS
                self.drought_active = False
                self.drought_timer = 0
        # ──────────────────────────────────────────────────────────────────
        
        # ── Premium Zone (Oasis) Rotation ──────────────────────────────────
        self.premium_timer += 1
        if self.premium_timer >= 2000:
            self.premium_timer = 0
            # V2.0: corners updated for 1600×1200 map
            corners = [
                (150, 150), (1450, 150),
                (150, 1050), (1450, 1050),
                (self.width // 2, self.height // 2)  # center as 5th option
            ]
            choice = np.random.randint(0, len(corners))
            self.premium_pos = np.array(corners[choice], dtype=np.float32)
            self.food_active.fill(False)
            self._spawn_food(self.num_food)
        # ──────────────────────────────────────────────────────────────────
        
        
        if self.big_crunch:
            self.legendary_pulse_frames = 0
            cx, cy = self.width/2, self.height/2
            diffs = np.array([cx, cy]) - self.agent_positions
            dists = np.linalg.norm(diffs, axis=1) + 1e-5
            dirs = diffs / dists[:, None]
            self.agent_positions += dirs * 15.0 # Suction
            self.big_crunch_progress += 0.015
            if self.big_crunch_progress >= 2.0:
                self.big_crunch = False
                self.big_crunch_progress = 0.0
                self._spawn_geography()
                self._reset_environment(len(alive_indices))
            return 
            
        # 0. Stealth Geography Check
        for aid in alive_indices:
            ax, ay = self.agent_positions[aid]
            dists_t = np.linalg.norm(self.thickets[:, :2] - [ax, ay], axis=1)
            self.in_thicket[aid] = np.any(dists_t < self.thickets[:, 2])
            dists_b = np.linalg.norm(self.burrows[:, :2] - [ax, ay], axis=1)
            self.in_burrow[aid] = np.any(dists_b < self.burrows[:, 2])

        # Active Camouflage Check
        self.is_camouflaged.fill(False)
        ghost_attempts = (actions[:, 4] > 0.7) & alive_mask & (self.agent_energy > 0.3)
        self.is_camouflaged[ghost_attempts] = True
        self.is_camouflaged |= self.in_thicket
        
        # Overdrive Check (Output 7)
        self.is_overdriving.fill(False)
        overdrive_attempts = (actions[:, 6] > 0.7) & alive_mask & (self.agent_energy > 3.0)
        self.is_overdriving[overdrive_attempts] = True
        
        # Kinetic Pulse Check (Output 6)
        pulse_attempts = (actions[:, 5] > 0.5) & alive_mask & (self.agent_energy > 30.0)
        valid_pulses = np.where(pulse_attempts)[0]
        if len(valid_pulses) > 0:
            mean_complexity = np.mean(active_conn_counts[alive_mask])
            for p_idx in valid_pulses:
                if active_conn_counts[p_idx] > mean_complexity:
                    self.agent_energy[p_idx] -= 30.0 # High neural cost
                    px, py = self.agent_positions[p_idx]
                    self.pulse_events.append((px, py))
                    
                    # Force Carnivores away
                    carnivores = np.where(self.is_carnivore & alive_mask)[0]
                    if len(carnivores) > 0:
                        c_pos = self.agent_positions[carnivores]
                        diffs = c_pos - [px, py]
                        dists = np.linalg.norm(diffs, axis=1) + 1e-4
                        in_range = dists < 100.0
                        affected = carnivores[in_range]
                        if len(affected) > 0:
                            dirs = diffs[in_range] / dists[in_range, None]
                            self.agent_positions[affected] += dirs * 40.0 # Radial physical repulse
        
        # 1. Evaluate Actions & Class Locking
        turn_demand = (actions[:, 0] - 1.0) * 0.5
        thrust_raw = actions[:, 1] - 0.5
        thrust = np.where(self.is_overdriving, thrust_raw * 1.5, np.clip(thrust_raw, -0.5, self.max_speed))
        thrust[self.kill_count >= 7] *= 1.05 # 5% Legendary speed boost
        
        self.agent_signals = np.clip(actions[:, 2] - 0.5, 0.0, 1.0)
        bite_demand = actions[:, 3]
        
        thrust[~alive_mask] = 0.0
        self.agent_signals[~alive_mask] = 0.0
        
        # [ALARMA EMERGENTE] Boost de velocidad para herbívoros que reciben señal de alarma intensa
        alarm_receivers = (self.sensory_inputs[:, 10] > 0.5) & alive_mask & ~self.is_carnivore
        thrust[alarm_receivers] *= 1.3  # Sprint de pánico vectorial
        
        biters = (bite_demand > 0.5) & alive_mask
        
        # Sustained biting required for carnivore conversion (30 ticks)
        self.bite_frames[biters] = np.minimum(self.bite_frames[biters] + 1, 60)
        self.bite_frames[~biters & alive_mask] = np.maximum(0, self.bite_frames[~biters & alive_mask] - 2)
        
        # First Blood Logic: only lock after sustained aggression
        new_biters = (self.bite_frames >= 30) & (~self.is_carnivore) & alive_mask
        if np.any(new_biters):
            self.agent_energy[new_biters] = 150.0 # Full heal when mutating into a predator
            self.new_carnivores_this_tick[new_biters] = True # Mark for neural bias injection
            # 15% probability of developing True Sight (Olfato/Rastreo)
            new_trackers = np.random.random(size=np.sum(new_biters)) < 0.15
            self.true_sight[new_biters] = new_trackers
            if np.any(new_trackers):
                print("[MUTACIÓN] Un Rastreador ha entrado en el ecosistema... el sigilo ya no es seguro.")
        self.is_carnivore[new_biters] = True  # Permanent lock after threshold
        
        # Modifier Penalties for Carnivores
        turn_delta = np.clip(turn_demand, -0.08, 0.08)
        turn_delta[self.is_carnivore] *= 1.0 # No Drag
        
        self.agent_angles[alive_mask] = normalize_angle(self.agent_angles[alive_mask] + turn_delta[alive_mask])
        
        vx = np.cos(self.agent_angles) * thrust
        vy = np.sin(self.agent_angles) * thrust
        
        self.agent_velocity[:, 0] += vx
        self.agent_velocity[:, 1] += vy

        # [KINETICS] Global atmospheric friction
        self.agent_velocity *= 0.85

        # [V2.0] Friction Map: apply per-zone velocity penalty vectorized
        if len(self.friction_zones) > 0:
            pos_alive = self.agent_positions  # shape (max_capacity, 2)
            for (zx, zy, zr, zf) in self.friction_zones:
                dz = pos_alive - np.array([zx, zy], dtype=np.float32)
                in_zone = (dz[:, 0]**2 + dz[:, 1]**2) < (zr * zr)
                in_zone &= alive_mask
                self.agent_velocity[in_zone] *= zf
        
        # Límite duro absoluto para evitar proyectiles infinitos
        hard_max_speed = 5.0
        self.agent_velocity = np.clip(self.agent_velocity, -hard_max_speed, hard_max_speed)
        
        self.agent_positions[:, 0] = np.clip(self.agent_positions[:, 0] + self.agent_velocity[:, 0], 0, self.width)
        self.agent_positions[:, 1] = np.clip(self.agent_positions[:, 1] + self.agent_velocity[:, 1], 0, self.height)
        
        speed_sq = self.agent_velocity[:, 0]**2 + self.agent_velocity[:, 1]**2
        
        # Explorer Morphogenesis Logic
        fast_agents = (speed_sq > self.max_speed**2) & alive_mask
        self.high_speed_frames[fast_agents] += 1
        self.high_speed_frames[~fast_agents] = 0
        new_explorers = self.high_speed_frames > 60
        self.is_explorer[new_explorers] = True
        
        # Camouflage Break Logic: if moving fast (speed > 50% max), lose camouflage overlay
        fast_runners = (speed_sq > (self.max_speed * 0.5)**2) & alive_mask
        self.is_camouflaged[fast_runners] = False
        
        # [LONGEVIDAD] Base cost: herbívoros -30% (0.14 vs 0.20), carnívoros x1.4 aplicado después
        herbivore_mask = ~self.is_carnivore
        energy_cost = np.where(herbivore_mask, 0.05, 0.08) + (speed_sq * 0.005)
        energy_cost[self.is_carnivore] *= 1.4  # Metabolismo carnívoro 1.4x
        energy_cost[ghost_attempts] += 0.20 # HEAVY neural camo cost to prevent hiding forever
        energy_cost[self.is_overdriving] += 0.02 # Overdrive adrenaline cost
        energy_cost[self.agent_signals > 0.5] += 0.40 # Semantic filter: metabolic cost to broadcasting noise
        energy_cost[self.in_burrow] *= 2.0 # Burrow stagnation multiplier
        energy_cost[alarm_receivers] += 0.1  # [ALARMA EMERGENTE] Costo metabólico del sprint de pánico
        
        # [FRENZY] Metabolic discount for hunters
        energy_cost[self.frenzy_timer > 0] *= 0.5
        
        # [V2.0] Carrying Capacity: kicks in at 15% of max_capacity (passive guardrail at ~150% target)
        cc_threshold = max(5, int(self.max_capacity * 0.15))
        carnivore_count = np.sum(self.is_carnivore & alive_mask)
        cc_multiplier = 1.0 + np.maximum(0.0, (carnivore_count - cc_threshold) * 0.05)
        energy_cost[self.is_carnivore & alive_mask] *= cc_multiplier
        
        # Burrow Force Eviction
        for aid in alive_indices:
            if self.in_burrow[aid]:
                self.burrow_time[aid] += 1
                if self.burrow_time[aid] > 150: # 5 second limit
                    self.in_burrow[aid] = False
                    self.burrow_time[aid] = 0
                    ang = np.random.uniform(0, 2*np.pi)
                    self.agent_positions[aid] += [np.cos(ang)*80, np.sin(ang)*80]
            else:
                self.burrow_time[aid] = max(0, self.burrow_time[aid] - 1)
        
        # [FRENZY] Hunger for glory decay
        self.frenzy_timer[self.frenzy_timer > 0] -= 1
        
        # Wall Repulsion (Anti-Stagnation)
        dist_x = np.minimum(self.agent_positions[:, 0], self.width - self.agent_positions[:, 0])
        dist_y = np.minimum(self.agent_positions[:, 1], self.height - self.agent_positions[:, 1])
        near_wall = (dist_x < 50.0) | (dist_y < 50.0)
        wall_huggers = near_wall & alive_mask
        
        if np.any(wall_huggers):
            cx, cy = self.width/2, self.height/2
            diffs = np.array([cx, cy]) - self.agent_positions[wall_huggers]
            dists = np.linalg.norm(diffs, axis=1) + 1e-5
            dirs = diffs / dists[:, None]
            self.agent_positions[wall_huggers] += dirs * 6.0
            energy_cost[wall_huggers] *= 5.0 # Camping penalty
            
        # [LONGEVIDAD] Bloating penalty was removed to allow Sages to hoard energy without dying rapidly.
        infancy_mask = self.agent_age < 300
        self.agent_energy -= np.where(infancy_mask, 0.03, energy_cost)
        self.agent_energy = np.clip(self.agent_energy, 0.0, self.MAX_ENERGY)
        
        # [REBALANCE] Hunger Magnetism removed — brain maintains full motor control even in starvation.
        # Thicket Energy Drain: agents inside thickets lose 0.05 energy per tick
        self.agent_energy[self.in_thicket & alive_mask] -= 0.05
        
        # Alarm timer decay
        active_alarm = self.alarm_timer > 0
        self.alarm_timer[active_alarm] -= 1
        self.alarm_pressure[self.alarm_timer > 0] = self.alarm_timer[self.alarm_timer > 0] / 60.0
        self.alarm_pressure[self.alarm_timer == 0] = 0.0
        
        # Frenzy timer decay
        self.frenzy_timer[self.frenzy_timer > 0] -= 1
        
        # Global Post-Kill Cooldown
        active_cooldown = self.kill_cooldown > 0
        self.kill_cooldown[active_cooldown] -= 1
        
        # Distance to all other agents (ignore dead and camouflaged)
        dist_a = np.linalg.norm(self.agent_positions[:, None, :] - self.agent_positions[None, :, :], axis=2)
        np.fill_diagonal(dist_a, np.inf)
        dist_a[:, ~self.agent_alive] = np.inf
        
        # Titan Tracking: Legendary predators ignore camo within 250 units
        # Mutants with True Sight ignore camo within their whole vision range
        legendary_predators = self.is_carnivore & (self.kill_count >= 7)
        true_sight_predators = self.is_carnivore & self.true_sight
        camo_mask = self.is_camouflaged.copy()
        
        for observer_id in range(self.max_capacity):
            if not self.agent_alive[observer_id]: continue
            
            if true_sight_predators[observer_id]:
                # "Olfato" total: ignoran el camuflaje estático completamente cerca
                is_camo_and_far = camo_mask & (dist_a[observer_id] >= self.vision_range)
                dist_a[observer_id, is_camo_and_far] = np.inf
            elif legendary_predators[observer_id]:
                is_camo_and_far = camo_mask & (dist_a[observer_id] >= 250.0)
                dist_a[observer_id, is_camo_and_far] = np.inf
            else:
                dist_a[observer_id, camo_mask] = np.inf
        
        # Spawn protection decreasing safely outside bounds
        self.invulnerability_frames[alive_indices] = np.maximum(0, self.invulnerability_frames[alive_indices] - 1)
        
        # 2. Bite Collisions / Active Predation (Optimized Vectorized Phase)
        active_biters = np.where(biters)[0]
        if len(active_biters) > 0 and len(alive_indices) > 1:
            # Broad-phase: only calculate distances for active biters vs everyone alive
            # Using squared distance to avoid expensive sqrt
            bite_radius_sq = 15.0**2
            pos_biters = self.agent_positions[active_biters]
            pos_all    = self.agent_positions
            
            for i, b_idx in enumerate(active_biters):
                if self.kill_cooldown[b_idx] > 0 or self.agent_energy[b_idx] <= 0:
                    continue
                
                # Check distances to all agents using squared differences (fast)
                dx = pos_all[:, 0] - pos_biters[i, 0]
                dy = pos_all[:, 1] - pos_biters[i, 1]
                dist_sq = dx**2 + dy**2
                
                # Filter visible targets within 15px
                visible_targets = np.where((dist_sq < bite_radius_sq) & self.agent_alive)[0]
                for victim in visible_targets:
                    if victim == b_idx: continue # Can't bite self
                    if self.in_burrow[victim] or self.invulnerability_frames[victim] > 0 or self.agent_energy[victim] <= 0: continue
                    
                    # Successful bite!
                    # [V2.0 DUAL-BAR] Bite drains VICTIM HP directly. Energy transferred to attacker.
                    # Predator HP drain from combat: 25 HP per successful bite.
                    self.agent_hp[victim] -= 25.0

                    # Trophic gain to attacker
                    if self.is_carnivore[victim]:
                        energy_stolen = 20.0 + max(0.0, self.agent_energy[victim] * 0.40)
                    else:
                        energy_stolen = 20.0 + self.agent_energy[victim] * 0.75  # Rich harvest

                    self.agent_energy[b_idx] = min(self.MAX_ENERGY, self.agent_energy[b_idx] + energy_stolen)
                    self.reward_signal[b_idx] = 1.0
                    v_pos = self.agent_positions[victim].copy()
                    self.predation_events.append((v_pos[0], v_pos[1], victim))
                    # V2.0: victim energy zeroed so kill triggers on hp<=0, not energy<=0
                    self.agent_energy[victim] = 0.0
                    
                    # Post-kill cooldown
                    self.kill_cooldown[b_idx] = 50
                    self.frenzy_timer[b_idx] = 300 # Frenzy reward
                    
                    # Alarm propagation: nearby herbivores get warned
                    nearby_prey = np.where(~self.is_carnivore & self.agent_alive)[0]
                    if len(nearby_prey) > 0:
                        d_alarm = np.linalg.norm(self.agent_positions[nearby_prey] - v_pos, axis=1)
                        alarmed = nearby_prey[d_alarm < 150.0]
                        self.alarm_pressure[alarmed] = 1.0
                        self.alarm_timer[alarmed] = 60
                    
                    # Canibalismo entre depredadores: herencia de kills
                    if self.is_carnivore[victim]:
                        self.kill_count[b_idx] += self.kill_count[victim]
                    
                    if self.agent_hp[victim] <= 0:
                        self.kill_count[b_idx] += 1
                        if self.kill_count[b_idx] > 0 and self.kill_count[b_idx] % 7 == 0:
                            self.legendary_pulse_frames = 15

                    break # Only bite one per tick
        
        # [ALARMA EMERGENTE] Atribución de crédito vectorial por señal de alarma útil
        strong_signalers = (self.agent_signals > 0.5) & alive_mask & ~self.is_carnivore
        herbivores_alive = alive_mask & ~self.is_carnivore # Cualquier herbívoro cercano es un receptor válido
        if np.any(strong_signalers) and sum(herbivores_alive) > 1:
            sig_pos   = self.agent_positions[strong_signalers]   # (S, 2)
            recv_pos  = self.agent_positions[herbivores_alive]    # (R, 2)
            # Distancias entre todos los pares signaler→receiver: (S, R)
            sig_to_recv = np.linalg.norm(
                sig_pos[:, np.newaxis, :] - recv_pos[np.newaxis, :, :], axis=2
            )
            # Solo contar receivers a menos de 400 px, y > 0 para no contarse a sí mismos
            in_range_matrix = (sig_to_recv < 400.0) & (sig_to_recv > 0.1)
            assists_gained  = np.sum(in_range_matrix, axis=1).astype(np.int32)
            
            sig_indices = np.where(strong_signalers)[0]
            self.signal_assists[sig_indices] += assists_gained
            
            # [HOTFIX] Refuerzo de Dopamina Social Hbbiano
            # Reduced to 0.05 to prevent 'Wireheading Seizures' where +1.0 every frame saturates all motor weights!
            successful = sig_indices[assists_gained > 0]
            self.reward_signal[successful] += 0.05
        # 3. Eating Passive Flora (V2.0 Spatial Optimization)
        if np.any(self.food_active) and np.any(self.agent_alive):
            active_food_idx = np.where(self.food_active)[0]
            
            # Grid cell_size = 100px. Agents only check their cell + neighbors.
            cell_size = 100.0
            food_grid = {}
            for f_i in active_food_idx:
                fx, fy = self.food_positions[f_i]
                gx, gy = int(fx // cell_size), int(fy // cell_size)
                if (gx, gy) not in food_grid: food_grid[(gx, gy)] = []
                food_grid[(gx, gy)].append(f_i)

            valid_grazers = ~self.is_carnivore[alive_indices] & (speed_sq[alive_indices] < 16.0) # Speed < 4.0
            grazing_indices = alive_indices[valid_grazers]
            
            global_foods_to_die = []
            healed_agents = []

            for idx in grazing_indices:
                ax, ay = self.agent_positions[idx]
                agx, agy = int(ax // cell_size), int(ay // cell_size)
                # Check 3x3 neighbor cells
                found_food = False
                for dx_g in [-1, 0, 1]:
                    for dy_g in [-1, 0, 1]:
                        cell = (agx + dx_g, agy + dy_g)
                        if cell in food_grid:
                            for f_idx in food_grid[cell]:
                                if not self.food_active[f_idx]: continue
                                fx, fy = self.food_positions[f_idx]
                                if (ax - fx)**2 + (ay - fy)**2 < 100.0: # Dist < 10px
                                    global_foods_to_die.append(f_idx)
                                    healed_agents.append(idx)
                                    self.food_active[f_idx] = False
                                    found_food = True
                                    break
                        if found_food: break
                    if found_food: break
            
            if len(healed_agents) > 0:
                healed_agents = np.array(healed_agents)
                global_foods_to_die = np.array(global_foods_to_die)
                self.reward_signal[healed_agents] = 1.0
                food_dens_mult = np.clip(self.num_food / max(1, np.sum(self.food_active)), 0.8, 1.5)
                this_food_energy = self.food_energy[global_foods_to_die] * food_dens_mult
                self.agent_energy[healed_agents] = np.clip(
                    self.agent_energy[healed_agents] + this_food_energy, 0.0, self.MAX_ENERGY
                )
                self._spawn_food(len(np.unique(global_foods_to_die)))

        # 4. Dual-Bar Death Hierarchy (V2.0)
        # Starvation: if energy == 0, drain HP at -2.0/tick (The "Agony" Factor)
        # This gives agents time to react to the HP sensory input.
        starving_mask = (self.agent_energy <= 0.0) & self.agent_alive
        self.agent_hp[starving_mask] = np.maximum(0.0, self.agent_hp[starving_mask] - 2.0)

        # Homeostasis: if energy > 70% max, burn 0.02*max_energy to heal +0.5 HP
        healing_mask = (self.agent_energy / self.MAX_ENERGY > 0.70) & self.agent_alive & (self.agent_hp < self.MAX_HP)
        self.agent_energy[healing_mask] -= 0.02 * self.MAX_ENERGY
        self.agent_hp[healing_mask] = np.minimum(self.agent_hp[healing_mask] + 0.5, self.MAX_HP)
        self.reward_signal[healing_mask] += 0.10  # Hebbian reinforcement for homeostasis

        # Real death trigger: hp <= 0 (replaces old energy <= 0 trigger)
        died_this_tick = (self.agent_hp <= 0) & self.agent_alive
        dead_indices = np.where(died_this_tick)[0]
        alive_post = np.where(self.agent_alive & ~died_this_tick)[0]
        
        if len(dead_indices) > 0 and len(alive_post) > 0:
            alpha_id = alive_post[np.argmax(self.agent_age[alive_post])]
            for died in dead_indices:
                self.oracle_deaths += 1
                # Materialización aleatoria en el mapa
                spawn_x = np.random.uniform(60, self.width - 60)
                spawn_y = np.random.uniform(60, self.height - 60)
                self.agent_positions[died, 0] = spawn_x
                self.agent_positions[died, 1] = spawn_y
                self.agent_angles[died] = np.random.uniform(0, 2 * np.pi)
                
                # [V2.0] Spawn energy: 40% of max. Prevents instant reproduction on tick 1.
                self.agent_energy[died] = self.MAX_ENERGY * 0.40
                self.agent_hp[died]     = self.MAX_HP          # V2.0: full HP on respawn
                
                self.agent_age[died] = 0
                # New agents always spawn as herbivores regardless of alpha type
                # This prevents predator monoculture — carnivores must re-earn that status
                self.is_carnivore[died] = False
                self.kill_count[died] = 0
                self.invulnerability_frames[died] = 30  # [REBALANCE] Reducido de 100 a 30 frames
                self.is_explorer[died] = False
                self.high_speed_frames[died] = 0
                self.bite_frames[died] = 0
                self.kill_cooldown[died] = 0
                self.alarm_pressure[died] = 0.0
                self.alarm_timer[died] = 0
                self.signal_assists[died] = 0  # [ALARMA EMERGENTE] reset créditos al renacer
                self.spawn_events.append((spawn_x, spawn_y))
                self.clones_produced_this_tick.append((alpha_id, died))
                self.agent_alive[died] = True 
                
        if len(alive_post) == 0:
            self.agent_alive[died_this_tick] = False

        # Independent High-End Clone Spawns (Mitosis)
        # V2.0 Asymmetric r/K thresholds (Fase 2.1 values — full r/K in Fase 2.3)
        herb_clone_ready = self.agent_alive & ~self.is_carnivore & (self.agent_energy >= 210.0)  # 60% of MAX_ENERGY
        carn_clone_ready = self.agent_alive & self.is_carnivore  & (self.agent_energy >= 280.0)  # 80% of MAX_ENERGY
        ready_to_clone = np.where(herb_clone_ready | carn_clone_ready)[0]
        for parent_id in ready_to_clone:
            inactive_slots = np.where(~self.agent_alive)[0]
            if len(inactive_slots) > 0:
                child_id = inactive_slots[0]
                self.agent_alive[child_id] = True
                self.agent_positions[child_id] = self.agent_positions[parent_id] + np.random.uniform(-5, 5, 2)
                self.agent_angles[child_id] = self.agent_angles[parent_id] + np.pi

                # V2.0 Asymmetric reproduction costs
                if self.is_carnivore[parent_id]:
                    repro_cost = self.agent_energy[parent_id] * 0.65  # Predator: 65% energy cost
                else:
                    repro_cost = self.agent_energy[parent_id] * 0.40  # Herbivore: 40% energy cost
                self.agent_energy[parent_id] -= repro_cost
                self.agent_energy[child_id] = repro_cost * 0.50  # Child gets 50% of what parent spent
                self.agent_hp[child_id]     = self.MAX_HP * 0.50  # V2.0: child born at 50% HP
                self.agent_age[child_id] = 0
                self.is_carnivore[child_id] = self.is_carnivore[parent_id]
                self.kill_count[child_id] = 0
                self.invulnerability_frames[child_id] = 30  # [REBALANCE] Reducido de 100 a 30 frames
                self.is_explorer[child_id] = False
                self.high_speed_frames[child_id] = 0
                self.bite_frames[child_id] = 0
                self.kill_cooldown[child_id] = 0
                self.alarm_pressure[child_id] = 0.0
                self.alarm_timer[child_id] = 0
                self.signal_assists[child_id] = 0  # [ALARMA EMERGENTE] hijo empieza sin créditos
                self.clones_produced_this_tick.append((parent_id, child_id))
        
        self.agent_age[self.agent_alive] += 1

        # [REBALANCE] Reduce continuous starvation penalty so it doesn't violently erase Hebbian learning
        self.reward_signal = np.where((self.agent_energy < 0.10 * self.MAX_ENERGY) & self.agent_alive, -0.05, self.reward_signal)
        
        return not np.any(self.agent_alive)
