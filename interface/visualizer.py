import pygame
import numpy as np
import sys
from interface.oracle import Oracle

class Visualizer:
    def __init__(self, sandbox, god_mode, fps=30):
        pygame.init()
        self.sandbox = sandbox
        self.god_mode = god_mode
        self.fps = fps
        
        # Dual-Layer Renderer for HUD Aspect Ratio scaling (Letterboxing)
        self.base_w = int(sandbox.width)  # 800
        self.base_h = int(sandbox.height) # 600
        self.real_screen = pygame.display.set_mode((1120, 600), pygame.RESIZABLE)
        pygame.display.set_caption("IpaVerse: Apex Intelligence & Trophic Cascades")
        self.virtual_screen = pygame.Surface((self.base_w, self.base_h))
        self.clock = pygame.time.Clock()
        
        # Initial black fill so blur doesn't composite over alpha-garbage
        self.virtual_screen.fill((5, 5, 8))
        
        self.font = pygame.font.SysFont("Consolas", 14)
        self.large_font = pygame.font.SysFont("Consolas", 24, bold=True)
        
        # Pre-cache Bloom Core Gradient High Res
        self.bloom_radius = 200
        self.bloom_surface = pygame.Surface((self.bloom_radius*2, self.bloom_radius*2), pygame.SRCALPHA)
        for i in range(self.bloom_radius, 0, -2):
            alpha = int(100 * (1.0 - (i / self.bloom_radius))**2)
            pygame.draw.circle(self.bloom_surface, (255, 255, 255, alpha), (self.bloom_radius, self.bloom_radius), i)
            
        self.cached_blooms = {}
        
        self.fade_surf = pygame.Surface((self.base_w, self.base_h), pygame.SRCALPHA)
        self.fade_surf.fill((5, 5, 8, 45))
        
        self.overlay_surf = pygame.Surface((self.base_w, self.base_h), pygame.SRCALPHA)
        self.overlay_surf.fill((0, 0, 0, 200))
        
        self.particles = [] 
        self.trails = {}    
        
        self.oracle = Oracle()
        self.oracle_msg = ""
        self.oracle_timer = 0
        self.full_screen_overlay = False
        
        self.last_alpha_id = -1
        self.laser_timer = 0
        self.laser_coords = ((0,0), (0,0))
        
        self.manual_zoom = 1.0
        self.camera_zoom = 1.0
        self.camera_target = np.array([self.base_w/2, self.base_h/2], dtype=np.float32)

    def _get_phenotype_color(self, idx, active_conn_counts, actions, alive_indices):
        if self.sandbox.is_carnivore[idx]:
            base_c = (200, 10, 10) # PERMANENT DEEP RED
        elif self.sandbox.is_overdriving[idx]:
            base_c = (0, 255, 255) # Electric Cyan / Adrenaline Overdrive
        else:
            conns = active_conn_counts[idx]
            thrust = actions[idx, 1]
            conn_mean = np.mean(active_conn_counts[alive_indices])
            speed_mean = np.mean(actions[alive_indices, 1])

            if conns > conn_mean + 2:
                base_c = (255, 255, 0)
            elif thrust > speed_mean + 0.2:
                base_c = (50, 100, 255)
            else:
                base_c = (50, 200, 50)
                
        return base_c

    def trigger_predation_sparks(self, event):
        x, y, victim = event
        for _ in range(25):
            vx, vy = np.random.uniform(-5, 5), np.random.uniform(-5, 5)
            self.particles.append([x, y, vx, vy, (255, 50, 50), 45, 4.0]) # Glowing Blood Sparks
            if len(self.particles) > 500:
                self.particles = self.particles[20:]
            
    def draw_polygon_glow(self, surface, color, pos, angle, radius, idx, active_conn_counts):
        mean_c = np.mean(active_conn_counts[self.sandbox.agent_alive])
        px, py = int(pos[0]), int(pos[1])
        radius = max(2, int(radius))
        
        is_carnivore = self.sandbox.is_carnivore[idx]
        is_smart     = active_conn_counts[idx] > mean_c * 1.2
        is_explorer  = self.sandbox.is_explorer[idx]
        
        points = []
        if is_carnivore: # 3 Points Arrowhead (Forward tip spearheads the angle)
            points.append((px + radius * 1.5 * np.cos(angle), py + radius * 1.5 * np.sin(angle)))
            points.append((px + radius * 0.8 * np.cos(angle + 2.6), py + radius * 0.8 * np.sin(angle + 2.6)))
            points.append((px + radius * 0.8 * np.cos(angle - 2.6), py + radius * 0.8 * np.sin(angle - 2.6)))
        elif is_smart: # 5 Points Pentagon (Higher Priority than Explorer)
            for i in range(5):
                points.append((px + radius * np.cos(angle + i * 2*np.pi/5), py + radius * np.sin(angle + i * 2*np.pi/5)))
        elif is_explorer: # 4 Points Rhombus
            points.append((px + radius * np.cos(angle), py + radius * np.sin(angle)))
            points.append((px + radius/2 * np.cos(angle + np.pi/2), py + radius/2 * np.sin(angle + np.pi/2)))
            points.append((px + radius * np.cos(angle + np.pi), py + radius * np.sin(angle + np.pi)))
            points.append((px + radius/2 * np.cos(angle - np.pi/2), py + radius/2 * np.sin(angle - np.pi/2)))
        
        # Hard Light Alpha Blur Matrix
        s = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
        dx, dy = radius*2, radius*2
        
        if len(points) > 2:
            points = [(int(p[0]), int(p[1])) for p in points]
            pygame.draw.polygon(surface, color, points, 0)
            pygame.draw.polygon(surface, (255, 255, 255), points, 1) # Hard Light Edges
            
            s_pts = [(int(p[0]-px+dx), int(p[1]-py+dy)) for p in points]
            pygame.draw.polygon(s, (*color, 60), s_pts, 0)
            pygame.draw.polygon(s, (*color, 90), s_pts, max(1, int(radius/2))) 
            
            # Apex Legendary Predator Marker
            if is_carnivore and self.sandbox.kill_count[idx] >= 7:
                inner_pts = [((px + p[0])/2, (py + p[1])/2) for p in points]
                pygame.draw.polygon(surface, (255, 50, 50), inner_pts, 1) 
        else:
            # Native Circle Prey
            pygame.draw.circle(surface, color, (px, py), radius)
            pygame.draw.circle(surface, (255, 255, 255), (px, py), radius, 1)
            lx = px + int(np.cos(angle) * (radius+4))
            ly = py + int(np.sin(angle) * (radius+4))
            pygame.draw.line(surface, (255, 255, 255), (px, py), (lx, ly), 1)
            
            pygame.draw.circle(s, (*color, 60), (dx, dy), radius+2)
            
        surface.blit(s, (px - dx, py - dy))

    def update_and_draw_particles(self):
        surviving = []
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            p[5] -= 1
            if p[5] > 0:
                # Discern Pulse expansion (Refraction wave) from generic sparks
                if p[4] == (200, 200, 200) and p[6] == 150.0:
                    rad = max(1, int((1.0 - (p[5] / 30.0)) * p[6]))
                    layer_alpha = int(255 * (p[5] / 30.0))
                    surf = pygame.Surface((rad*2, rad*2), pygame.SRCALPHA)
                    pygame.draw.circle(surf, (150, 150, 150, layer_alpha), (rad, rad), rad, 6)
                    self.virtual_screen.blit(surf, (int(p[0]-rad), int(p[1]-rad)))
                else:
                    rad = max(1, int((p[5] / 45.0) * p[6]))
                    pygame.draw.circle(self.virtual_screen, p[4], (int(p[0]), int(p[1])), rad)
                surviving.append(p)
        self.particles = surviving

    def update_and_draw_trails(self, alive_indices):
        top_10 = sorted(alive_indices, key=lambda x: self.sandbox.agent_age[x], reverse=True)[:10]
        to_delete = [k for k in self.trails.keys() if k not in top_10]
        for k in to_delete:
            del self.trails[k]

        for aid in top_10:
            if self.sandbox.is_camouflaged[aid]: 
                # Flush trail gracefully so it doesn't suddenly teleport when reappearing
                if aid in self.trails: self.trails[aid].clear()
                continue
            if aid not in self.trails:
                self.trails[aid] = []
            pos = self.sandbox.agent_positions[aid]
            self.trails[aid].append((int(pos[0]), int(pos[1])))
            
            t_len = 100 if self.sandbox.is_overdriving[aid] else 50
            if len(self.trails[aid]) > t_len: 
                self.trails[aid].pop(0)
                
            if len(self.trails[aid]) > 1:
                pts = self.trails[aid]
                c = (200, 20, 20) if self.sandbox.kill_count[aid] >= 7 else (100, 100, 100)
                for i in range(len(pts)-1):
                    alpha = int((i / len(pts)) * 100)
                    pygame.draw.line(self.virtual_screen, (*c, alpha), pts[i], pts[i+1], 2 if c[0]>100 else 1)

    def render(self, actions, active_conn_counts):
        # 1. Motion Blur Fading layer
        self.virtual_screen.blit(self.fade_surf, (0,0))
        
        self.real_screen.fill((5, 5, 5)) # Laboratory Sidebar Background

        window_w, window_h = self.real_screen.get_size()
        hud_width = 320
        sim_w = max(10, window_w - hud_width)
        scale = min(sim_w / self.base_w, window_h / self.base_h)
        scaled_w = int(self.base_w * scale)
        scaled_h = int(self.base_h * scale)
        offset_x = hud_width + (sim_w - scaled_w) // 2
        offset_y = (window_h - scaled_h) // 2

        # Map Mouse clicks to scaled virtual screen
        def get_virtual_mouse(m_pos):
            mx, my = m_pos
            vx = (mx - offset_x) / scale
            vy = (my - offset_y) / scale
            return vx, vy

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.close()
                sys.exit()
            if event.type == pygame.VIDEORESIZE:
                self.real_screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            if event.type == pygame.MOUSEWHEEL:
                self.manual_zoom = max(1.0, self.manual_zoom + event.y * 0.1)
            if event.type == pygame.KEYDOWN:
                vx, vy = get_virtual_mouse(pygame.mouse.get_pos())
                if event.key == pygame.K_m: 
                    self.god_mode.trigger_meteor(vx, vy, radius=150.0)
                elif event.key == pygame.K_f: 
                    self.god_mode.trigger_flood()
                elif event.key == pygame.K_r: 
                    self.god_mode.trigger_radiation()
                elif event.key == pygame.K_BACKSPACE or event.key == pygame.K_ESCAPE:
                    self.god_mode.trigger_big_crunch()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: 
                vx, vy = get_virtual_mouse(event.pos)
                self.god_mode.trigger_meteor(vx, vy, radius=70.0)

        alive_mask = self.sandbox.agent_alive
        alive_indices = np.where(alive_mask)[0]

        if self.sandbox.oracle_deaths >= 100:
            self.sandbox.oracle_deaths = 0
            if len(alive_indices) > 0:
                dom, col = self.oracle.compute_archetype(active_conn_counts, actions[:,2], actions[:,1], alive_mask)
                self.oracle_msg = f"ORACLE POST-MORTEM: The Era is dominated by {dom}."
                self.oracle_timer = 180 
                self.full_screen_overlay = False

        if self.sandbox.big_crunch and self.sandbox.big_crunch_progress > 1.95 and not self.full_screen_overlay:
            if len(alive_indices) > 0:
                dom, col = self.oracle.compute_archetype(active_conn_counts, actions[:,2], actions[:,1], alive_mask)
                alpha = alive_indices[np.argmax(self.sandbox.agent_age[alive_indices])]
                self.oracle.save_epoch(dom, self.sandbox.agent_age[alpha], alpha, active_conn_counts[alpha])
                self.oracle_msg = f"BIG CRUNCH\nEra of {dom}\nAlpha Complexity: {active_conn_counts[alpha]}\nRestarting Environment..."
            else:
                self.oracle_msg = "BIG CRUNCH\nExtinction Reached.\nRestarting Environment..."
            self.oracle_timer = 240 
            self.full_screen_overlay = True

        # Draw Geographies
        frame_time = pygame.time.get_ticks() / 1000.0
        
        # Thickets
        for tx, ty, tr in self.sandbox.thickets:
            jitter = np.sin(frame_time * 10.0 + tx) * 4.0
            r_jit = tr + jitter
            # Fast alpha circle without recreating surface constantly 
            s = pygame.Surface((int(r_jit*2), int(r_jit*2)), pygame.SRCALPHA)
            pygame.draw.circle(s, (20, 80, 20, 100), (int(r_jit), int(r_jit)), int(r_jit))
            self.virtual_screen.blit(s, (int(tx - r_jit), int(ty - r_jit)))
            
        # Burrows
        for bx, by, br in self.sandbox.burrows:
            pygame.draw.circle(self.virtual_screen, (5, 5, 5), (int(bx), int(by)), int(br))
            pygame.draw.circle(self.virtual_screen, (80, 20, 80), (int(bx), int(by)), int(br), 2)
        
        # Draw Food
        for fx, fy in self.sandbox.food_positions[self.sandbox.food_active]:
            # Native additive bloom for food spots
            pygame.draw.circle(self.virtual_screen, (40, 150, 40), (int(fx), int(fy)), 4)
            pygame.draw.circle(self.virtual_screen, (100, 255, 100), (int(fx), int(fy)), 2)

        if len(alive_indices) > 0:
            for px, py in self.sandbox.pulse_events:
                self.particles.append([px, py, 0, 0, (200, 200, 200), 30, 150.0]) # Pulse Refraction Ring
                
            for p_event in self.sandbox.predation_events:
                self.trigger_predation_sparks(p_event)
                
            for parent, child in self.sandbox.clones_produced_this_tick:
                p_pos = self.sandbox.agent_positions[parent]
                c_pos = self.sandbox.agent_positions[child]
                p_col = self._get_phenotype_color(parent, active_conn_counts, actions, alive_indices)
                c_col = self._get_phenotype_color(child, active_conn_counts, actions, alive_indices)
                
                diff = c_pos - p_pos
                dist = np.linalg.norm(diff)
                if dist > 0.1:
                    dir_v = diff / dist
                    perp_v = np.array([-dir_v[1], dir_v[0]])
                    
                    for i in range(30):
                        t = i / 29.0
                        mid_c = (
                            int(p_col[0] + (c_col[0] - p_col[0]) * t),
                            int(p_col[1] + (c_col[1] - p_col[1]) * t),
                            int(p_col[2] + (c_col[2] - p_col[2]) * t)
                        )
                        
                        base_x = p_pos[0] + dir_v[0] * dist * t
                        base_y = p_pos[1] + dir_v[1] * dist * t
                        
                        w1 = np.sin(t * np.pi * 4) * 8.0
                        self.particles.append([base_x + perp_v[0] * w1, base_y + perp_v[1] * w1, 0, 0, mid_c, 45, 2.0])
                        
                        w2 = np.sin(t * np.pi * 4 + np.pi) * 8.0
                        self.particles.append([base_x + perp_v[0] * w2, base_y + perp_v[1] * w2, 0, 0, mid_c, 45, 2.0])
                        
                        if len(self.particles) > 500:
                            self.particles = self.particles[20:]
            
            self.update_and_draw_trails(alive_indices)
            alpha_idx = alive_indices[np.argmax(self.sandbox.agent_age[alive_indices])]
            
            # Auto-Zoom Camera targeted on Alpha Biter Context
            target_zoom = self.manual_zoom
            target_pos = np.array([self.base_w/2, self.base_h/2], dtype=np.float32)
            if actions[alpha_idx, 3] > 0.8: # Alpha is Hunting
                target_zoom = max(self.manual_zoom, 1.8)
                target_pos = self.sandbox.agent_positions[alpha_idx]
            
            # Smooth Camera LERP
            self.camera_zoom += (target_zoom - self.camera_zoom) * 0.05
            self.camera_target += (target_pos - self.camera_target) * 0.05
            
            if self.last_alpha_id != -1 and self.last_alpha_id != alpha_idx and self.sandbox.agent_alive[alpha_idx]:
                if not self.sandbox.agent_alive[self.last_alpha_id]: 
                    old_pos = self.sandbox.agent_positions[self.last_alpha_id]
                    new_pos = self.sandbox.agent_positions[alpha_idx]
                    self.laser_coords = ((int(old_pos[0]), int(old_pos[1])), (int(new_pos[0]), int(new_pos[1])))
                    self.laser_timer = 30 
            self.last_alpha_id = alpha_idx

            carnivores_alive = 0

            for idx in alive_indices:
                pos = self.sandbox.agent_positions[idx].copy()
                
                if self.sandbox.is_overdriving[idx]:
                    pos += np.random.uniform(-1, 1, 2) # Adrenaline Physical Vibration
                    
                angle = self.sandbox.agent_angles[idx]
                energy = self.sandbox.agent_energy[idx]
                color = self._get_phenotype_color(idx, active_conn_counts, actions, alive_indices)
                
                # Visual Starving Cue
                if self.sandbox.is_carnivore[idx] and energy < 20.0 and np.random.random() > 0.5:
                    color = (20, 0, 0) # Black/Faded Red flicker

                is_camo = self.sandbox.is_camouflaged[idx]
                
                # Dynamic Biological Log-Scaling mapping Energy
                base_radius = max(2, int(np.log(energy + 1.0) * 2.5))

                if is_camo:
                    self.draw_polygon_glow(self.virtual_screen, color, pos, angle, base_radius/2, idx, active_conn_counts)
                else:
                    self.draw_polygon_glow(self.virtual_screen, color, pos, angle, base_radius, idx, active_conn_counts)
    
                    if self.sandbox.is_carnivore[idx]:
                        carnivores_alive += 1
                    
                    if idx == alpha_idx:
                        px, py = int(pos[0]), int(pos[1])
                        pygame.draw.circle(self.virtual_screen, (255, 255, 255), (px, py), base_radius + 4, 1)

            if self.laser_timer > 0:
                self.laser_timer -= 1
                pygame.draw.line(self.virtual_screen, (255, 255, 255), self.laser_coords[0], self.laser_coords[1], max(1, int(self.laser_timer/10)))

        self.update_and_draw_particles()

        if self.oracle_timer > 0:
            self.oracle_timer -= 1
            if self.full_screen_overlay:          
                self.virtual_screen.blit(self.overlay_surf, (0,0))
                
                lines = self.oracle_msg.split('\n')
                for i, ln in enumerate(lines):
                    ren = self.large_font.render(ln, True, (255, 255, 255))
                    self.virtual_screen.blit(ren, (self.base_w//2 - ren.get_width()//2, self.base_h//2 - 40 + (30*i)))

        # Screen Shake application (Damped significantly for viewing clarity)
        shake_x = shake_y = 0
        if self.god_mode.screen_shake > 0.5:
            shake_x = np.random.uniform(-self.god_mode.screen_shake, self.god_mode.screen_shake) * 0.3
            shake_y = np.random.uniform(-self.god_mode.screen_shake, self.god_mode.screen_shake) * 0.3
            self.god_mode.screen_shake *= 0.8 # Faster decay

        # Camera Sub-surfacing (Auto Zooming)
        if self.camera_zoom > 1.01:
            cw = int(self.base_w / self.camera_zoom)
            ch = int(self.base_h / self.camera_zoom)
            cx = int(np.clip(self.camera_target[0] - cw/2, 0, self.base_w - cw))
            cy = int(np.clip(self.camera_target[1] - ch/2, 0, self.base_h - ch))
            sub_rect = pygame.Rect(cx, cy, cw, ch)
            sub_surface = self.virtual_screen.subsurface(sub_rect)
            scaled_virtual = pygame.transform.smoothscale(sub_surface, (scaled_w, scaled_h))
        else:
            scaled_virtual = pygame.transform.smoothscale(self.virtual_screen, (scaled_w, scaled_h))

        # Standard Clean Render (Chromatic Aberration removed for visibility)
        if self.sandbox.legendary_pulse_frames > 0:
            self.sandbox.legendary_pulse_frames -= 1
            
        self.real_screen.blit(scaled_virtual, (offset_x + shake_x, offset_y + shake_y))

        # Exterior HUD Render with Neon Flicker
        if len(alive_indices) > 0:
            alpha_age = self.sandbox.agent_age[alpha_idx]
            prey_count = len(alive_indices) - carnivores_alive
            
            hud_info = [
                f"IPA_VERSE APEX TELEMETRY",
                f"Total Population:  {len(alive_indices)}/50",
                f"Predators Alive:   {carnivores_alive}",
                f"Passive Grazers:   {prey_count}",
                f"Alpha Age (Ticks): {alpha_age}",
                f"Alpha Complexity:  {active_conn_counts[alpha_idx]}",
                f"Zoom Level:        {self.camera_zoom:.2f}x"
            ]
            if self.oracle_timer > 0 and not self.full_screen_overlay:
                hud_info.append(self.oracle_msg)

            a_flicker = int(np.random.uniform(170, 255))
            for i, text in enumerate(hud_info):
                c = (255, 255, 0) if "ORACLE" in text else (200, 200, 200)
                font_to_use = self.large_font if i == 0 else self.font
                ren = font_to_use.render(text, True, c)
                ren.set_alpha(a_flicker)
                self.real_screen.blit(ren, (10, 10 + (25 * i)))

            # Neural Viewer Output Nodes (Alpha)
            nv_start_y = 10 + (25 * len(hud_info)) + 15
            nv_ren = self.font.render("ALPHA NEURAL OUTPUTS:", True, (200, 200, 200))
            self.real_screen.blit(nv_ren, (10, nv_start_y))
            
            out_labels = ["Turn", "Thrust", "Comm", "Bite", "Ghost", "Pulse", "Odrive"]
            for o_idx in range(7):
                val = actions[alpha_idx, o_idx]
                c_node = (0, 255, 255) if val > 0.5 else (50, 20, 20)
                cx = 25 + (o_idx * 43)
                cy = nv_start_y + 30
                pygame.draw.circle(self.real_screen, c_node, (cx, cy), 8)
                lbl = self.font.render(out_labels[o_idx][:3], True, (255, 255, 255))
                self.real_screen.blit(lbl, (cx - 12, cy + 15))

        pygame.display.flip()
        self.clock.tick(self.fps)

    def close(self):
        pygame.quit()
