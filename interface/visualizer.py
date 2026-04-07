import pygame
import numpy as np
import sys
import math
from interface.oracle import Oracle

class Visualizer:
    def __init__(self, sandbox, god_mode, fps=30, world_name="default"):
        pygame.init()
        self.sandbox = sandbox
        self.god_mode = god_mode
        self.fps = fps
        self.world_name = world_name
        self.should_quit = False
        
        # Dual-Layer Renderer for HUD Aspect Ratio scaling (Letterboxing)
        self.base_w = int(sandbox.width)  # 800
        self.base_h = int(sandbox.height) # 600
        self.real_screen = pygame.display.set_mode((1120, 600), pygame.RESIZABLE)
        pygame.display.set_caption(f"IpaVerse: {world_name}")
        self.virtual_screen = pygame.Surface((self.base_w, self.base_h))
        self.clock = pygame.time.Clock()
        
        # Initial black fill so blur doesn't composite over alpha-garbage
        self.virtual_screen.fill((5, 5, 8))
        
        # Load Pixel-Art Assets
        try:
            self.tex_presa = pygame.image.load("assets/textures/presa.png").convert_alpha()
            self.tex_predador = pygame.image.load("assets/textures/depredador.png").convert_alpha()
            self.tex_comida = pygame.image.load("assets/textures/comida.png").convert_alpha()
            self.tex_thicket = pygame.image.load("assets/textures/thicket.png").convert_alpha()
            self.tex_sangre = pygame.image.load("assets/textures/sangre.png").convert_alpha()
        except Exception as e:
            self.tex_presa = pygame.Surface((16,16), pygame.SRCALPHA)
            self.tex_predador = pygame.Surface((24,24), pygame.SRCALPHA)
            self.tex_comida = pygame.Surface((8,8), pygame.SRCALPHA)
            self.tex_thicket = pygame.Surface((32,32), pygame.SRCALPHA)
            self.tex_sangre = pygame.Surface((16,16), pygame.SRCALPHA)

        self.colored_chips = {
            (0, 255, 255): self._tint_surface(self.tex_presa, (0, 255, 255)),
            (50, 255, 100): self._tint_surface(self.tex_presa, (50, 100, 255)),  # Electric Blue Explorador
            (255, 165, 0): self._tint_surface(self.tex_presa, (255, 100, 0)),    # Vibrant Orange Territorial
            (100, 100, 100): self._tint_surface(self.tex_presa, (100, 100, 100)), # Camo
            (255, 255, 255): self._tint_surface(self.tex_presa, (255, 215, 0))   # Gold Sage
        }
            
        # Grid Ambience Texture
        self.grid_surf = pygame.Surface((self.base_w, self.base_h), pygame.SRCALPHA)
        for x in range(0, self.base_w, 40):
            pygame.draw.line(self.grid_surf, (0, 255, 255, 30), (x, 0), (x, self.base_h), 1)
        for y in range(0, self.base_h, 40):
            pygame.draw.line(self.grid_surf, (0, 255, 255, 30), (0, y), (self.base_w, y), 1)
        
        self.previous_positions = np.zeros((50, 2))
        self.ema_velocity = np.zeros(50)
        self.show_codex = False

        
        self.font = pygame.font.SysFont("Consolas", 14)
        self.large_font = pygame.font.SysFont("Consolas", 24, bold=True)
        self.small_font = pygame.font.SysFont("Consolas", 11)
        
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
        
        self.oracle = Oracle(world_name=world_name)
        self.oracle_msg = ""
        self.oracle_timer = 0
        self.full_screen_overlay = False
        
        self.last_alpha_id = -1
        self.laser_timer = 0
        self.laser_coords = ((0,0), (0,0))
        
        self.manual_zoom = 1.0
        self.camera_zoom = 1.0
        self.camera_target = np.array([self.base_w/2, self.base_h/2], dtype=np.float32)

    def _tint_surface(self, surf, color):
        colored = surf.copy()
        colored.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return colored

    def ticks_to_years(self, ticks):
        years = ticks // 1200
        months = (ticks % 1200) // 100
        return years, months

    def get_genome_name(self, idx, is_carnivore):
        syl1 = ["Gar", "Vor", "Som", "Rak", "Khar", "Vel", "Zor", "Bra"]
        syl2 = ["ra", "az", "bra", "rok", "th", "ox", "en", "ka"]
        idx = int(idx)
        name = syl1[idx % len(syl1)] + syl2[(idx * 7) % len(syl2)]
        return name + ("-R" if is_carnivore else "-X")

    def draw_status_bar(self, surface, x, y, width, height, value, max_value, color):
        pygame.draw.rect(surface, (40, 40, 40), (x, y, width, height), border_radius=4)
        if value > 0:
            fill_w = max(4, int((value / max_value) * width))
            pygame.draw.rect(surface, color, (x, y, fill_w, height), border_radius=4)
            pygame.draw.rect(surface, (255, 255, 255), (x, y, fill_w, height//3), border_radius=4)

    def draw_vector_icon(self, surface, icon_type, x, y, color):
        s = 14 # size param
        if icon_type == "heart":
            pts = [(x, y-s//4), (x-s//2, y-s//2), (x-s, y-s//4), (x-s, y+s//4), (x, y+s//1.5), (x+s, y+s//4), (x+s, y-s//4), (x+s//2, y-s//2)]
            pygame.draw.polygon(surface, color, pts)
        elif icon_type == "bolt":
            pts = [(x+s//4, y-s//2), (x-s//3, y+s//6), (x+s//6, y+s//6), (x-s//4, y+s//2), (x+s//3, y-s//6), (x-s//6, y-s//6)]
            pygame.draw.polygon(surface, color, pts)
        elif icon_type == "skull":
            pygame.draw.circle(surface, color, (x, y-s//6), s//2)
            pygame.draw.rect(surface, color, (x-s//3, y, int(s/1.5), s//2))
            pygame.draw.circle(surface, (0, 0, 0), (x-s//4, y-s//6), s//4)
            pygame.draw.circle(surface, (0, 0, 0), (x+s//4, y-s//6), s//4)

    def draw_tracking_cam(self, target_surface, center_x, center_y, agent_idx, scale=1.0):
        pos = self.sandbox.agent_positions[agent_idx]
        px, py = int(pos[0]), int(pos[1])
        sub_w, sub_h = 64, 64 # Widened from 32x32 to provide less zoom and more context
        
        # Clip rect to avoid boundary errors on subsurface
        clip_x = np.clip(px - sub_w//2, 0, self.base_w - sub_w)
        clip_y = np.clip(py - sub_h//2, 0, self.base_h - sub_h)
        
        sub_rect = pygame.Rect(clip_x, clip_y, sub_w, sub_h)
        try:
            sub_surface = self.virtual_screen.subsurface(sub_rect)
            cam_dim = int(128 * scale)
            scaled_cam = pygame.transform.scale(sub_surface, (cam_dim, cam_dim))
            
            t_x, t_y = center_x - cam_dim//2, center_y - cam_dim//2
            target_surface.blit(scaled_cam, (t_x, t_y))
            pygame.draw.rect(target_surface, (200, 200, 200, 150), (t_x, t_y, cam_dim, cam_dim), 1)
        except Exception:
            pass

    def draw_neural_radar(self, target_surface, center_x, center_y, actions, agent_idx, color, scale=1.0):
        out_labels = ["Girar", "Acelerar", "Señal", "Morder", "Camo", "Pulso Q", "Overdrive"]
        num_outputs = len(out_labels)
        max_r = 70 * scale
        
        active_points = []
        bg_points = []
        for i in range(num_outputs):
            ang = i * (2 * np.pi / num_outputs) - np.pi / 2
            bg_px, bg_py = center_x + max_r * np.cos(ang), center_y + max_r * np.sin(ang)
            bg_points.append((bg_px, bg_py))
            pygame.draw.line(target_surface, (50, 50, 50, 150), (center_x, center_y), (bg_px, bg_py), 1)
            
            val = actions[agent_idx, i]
            if np.isnan(val) or np.isinf(val):
                val = 0.0
            r_val = max(0.1, min(val, 1.0))
            active_points.append((center_x + (max_r * r_val) * np.cos(ang), center_y + (max_r * r_val) * np.sin(ang)))
        
        pygame.draw.polygon(target_surface, (50, 50, 50, 150), bg_points, 1)
        
        radar_dim = int(150 * scale)
        radar_surf = pygame.Surface((radar_dim, radar_dim), pygame.SRCALPHA)
        local_active = []
        for p in active_points:
            local_active.append((p[0] - center_x + radar_dim//2, p[1] - center_y + radar_dim//2))
        
        if len(local_active) > 2:
            pygame.draw.polygon(radar_surf, (*color, 100), local_active)
            pygame.draw.polygon(radar_surf, (*color, 255), local_active, 2)
        target_surface.blit(radar_surf, (center_x - radar_dim//2, center_y - radar_dim//2))
        
        for i, (bx, by) in enumerate(bg_points):
            # Push label outwards slightly
            ang = i * (2 * np.pi / num_outputs) - np.pi / 2
            lx, ly = center_x + (max_r + 15) * np.cos(ang), center_y + (max_r + 15) * np.sin(ang)
            l_ren = self.small_font.render(out_labels[i], True, (180, 180, 180, 180))
            target_surface.blit(l_ren, (lx - l_ren.get_width()//2, ly - l_ren.get_height()//2))


    def get_agent_aura(self, idx, actions, active_conn_counts):
        if self.sandbox.is_carnivore[idx]:
            if self.sandbox.kill_count[idx] >= 7:
                return (255, 255, 0), "Titán Alfa" # Yellow Glow
            elif self.sandbox.true_sight[idx]:
                return (180, 0, 180), "Rastreador" # Purple Glow for True Sight
            else:
                return (200, 10, 10), "Depredador"

        # Prey Hierarchy
        if self.sandbox.agent_age[idx] > 13000 or active_conn_counts[idx] >= 7:
            return (255, 255, 255), "Sabio"
        elif self.sandbox.is_camouflaged[idx]:
            return (100, 100, 100), "Oculto"
        elif actions[idx, 5] > 0.7 and self.ema_velocity[idx] < 0.2:
            return (255, 165, 0), "Territorial"
        elif self.ema_velocity[idx] > 0.8:
            return (50, 255, 100), "Explorador"
        else:
            return (0, 255, 255), "Evasivo"

    def trigger_predation_sparks(self, event):
        x, y, victim = event
        for _ in range(25):
            vx, vy = np.random.uniform(-5, 5), np.random.uniform(-5, 5)
            self.particles.append([x, y, vx, vy, (255, 50, 50), 45, 4.0]) # Glowing Blood Sparks
            if len(self.particles) > 500:
                self.particles = self.particles[20:]
            
    def draw_polygon_glow(self, surface, color, pos, angle, radius, idx, active_conn_counts):
        px, py = int(pos[0]), int(pos[1])
        radius = max(2, int(radius))
        is_carnivore = self.sandbox.is_carnivore[idx]
        
        # Area Aura Blur Rings (Preserves the energetic bio-feedback)
        s = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
        dx, dy = radius*2, radius*2
        
        pygame.draw.circle(s, (*color, 60), (dx, dy), radius+4)
        pygame.draw.circle(s, (*color, 20), (dx, dy), radius*2)
        surface.blit(s, (px - dx, py - dy))

        # Rotate Sprite based on calculated angle (Degrees passed natively from our atan2 code)
        if is_carnivore:
            sprite = pygame.transform.rotate(self.tex_predador, angle)
            # Tint overlay if apex
            if self.sandbox.kill_count[idx] >= 7:
                glow_s = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
                glow_s.fill((255, 50, 50, 100))
                sprite.blit(glow_s, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        else:
            if color in self.colored_chips:
                base_tex = self.colored_chips[color]
            else:
                base_tex = self.tex_presa
            sprite = pygame.transform.rotate(base_tex, angle)
            
        rect = sprite.get_rect(center=(px, py))
        surface.blit(sprite, rect.topleft)

    def update_and_draw_particles(self):
        surviving = []
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            p[5] -= 1
            if p[5] > 0:
                # Discern Pulse expansion (Refraction wave) from generic sparks
                if p[4] == (200, 200, 200) and p[6] == 80.0:
                    rad = max(1, int((1.0 - (p[5] / 20.0)) * p[6]))
                    layer_alpha = int(255 * (p[5] / 20.0))
                    surf = pygame.Surface((rad*2, rad*2), pygame.SRCALPHA)
                    pygame.draw.circle(surf, (150, 150, 150, layer_alpha), (rad, rad), rad, 6)
                    self.virtual_screen.blit(surf, (int(p[0]-rad), int(p[1]-rad)))
                # Spawn Ring (Expanding golden light)
                elif p[4] == (255, 220, 100) and p[6] == 40.0:
                    rad = max(1, int((1.0 - (p[5] / 30.0)) * p[6]))
                    layer_alpha = int(200 * (p[5] / 30.0))
                    surf = pygame.Surface((rad*2, rad*2), pygame.SRCALPHA)
                    pygame.draw.circle(surf, (255, 220, 100, layer_alpha), (rad, rad), rad, 3)
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
                is_legendary = self.sandbox.kill_count[aid] >= 7
                c = (20, 5, 20) if is_legendary else (100, 100, 100)
                for i in range(len(pts)-1):
                    alpha = int((i / len(pts)) * 200) if is_legendary else int((i / len(pts)) * 100)
                    thickness = 4 if is_legendary else 1
                    pygame.draw.line(self.virtual_screen, (*c, alpha), pts[i], pts[i+1], thickness)

    def render(self, actions, active_conn_counts, genetic_drift_active=False):
        self.virtual_screen.blit(self.fade_surf, (0,0))
        self.virtual_screen.blit(self.grid_surf, (0,0))
        self.real_screen.fill((5, 5, 5))

        window_w, window_h = self.real_screen.get_size()
        hud_width = 320
        sim_w = window_w
        scale = min(sim_w / self.base_w, window_h / self.base_h)
        scaled_w = int(self.base_w * scale)
        scaled_h = int(self.base_h * scale)
        offset_x = (window_w - scaled_w) // 2
        offset_y = (window_h - scaled_h) // 2

        # Relative Zoom Map Helper
        def get_virtual_mouse(m_pos):
            mx, my = m_pos
            vx_scaled = (mx - offset_x)
            vy_scaled = (my - offset_y)
            if self.camera_zoom > 1.01:
                cw = self.base_w / self.camera_zoom
                ch = self.base_h / self.camera_zoom
                cx = np.clip(self.camera_target[0] - cw/2, 0, self.base_w - cw)
                cy = np.clip(self.camera_target[1] - ch/2, 0, self.base_h - ch)
                return (vx_scaled / scale / self.camera_zoom) + cx, (vy_scaled / scale / self.camera_zoom) + cy
            return (vx_scaled / scale), (vy_scaled / scale)

        m_pos = pygame.mouse.get_pos()
        old_vx, old_vy = get_virtual_mouse(m_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.should_quit = True
                return
            if event.type == pygame.VIDEORESIZE:
                self.real_screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_h:
                    self.show_codex_loop()
            if event.type == pygame.MOUSEWHEEL:
                if m_pos[0] < hud_width or m_pos[0] > window_w - hud_width:
                    continue
                self.manual_zoom = max(1.0, self.manual_zoom + event.y * 0.1)
                self.camera_zoom = self.manual_zoom
                
                # Compensar camera_target hacia el mouse actual (Relative Panning)
                if self.manual_zoom > 1.01:
                    vx_s = (m_pos[0] - offset_x)
                    vy_s = (m_pos[1] - offset_y)
                    
                    new_tx = old_vx - (vx_s / scale / self.manual_zoom) + (self.base_w / (2 * self.manual_zoom))
                    new_ty = old_vy - (vy_s / scale / self.manual_zoom) + (self.base_h / (2 * self.manual_zoom))
                    
                    cw = self.base_w / self.manual_zoom
                    ch = self.base_h / self.manual_zoom
                    self.camera_target[0] = np.clip(new_tx, cw/2, self.base_w - cw/2)
                    self.camera_target[1] = np.clip(new_ty, ch/2, self.base_h - ch/2)
                else:
                    self.camera_target = np.array([self.base_w/2, self.base_h/2], dtype=np.float32)

            if event.type == pygame.KEYDOWN:
                vx, vy = get_virtual_mouse(m_pos)
                if event.key == pygame.K_m: 
                    self.god_mode.trigger_meteor(vx, vy, radius=150.0)
                elif event.key == pygame.K_f: 
                    self.god_mode.trigger_flood()
                elif event.key == pygame.K_r: 
                    self.god_mode.trigger_radiation()
                elif event.key == pygame.K_ESCAPE:
                    self.should_quit = True
                    return
                elif event.key == pygame.K_SPACE:
                    self.god_mode.trigger_big_crunch()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Codex Button Click Check
                if m_pos[0] >= window_w - 50 and m_pos[0] <= window_w - 20 and m_pos[1] >= 20 and m_pos[1] <= 50:
                    self.show_codex_loop()
                    continue
                if m_pos[0] < hud_width or m_pos[0] > window_w - hud_width:
                    continue
                vx, vy = get_virtual_mouse(event.pos)
                self.god_mode.trigger_meteor(vx, vy, radius=70.0)

        alive_mask = self.sandbox.agent_alive
        alive_indices = np.where(alive_mask)[0]

        # Calculate Vectorized EMA Velocity
        speeds = np.linalg.norm(self.sandbox.agent_positions - self.previous_positions, axis=1)
        self.ema_velocity = self.ema_velocity * 0.98 + speeds * 0.02

        if self.sandbox.oracle_deaths >= 100:
            self.sandbox.oracle_deaths = 0
            if len(alive_indices) > 0:
                dom, col, stats = self.oracle.compute_archetype(active_conn_counts, actions, self.sandbox)
                self.oracle_msg = f"ORÁCULO POST-MORTEM: La Era está dominada por {dom}.\n>>> {stats}"
                self.oracle_timer = 240 
                self.full_screen_overlay = False

        if self.sandbox.big_crunch and self.sandbox.big_crunch_progress > 1.95 and not self.full_screen_overlay:
            if len(alive_indices) > 0:
                dom, col, stats = self.oracle.compute_archetype(active_conn_counts, actions, self.sandbox)
                alpha = alive_indices[np.argmax(self.sandbox.agent_age[alive_indices])]
                self.oracle.save_epoch(dom, self.sandbox.agent_age[alpha], alpha, active_conn_counts[alpha], np.max(self.sandbox.kill_count))
                self.oracle_msg = f"GRAN COLAPSO\nEra de {dom}\nComplejidad del Alfa: {active_conn_counts[alpha]}\n>>> {stats}\nReiniciando Entorno..."
            else:
                self.oracle_msg = "GRAN COLAPSO\nExtinción Alcanzada.\nReiniciando Entorno..."
            self.oracle_timer = 240 
            self.full_screen_overlay = True

        # Draw Geographies
        frame_time = pygame.time.get_ticks() / 1000.0
        
        # Thickets
        for tx, ty, tr in self.sandbox.thickets:
            jitter = np.sin(frame_time * 10.0 + tx) * 2.0
            r_jit = tr + jitter
            scaled_thick = pygame.transform.scale(self.tex_thicket, (int(r_jit*2), int(r_jit*2)))
            self.virtual_screen.blit(scaled_thick, (int(tx - r_jit), int(ty - r_jit)))
            
        # Burrows
        for bx, by, br in self.sandbox.burrows:
            pygame.draw.circle(self.virtual_screen, (5, 5, 5), (int(bx), int(by)), int(br))
            pygame.draw.circle(self.virtual_screen, (80, 20, 80), (int(bx), int(by)), int(br), 2)
        
        # Draw Food
        for fx, fy in self.sandbox.food_positions[self.sandbox.food_active]:
            pygame.draw.circle(self.virtual_screen, (40, 150, 40), (int(fx), int(fy)), 6)
            self.virtual_screen.blit(self.tex_comida, (int(fx)-4, int(fy)-4))

        if len(alive_indices) > 0:
            for px, py in self.sandbox.pulse_events:
                self.particles.append([px, py, 0, 0, (200, 200, 200), 20, 80.0]) # Pulse Refraction Ring (reduced)
            
            # Spawn Animations (Expanding golden rings)
            for sx, sy in self.sandbox.spawn_events:
                self.particles.append([sx, sy, 0, 0, (255, 220, 100), 30, 40.0]) # Spawn Ring
                
            for p_event in self.sandbox.predation_events:
                self.trigger_predation_sparks(p_event)
                
            for parent, child in self.sandbox.clones_produced_this_tick:
                p_pos = self.sandbox.agent_positions[parent]
                c_pos = self.sandbox.agent_positions[child]
                p_col, _ = self.get_agent_aura(parent, actions, active_conn_counts)
                c_col, _ = self.get_agent_aura(child, actions, active_conn_counts)
                
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
            
            # Identify Legendary
            carnivore_idx = np.where(self.sandbox.is_carnivore & self.sandbox.agent_alive)[0]
            if len(carnivore_idx) > 0:
                legendary_idx = carnivore_idx[np.argmax(self.sandbox.kill_count[carnivore_idx])]
            else:
                legendary_idx = None
            
            # The auto-camera target shift code has been replaced by mouse-relative zoom.
            
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
                    
                # Delta Velocity Angle Calculation
                prev_pos = self.previous_positions[idx]
                dx, dy = pos[0] - prev_pos[0], pos[1] - prev_pos[1]
                if abs(dx) > 0.01 or abs(dy) > 0.01:
                    self.sandbox.agent_angles[idx] = math.degrees(math.atan2(-dy, dx))
                angle = self.sandbox.agent_angles[idx]
                
                energy = self.sandbox.agent_energy[idx]
                color, _ = self.get_agent_aura(idx, actions, active_conn_counts)
                
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
                
                px, py = int(pos[0]), int(pos[1])
                
                # Flecha indicadora del Alfa (blanca, pulsante)
                if idx == alpha_idx:
                    pygame.draw.circle(self.virtual_screen, (255, 255, 255), (px, py), base_radius + 4, 1)
                    arrow_y = py - base_radius - 14
                    arrow_pts = [(px, arrow_y + 8), (px - 5, arrow_y), (px + 5, arrow_y)]
                    pygame.draw.polygon(self.virtual_screen, (255, 255, 255), arrow_pts, 0)
                    lbl = self.font.render("A", True, (255, 255, 255))
                    self.virtual_screen.blit(lbl, (px - lbl.get_width()//2, arrow_y - 14))
                
                # Flecha indicadora del Legendario (púrpura)
                if self.sandbox.is_carnivore[idx] and self.sandbox.kill_count[idx] >= 7:
                    arrow_y = py - base_radius - 14
                    arrow_pts = [(px, arrow_y + 8), (px - 5, arrow_y), (px + 5, arrow_y)]
                    pygame.draw.polygon(self.virtual_screen, (180, 0, 255), arrow_pts, 0)
                    kills = self.sandbox.kill_count[idx]
                    lbl = self.font.render(f"★{kills}", True, (180, 0, 255))
                    self.virtual_screen.blit(lbl, (px - lbl.get_width()//2, arrow_y - 14))

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

        # ----------------------------------------------------
        # STEP A: Draw the Actual Sandbox Backend FIRST
        # ----------------------------------------------------
        if self.sandbox.legendary_pulse_frames > 0:
            self.sandbox.legendary_pulse_frames -= 1
            
        self.real_screen.blit(scaled_virtual, (offset_x + shake_x, offset_y + shake_y))

        # ----------------------------------------------------
        # STEP B: Draw The Full Screen HUD Overlay ON TOP
        # ----------------------------------------------------
        self.hud_surface = pygame.Surface((window_w, window_h), pygame.SRCALPHA)
        scale_y = max(0.6, min(1.0, window_h / 700.0))
        
        if len(alive_indices) > 0:
            alpha_age_ticks = self.sandbox.agent_age[alpha_idx]
            y_yr, m_mo = self.ticks_to_years(alpha_age_ticks)
            prey_count = len(alive_indices) - carnivores_alive
            alpha_energy = self.sandbox.agent_energy[alpha_idx]
            alpha_kills = self.sandbox.kill_count[alpha_idx]
            
            camo = actions[alpha_idx, 4]
            dash = actions[alpha_idx, 6]
            thr = actions[alpha_idx, 1]
            turn = actions[alpha_idx, 0]
            sig = actions[alpha_idx, 2]
            
            alpha_col, b_status = self.get_agent_aura(alpha_idx, actions, active_conn_counts)
            
            # --- LEFT COLUMN (ALPHA / PREY FOCUS) ---
            alpha_is_carn = self.sandbox.is_carnivore[alpha_idx]
            alpha_name = self.get_genome_name(alpha_idx, alpha_is_carn)
            
            left_info = [
                f"MUNDO: {self.world_name.upper()}",
                f"Deriva Genética: {'ACTIVA' if genetic_drift_active else 'EN ESPERA'}",
                f"Edad Promedio: {y_yr} Años"
            ]
            
            if self.oracle_timer > 0 and not self.full_screen_overlay:
                for line in self.oracle_msg.split('\n'):
                    left_info.append(line)
            
            a_flicker = int(np.random.uniform(180, 255))
            for i, text in enumerate(left_info):
                c = (255, 255, 0) if "ORÁCULO" in text or ">>>" in text else (200, 200, 200)
                font_to_use = self.large_font if i == 0 else self.font
                ren = font_to_use.render(text, True, (*c, a_flicker))
                self.hud_surface.blit(ren, (20, 20 + int(30 * scale_y * i)))
            
            hud_y = 20 + int(30 * scale_y * len(left_info)) + int(30 * scale_y)
            
            pygame.draw.rect(self.hud_surface, (20, 25, 30, 160), (20, hud_y, 300, 110), border_radius=8)
            pygame.draw.rect(self.hud_surface, (50, 100, 150, 200), (20, hud_y, 300, 110), 2, border_radius=8)
            
            self.draw_vector_icon(self.hud_surface, "heart", 45, hud_y + 25, (255, 50, 50))
            age_txt = self.font.render(f"Supervivencia: {y_yr} A, {m_mo} M", True, (200, 200, 200))
            self.hud_surface.blit(age_txt, (65, hud_y + 15))
            
            self.draw_vector_icon(self.hud_surface, "bolt", 45, hud_y + 55, (255, 255, 0))
            self.draw_status_bar(self.hud_surface, 65, hud_y + 45, 240, 20, alpha_energy, 100.0, (255, 200, 0))
            
            self.draw_vector_icon(self.hud_surface, "skull", 45, hud_y + 85, (150, 0, 200))
            k_txt = self.font.render(f"Kills Registrados: {alpha_kills}", True, (200, 200, 200))
            self.hud_surface.blit(k_txt, (65, hud_y + 75))
            
            hud_y += int(120 * scale_y)
            # biological status & name floating
            st_ren = self.font.render(f"Estado: {b_status}", True, alpha_col)
            self.hud_surface.blit(st_ren, (170 - st_ren.get_width()//2, hud_y))
            n_ren = self.large_font.render(alpha_name, True, alpha_col)
            self.hud_surface.blit(n_ren, (170 - n_ren.get_width()//2, hud_y + int(25 * scale_y)))
            
            # PiP Cam
            hud_y += int(65 * scale_y)
            self.draw_tracking_cam(self.hud_surface, 170, hud_y + int(64 * scale_y), alpha_idx, scale=scale_y)
            
            # Radar
            hud_y += int(140 * scale_y)
            nv_ren = self.font.render("CÓRTEX (ALFA):", True, (200, 200, 200))
            self.hud_surface.blit(nv_ren, (20, hud_y))
            self.draw_neural_radar(self.hud_surface, 170, hud_y + int(100 * scale_y), actions, alpha_idx, (0, 255, 255), scale=scale_y)

            # --- RIGHT COLUMN (TITAN / PREDATOR FOCUS) ---
            right_x = window_w - 320
            
            right_info = [
                f"Población Total: {len(alive_indices)}/50",
                f"Herbívoros (Presas): {prey_count}",
                f"Carnívoros (Cazadores): {carnivores_alive}",
                f"Densidad Biológica: {int((len(alive_indices)/50)*100)}%"
            ]
            for i, text in enumerate(right_info):
                ren = self.font.render(text, True, (200, 200, 200, a_flicker))
                self.hud_surface.blit(ren, (right_x, 20 + int(30 * scale_y * i)))
                
            if legendary_idx is not None:
                leg_name = self.get_genome_name(legendary_idx, True)
                leg_age_ticks = self.sandbox.agent_age[legendary_idx]
                leg_y, leg_m = self.ticks_to_years(leg_age_ticks)
                leg_energy = self.sandbox.agent_energy[legendary_idx]
                leg_scale = self.sandbox.kill_count[legendary_idx]
                
                # Biostatus Titan
                leg_col, t_status = self.get_agent_aura(legendary_idx, actions, active_conn_counts)

                l_hud_y = 20 + int(30 * scale_y * len(right_info)) + int(30 * scale_y)
                pygame.draw.rect(self.hud_surface, (30, 20, 20, 160), (right_x, l_hud_y, 300, 110), border_radius=8)
                pygame.draw.rect(self.hud_surface, (255, 50, 50, 200), (right_x, l_hud_y, 300, 110), 2, border_radius=8)

                self.draw_vector_icon(self.hud_surface, "heart", right_x + 25, l_hud_y + 25, (255, 50, 50))
                leg_age_tc = self.font.render(f"Supervivencia: {leg_y} A, {leg_m} M", True, (200, 200, 200))
                self.hud_surface.blit(leg_age_tc, (right_x + 45, l_hud_y + 15))
                
                self.draw_vector_icon(self.hud_surface, "bolt", right_x + 25, l_hud_y + 55, (255, 255, 0))
                self.draw_status_bar(self.hud_surface, right_x + 45, l_hud_y + 45, 240, 20, leg_energy, 100.0, (255, 50, 0))
                
                self.draw_vector_icon(self.hud_surface, "skull", right_x + 25, l_hud_y + 85, (150, 0, 200))
                leg_k_tc = self.font.render(f"Víctimas Titánicas: {leg_scale}", True, (255, 100, 100))
                self.hud_surface.blit(leg_k_tc, (right_x + 45, l_hud_y + 75))
                
                l_hud_y += int(120 * scale_y)
                tst_ren = self.font.render(f"Estado: {t_status}", True, leg_col)
                self.hud_surface.blit(tst_ren, (right_x + 150 - tst_ren.get_width()//2, l_hud_y))
                l_ren = self.large_font.render(leg_name, True, leg_col)
                self.hud_surface.blit(l_ren, (right_x + 150 - l_ren.get_width()//2, l_hud_y + int(25 * scale_y)))
                
                l_hud_y += int(65 * scale_y)
                self.draw_tracking_cam(self.hud_surface, right_x + 150, l_hud_y + int(64 * scale_y), legendary_idx, scale=scale_y)

                l_hud_y += int(140 * scale_y)
                nv_ren2 = self.font.render("CÓRTEX (TITAN):", True, (255, 100, 100))
                self.hud_surface.blit(nv_ren2, (right_x, l_hud_y))
                self.draw_neural_radar(self.hud_surface, right_x + 150, l_hud_y + int(100 * scale_y), actions, legendary_idx, (255, 0, 0), scale=scale_y)

        # Draw [?] Codex Button
        codex_rect = pygame.Rect(window_w - 50, 20, 30, 30)
        pygame.draw.rect(self.hud_surface, (50, 100, 150, 160), codex_rect, border_radius=5)
        pygame.draw.rect(self.hud_surface, (100, 200, 255), codex_rect, 1, border_radius=5)
        btn_ren = self.large_font.render("?", True, (255, 255, 255))
        self.hud_surface.blit(btn_ren, (codex_rect.centerx - btn_ren.get_width()//2, codex_rect.centery - btn_ren.get_height()//2))

        # Compose final screen
        self.real_screen.blit(self.hud_surface, (0, 0))

        self.previous_positions = np.copy(self.sandbox.agent_positions)

        pygame.display.flip()
        self.clock.tick(self.fps)

    def show_extinction_screen(self):
        """Pantalla de extinción con opciones de reiniciar o salir."""
        btn_restart = pygame.Rect(self.real_screen.get_width()//2 - 160, self.real_screen.get_height()//2 + 20, 320, 60)
        btn_exit = pygame.Rect(self.real_screen.get_width()//2 - 160, self.real_screen.get_height()//2 + 100, 320, 60)
        
        while True:
            self.real_screen.fill((5, 5, 8))
            mx, my = pygame.mouse.get_pos()
            click = False
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "EXIT"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    click = True
            
            # Title
            title = self.large_font.render("EXTINCIÓN TOTAL", True, (255, 50, 50))
            self.real_screen.blit(title, (self.real_screen.get_width()//2 - title.get_width()//2, self.real_screen.get_height()//3 - 30))
            
            sub = self.font.render("Todas las formas de vida han perecido.", True, (200, 200, 200))
            self.real_screen.blit(sub, (self.real_screen.get_width()//2 - sub.get_width()//2, self.real_screen.get_height()//3 + 20))
            
            # Restart button
            r_hover = btn_restart.collidepoint((mx, my))
            col_r = (30, 100, 30) if r_hover else (20, 60, 20)
            pygame.draw.rect(self.real_screen, col_r, btn_restart, border_radius=10)
            pygame.draw.rect(self.real_screen, (0, 255, 0) if r_hover else (50, 120, 50), btn_restart, 2, border_radius=10)
            txt_r = self.font.render("REINICIAR MUNDO", True, (255, 255, 255))
            self.real_screen.blit(txt_r, (btn_restart.centerx - txt_r.get_width()//2, btn_restart.centery - txt_r.get_height()//2))
            
            # Exit button
            e_hover = btn_exit.collidepoint((mx, my))
            col_e = (100, 30, 30) if e_hover else (60, 20, 20)
            pygame.draw.rect(self.real_screen, col_e, btn_exit, border_radius=10)
            pygame.draw.rect(self.real_screen, (255, 0, 0) if e_hover else (120, 50, 50), btn_exit, 2, border_radius=10)
            txt_e = self.font.render("VOLVER AL MENÚ", True, (255, 255, 255))
            self.real_screen.blit(txt_e, (btn_exit.centerx - txt_e.get_width()//2, btn_exit.centery - txt_e.get_height()//2))
            
            if click:
                if r_hover:
                    return "RESTART"
                if e_hover:
                    return "EXIT"
            
            pygame.display.flip()
            self.clock.tick(30)

    def close(self):
        # Don't pygame.quit() — menu needs pygame alive
        pass

    def show_codex_loop(self):
        self.show_codex = True
        overlay = pygame.Surface(self.real_screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 220))
        
        while self.show_codex:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.should_quit = True
                    self.show_codex = False
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_h or event.key == pygame.K_ESCAPE:
                        self.show_codex = False
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # Generic click anywhere to close
                    self.show_codex = False

            # Draw Base Game frozen
            self.real_screen.blit(self.hud_surface, (0, 0))
            self.real_screen.blit(overlay, (0, 0))
            
            # Codex Content
            cx, cy = self.real_screen.get_width() // 2, self.real_screen.get_height() // 2
            pygame.draw.rect(self.real_screen, (20, 25, 30), (cx - 250, cy - 250, 500, 500), border_radius=15)
            pygame.draw.rect(self.real_screen, (100, 200, 255), (cx - 250, cy - 250, 500, 500), 2, border_radius=15)
            
            title = self.large_font.render("CÓDICE DE COMPORTAMIENTO", True, (255, 255, 255))
            self.real_screen.blit(title, (cx - title.get_width()//2, cy - 230))
            
            entries = [
                ((0, 255, 255), "Evasivo (Cian)", "Comportamiento estándar de supervivencia."),
                ((50, 100, 255), "Explorador (Azul)", "Agentes con alta inercia que patrullan el mapa."),
                ((255, 100, 0), "Territorial (Naranja)", "Agentes estacionarios reclamando zonas de comida."),
                ((100, 100, 100), "Oculto (Gris)", "Agentes usando neuronas de camuflaje biológico."),
                ((255, 215, 0), "Sabio (Dorado)", "Veteranos (Edad > 13000) o de alta complejidad."),
                ((200, 10, 10), "Depredador (Rojo)", "Carnívoros de primer nivel."),
                ((180, 0, 180), "Rastreador (Magenta)", "Cazadores mutantes con Olfato (inmunes al Camuflaje)."),
                ((255, 255, 0), "Titán Alfa (Amarillo)", "Cazadores Leyenda con más de 7 víctimas directas.")
            ]
            
            iy = cy - 160
            for color, name, desc in entries:
                pygame.draw.circle(self.real_screen, color, (cx - 210, iy + 6), 8)
                n_ren = self.large_font.render(name, True, color)
                self.real_screen.blit(n_ren, (cx - 180, iy - 6))
                d_ren = self.font.render(desc, True, (200, 200, 200))
                self.real_screen.blit(d_ren, (cx - 180, iy + 20))
                iy += 55
                
            close_lbl = self.font.render("Haz clic o presiona [H] para reanudar", True, (150, 150, 150))
            self.real_screen.blit(close_lbl, (cx - close_lbl.get_width()//2, cy + 260))

            pygame.display.flip()
            self.clock.tick(30)

