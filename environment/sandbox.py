import numpy as np

def normalize_angle(theta):
    return (theta + np.pi) % (2 * np.pi) - np.pi

class Sandbox:
    """
    IpaVerse Sandbox: Features Trophic Cascades, Apex Predation locking, 
    and Persistent Async Evolution.
    """
    def __init__(self, num_agents=50, max_capacity=50, num_food=100, width=800, height=600):
        self.max_capacity = max_capacity
        self.num_food = num_food
        self.width = width
        self.height = height
        
        self.max_speed = 6.0
        self.vision_range = 150.0
        
        self.agent_positions = np.zeros((max_capacity, 2), dtype=np.float32)
        self.agent_angles = np.zeros(max_capacity, dtype=np.float32)
        self.agent_velocity = np.zeros((max_capacity, 2), dtype=np.float32)
        self.agent_energy = np.zeros(max_capacity, dtype=np.float32)
        self.agent_alive = np.zeros(max_capacity, dtype=bool)
        self.agent_age = np.zeros(max_capacity, dtype=np.int32)
        self.agent_signals = np.zeros(max_capacity, dtype=np.float32)
        
        # Apex Mechanics
        self.is_carnivore = np.zeros(max_capacity, dtype=bool)
        self.kill_count = np.zeros(max_capacity, dtype=np.int32)
        self.legendary_pulse_frames = 0
        self.true_sight = np.zeros(max_capacity, dtype=bool)
        
        # Tactical Shelters
        self.thickets = np.zeros((3, 3), dtype=np.float32) # x, y, radius — 3 thickets (reduced)
        self.burrows = np.zeros((1, 3), dtype=np.float32)   # 1 burrow only (reduced)
        
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
        
        self.food_positions = np.zeros((self.num_food, 2), dtype=np.float32)
        self.food_active = np.zeros(self.num_food, dtype=bool)
        
        # Smart Food System: cluster centers dinámicos
        self.food_centers = np.column_stack([
            np.random.uniform(100, self.width - 100, 5),
            np.random.uniform(100, self.height - 100, 5)
        ]).astype(np.float32)  # 5 centros de cluster rotativos
        self.food_rotation_timer = 0
        
        # Drought System
        self.drought_active = False
        self.drought_timer = 0
        
        self.clones_produced_this_tick = []
        self.predation_events = [] # (x, y, killer_color)
        self.pulse_events = [] # (x, y) visually rendered refractive waves
        self.spawn_events = [] # (x, y) for spawn animation rings
        self.new_carnivores_this_tick = np.zeros(max_capacity, dtype=bool)
        
        self._spawn_geography()
        
        self.sensory_inputs = np.zeros((max_capacity, 13), dtype=np.float32)
        
        self.big_crunch = False
        self.big_crunch_progress = 0.0
        self.oracle_deaths = 0
        
        self._reset_environment(num_agents)

    def _reset_environment(self, num_agents):
        self.agent_positions.fill(0.0)
        self.agent_angles.fill(0.0)
        self.agent_velocity.fill(0.0)
        self.agent_energy.fill(0.0)
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
        self.agent_positions[:num_agents, 0] = np.random.uniform(0, self.width, num_agents)
        self.agent_positions[:num_agents, 1] = np.random.uniform(0, self.height, num_agents)
        self.agent_angles[:num_agents] = np.random.uniform(0, 2*np.pi, num_agents)
        self.agent_energy[:num_agents] = 100.0
        self.agent_alive[:num_agents] = True
        
        self.food_active.fill(False)
        self._spawn_food(self.num_food)
    def _spawn_geography(self):
        for i in range(3):  # 3 thickets — terrain is more open and dangerous
            self.thickets[i] = [np.random.uniform(100, self.width-100), np.random.uniform(100, self.height-100), np.random.uniform(40, 65)]
        for i in range(1):  # 1 burrow — hiding is a scarce resource
            self.burrows[i] = [np.random.uniform(150, self.width-150), np.random.uniform(150, self.height-150), np.random.uniform(21, 30)]
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
            
            # Asignar cada food item a un centro de cluster aleatorio (vectorizado)
            center_assignments = np.random.randint(0, len(self.food_centers), size=n)
            cx = self.food_centers[center_assignments, 0]
            cy = self.food_centers[center_assignments, 1]
            
            # Dispersíon gaussiana vectorial alrededor de los centros
            r   = np.random.normal(0, 30.0, size=n)
            ang = np.random.uniform(0, 2 * np.pi, size=n)
            self.food_positions[spawn_idx, 0] = np.clip(cx + r * np.cos(ang), 0, self.width)
            self.food_positions[spawn_idx, 1] = np.clip(cy + r * np.sin(ang), 0, self.height)
            self.food_active[spawn_idx] = True

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
            categorize_rays(ang_a, dist_a, 6)
            
            # Input 11: Blood Scent (Max energy of neighbors within 120 units)
            energy_matrix = np.tile(self.agent_energy[active_ids], (A, 1))
            scent_mask = dist_a < 120.0
            visible_energies = np.where(scent_mask, energy_matrix, 0.0)
            self.sensory_inputs[active_ids, 11] = np.max(visible_energies, axis=1) / 100.0
            
            # Input 12: Target Velocity (Ignore invisible targets)
            closest_idx = np.argmin(dist_a, axis=1)
            valid_closest = dist_a[np.arange(len(dist_a)), closest_idx] < np.inf
            
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
            
        self.sensory_inputs[active_ids, 9] = self.agent_energy[active_ids] / 100.0
        
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
            
        return self.sensory_inputs

    def step(self, actions, active_conn_counts):
        self.clones_produced_this_tick.clear()
        self.predation_events.clear()
        self.pulse_events.clear()
        self.spawn_events.clear()
        self.new_carnivores_this_tick.fill(False)
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
        if not self.drought_active and self.drought_timer >= 3000:   # cada 100s a 30 FPS
            self.drought_active = True
            self.drought_timer = 0
        elif self.drought_active:
            if self.drought_timer >= 600:                             # dura 20s a 30 FPS
                self.drought_active = False
                self.drought_timer = 0
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
        alarm_receivers = (self.sensory_inputs[:, 10] > 0.6) & alive_mask & ~self.is_carnivore
        thrust[alarm_receivers] *= 1.3  # Sprint de pánico vectorial
        
        biters = (bite_demand > 0.5) & alive_mask
        
        # Sustained biting required for carnivore conversion (30 ticks)
        self.bite_frames[biters] = np.minimum(self.bite_frames[biters] + 1, 60)
        self.bite_frames[~biters & alive_mask] = np.maximum(0, self.bite_frames[~biters & alive_mask] - 2)
        
        # First Blood Logic: only lock after sustained aggression
        new_biters = (self.bite_frames >= 30) & (~self.is_carnivore) & alive_mask
        if np.any(new_biters):
            self.agent_energy[new_biters] = 100.0 # Full heal when mutating into a predator
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
        
        self.agent_velocity[:, 0] = vx
        self.agent_velocity[:, 1] = vy
        self.agent_positions[:, 0] = np.clip(self.agent_positions[:, 0] + vx, 0, self.width)
        self.agent_positions[:, 1] = np.clip(self.agent_positions[:, 1] + vy, 0, self.height)
        
        speed_sq = vx**2 + vy**2
        
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
        energy_cost = np.where(herbivore_mask, 0.14, 0.20) + (speed_sq * 0.05)
        energy_cost[self.is_carnivore] *= 1.4  # Metabolismo carnívoro 1.4x
        energy_cost[ghost_attempts] += 0.20 # HEAVY neural camo cost to prevent hiding forever
        energy_cost[self.is_overdriving] += 0.02 # Overdrive adrenaline cost
        energy_cost[self.agent_signals > 0.5] += 0.08 # Semantic filter: metabolic cost to broadcasting noise
        energy_cost[self.in_burrow] *= 2.0 # Burrow stagnation multiplier
        energy_cost[alarm_receivers] += 0.3  # [ALARMA EMERGENTE] Costo metabólico del sprint de pánico
        
        # [REBALANCE] Carrying Capacity: kicks in from 30 carnivores (vectorizado)
        carnivore_count = np.sum(self.is_carnivore & alive_mask)
        cc_multiplier = 1.0 + np.maximum(0.0, (carnivore_count - 30) * 0.02)
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
            
        # Energy Saturation Cap & Bloating Penalty
        energy_cost[(self.agent_energy > 80.0) & ~self.is_carnivore] *= 1.5
        self.agent_energy -= energy_cost
        self.agent_energy = np.clip(self.agent_energy, 0.0, 100.0)
        
        # [REBALANCE] Hunger Magnetism removed — brain maintains full motor control even in starvation.
        # Thicket Energy Drain: agents inside thickets lose 0.05 energy per tick
        self.agent_energy[self.in_thicket & alive_mask] -= 0.05
        
        # Alarm timer decay
        active_alarm = self.alarm_timer > 0
        self.alarm_timer[active_alarm] -= 1
        self.alarm_pressure[self.alarm_timer > 0] = self.alarm_timer[self.alarm_timer > 0] / 60.0
        self.alarm_pressure[self.alarm_timer == 0] = 0.0
        
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
        
        # 2. Bite Collisions / Active Predation
        active_biters = np.where(biters)[0]
        if len(active_biters) > 0 and len(alive_indices) > 1:
            for b_idx in active_biters:
                if self.kill_cooldown[b_idx] > 0:
                    continue
                
                # Predators can bite anyone visible to them (handles Titan tracking and normal camo)
                visible_targets = np.where(dist_a[b_idx] < 15.0)[0]
                for victim in visible_targets:
                    if self.in_burrow[victim] or self.invulnerability_frames[victim] > 0: continue
                    
                    # Successful bite!
                    energy_stolen = np.maximum(40.0, self.agent_energy[victim]) # Massive harvest
                    self.agent_energy[b_idx] = min(100.0, self.agent_energy[b_idx] + energy_stolen)
                    v_pos = self.agent_positions[victim].copy()
                    self.predation_events.append((v_pos[0], v_pos[1], victim))
                    self.agent_energy[victim] = -10.0
                    
                    # Post-kill cooldown
                    self.kill_cooldown[b_idx] = 50
                    
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
                    
                    if self.agent_energy[victim] <= 0:
                        self.kill_count[b_idx] += 1
                        if self.kill_count[b_idx] > 0 and self.kill_count[b_idx] % 7 == 0:
                            self.legendary_pulse_frames = 15
                    
                    break # Only bite one per tick
        
        # [ALARMA EMERGENTE] Atribución de crédito vectorial por señal de alarma útil
        # Un emisor recibe crédito si: emite señal fuerte, hay alarm_receivers vivos cerca, y NO fue cazado este tick
        strong_signalers = (self.agent_signals > 0.5) & alive_mask & ~self.is_carnivore
        if np.any(strong_signalers) and np.any(alarm_receivers):
            sig_pos   = self.agent_positions[strong_signalers]   # (S, 2)
            recv_pos  = self.agent_positions[alarm_receivers]    # (R, 2)
            # Distancias entre todos los pares signaler→receiver: (S, R)
            sig_to_recv = np.linalg.norm(
                sig_pos[:, np.newaxis, :] - recv_pos[np.newaxis, :, :], axis=2
            )
            # Solo contar receivers dentro del rango de señal (300 unidades)
            in_range_matrix = sig_to_recv < 300.0          # (S, R) bool
            assists_gained  = np.sum(in_range_matrix, axis=1).astype(np.int32)  # (S,)
            sig_indices = np.where(strong_signalers)[0]
            self.signal_assists[sig_indices] += assists_gained
        
        # 3. Eating Passive Flora
        if np.any(self.food_active) and np.any(self.agent_alive):
            active_food_idx = np.where(self.food_active)[0]
            
            diffs = self.agent_positions[alive_indices, np.newaxis, :] - self.food_positions[active_food_idx][np.newaxis, :, :]
            dist_sq = diffs[:, :, 0]**2 + diffs[:, :, 1]**2
            eaters = np.any(dist_sq < 100.0, axis=1) & ~self.is_carnivore[alive_indices] # Carnivores can't eat green food
            
            if np.any(eaters):
                closest_food_local = np.argmin(dist_sq, axis=1)
                eater_mask = eaters & (dist_sq[np.arange(len(alive_indices)), closest_food_local] < 100.0)
                
                food_to_die = closest_food_local[eater_mask]
                global_foods_to_die = active_food_idx[food_to_die]
                self.food_active[global_foods_to_die] = False
                
                healed_agents = alive_indices[eater_mask]
                active_food_count = np.sum(self.food_active)
                food_density_ratio = np.clip(active_food_count / self.num_food, 0.2, 1.0)
                food_energy = np.clip(40.0 / food_density_ratio, 30.0, 60.0)  # Scarce = more energy
                self.agent_energy[healed_agents] = np.clip(self.agent_energy[healed_agents] + food_energy, 0, 100.0)
                self._spawn_food(len(np.unique(global_foods_to_die)))

        # 4. Handle Starvation & Core Async Replacement
        died_this_tick = (self.agent_energy <= 0) & self.agent_alive
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
                
                # [REBALANCE] Energia de spawn estandarizada — todos los agentes inician con la misma base.
                self.agent_energy[died] = 80.0
                
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
        # Herbivores reproduce faster (75 energy) — gives prey population recovery advantage
        herb_clone_ready = self.agent_alive & ~self.is_carnivore & (self.agent_energy >= 75.0)
        carn_clone_ready = self.agent_alive & self.is_carnivore  & (self.agent_energy >= 90.0)
        ready_to_clone = np.where(herb_clone_ready | carn_clone_ready)[0]
        for parent_id in ready_to_clone:
            inactive_slots = np.where(~self.agent_alive)[0]
            if len(inactive_slots) > 0:
                child_id = inactive_slots[0]
                self.agent_alive[child_id] = True
                self.agent_positions[child_id] = self.agent_positions[parent_id] + np.random.uniform(-5, 5, 2)
                self.agent_angles[child_id] = self.agent_angles[parent_id] + np.pi 
                self.agent_energy[parent_id] = 45.0
                self.agent_energy[child_id] = 45.0
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
        return not np.any(self.agent_alive)
