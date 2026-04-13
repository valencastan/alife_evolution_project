import pygame
import numpy as np
import sys
import math
from interface.oracle import Oracle

# ---------------------------------------------------------------------------
# Module-level age formatter
# ---------------------------------------------------------------------------
def format_age(ticks, fps=30):
    """Convert simulation ticks to 'Xa Ym' or 'Xm' or 'Xs' depending on age."""
    seconds = int(ticks / fps)
    months  = seconds // 60
    years   = months // 12
    m       = months % 12
    if years > 0:
        return f"{years}a {m}m"
    if months > 0:
        return f"{m}m"
    return f"{seconds}s"


class Visualizer:
    def __init__(self, sandbox, god_mode, fps=30, world_name="default"):
        pygame.init()
        self.sandbox    = sandbox
        self.god_mode   = god_mode
        self.fps        = fps
        self.world_name = world_name
        self.should_quit = False

        # Dual-Layer Renderer for HUD Aspect Ratio scaling (Letterboxing)
        self.base_w = int(sandbox.width)   # 800
        self.base_h = int(sandbox.height)  # 600
        self.real_screen   = pygame.display.set_mode((1120, 600), pygame.RESIZABLE)
        pygame.display.set_caption(f"IpaVerse: {world_name}")
        self.virtual_screen = pygame.Surface((self.base_w, self.base_h))
        self.clock = pygame.time.Clock()

        # Initial black fill so blur doesn't composite over alpha-garbage
        self.virtual_screen.fill((5, 5, 8))

        # Load Pixel-Art Assets
        try:
            def resource_path(relative_path):
                import sys, os
                if hasattr(sys, '_MEIPASS'):
                    return os.path.join(sys._MEIPASS, relative_path)
                return os.path.join(os.path.abspath("."), relative_path)

            self.tex_presa    = pygame.image.load(resource_path("assets/textures/presa.png")).convert_alpha()
            self.tex_predador = pygame.image.load(resource_path("assets/textures/depredador.png")).convert_alpha()
            self.tex_comida   = pygame.image.load(resource_path("assets/textures/comida.png")).convert_alpha()
            self.tex_thicket  = pygame.image.load(resource_path("assets/textures/thicket.png")).convert_alpha()
            self.tex_sangre   = pygame.image.load(resource_path("assets/textures/sangre.png")).convert_alpha()
        except Exception as e:
            print(f"Failed to load textures: {e}")
            self.tex_presa    = pygame.Surface((16, 16), pygame.SRCALPHA)
            self.tex_predador = pygame.Surface((24, 24), pygame.SRCALPHA)
            self.tex_comida   = pygame.Surface((8,  8),  pygame.SRCALPHA)
            self.tex_thicket  = pygame.Surface((32, 32), pygame.SRCALPHA)
            self.tex_sangre   = pygame.Surface((16, 16), pygame.SRCALPHA)

        self.colored_chips = {
            (0, 255, 255):   self._tint_surface(self.tex_presa, (0, 255, 255)),
            (50, 255, 100):  self._tint_surface(self.tex_presa, (50, 100, 255)),
            (255, 165, 0):   self._tint_surface(self.tex_presa, (255, 100, 0)),
            (100, 100, 100): self._tint_surface(self.tex_presa, (100, 100, 100)),
            (255, 255, 255): self._tint_surface(self.tex_presa, (255, 215, 0)),
        }

        # Grid Ambience Texture
        self.grid_surf = pygame.Surface((self.base_w, self.base_h), pygame.SRCALPHA)
        for x in range(0, self.base_w, 40):
            pygame.draw.line(self.grid_surf, (0, 255, 255, 30), (x, 0), (x, self.base_h), 1)
        for y in range(0, self.base_h, 40):
            pygame.draw.line(self.grid_surf, (0, 255, 255, 30), (0, y), (self.base_w, y), 1)

        self.previous_positions = np.zeros((50, 2))
        self.ema_velocity       = np.zeros(50)
        self.show_codex         = False

        self.font       = pygame.font.SysFont("Consolas", 14)
        self.large_font = pygame.font.SysFont("Consolas", 24, bold=True)
        self.small_font = pygame.font.SysFont("Consolas", 11)

        # Pre-cache Bloom Core Gradient High Res
        self.bloom_radius  = 200
        self.bloom_surface = pygame.Surface((self.bloom_radius * 2, self.bloom_radius * 2), pygame.SRCALPHA)
        for i in range(self.bloom_radius, 0, -2):
            alpha = int(100 * (1.0 - (i / self.bloom_radius)) ** 2)
            pygame.draw.circle(self.bloom_surface, (255, 255, 255, alpha),
                               (self.bloom_radius, self.bloom_radius), i)

        self.cached_blooms = {}

        self.fade_surf = pygame.Surface((self.base_w, self.base_h), pygame.SRCALPHA)
        self.fade_surf.fill((5, 5, 8, 45))

        self.overlay_surf = pygame.Surface((self.base_w, self.base_h), pygame.SRCALPHA)
        self.overlay_surf.fill((0, 0, 0, 200))

        self.particles = []
        self.trails    = {}

        self.oracle       = Oracle(world_name=world_name)
        self.oracle_msg   = ""
        self.oracle_timer = 0
        self.full_screen_overlay = False

        self.last_alpha_id  = -1
        self.laser_timer    = 0
        self.laser_coords   = ((0, 0), (0, 0))

        self.manual_zoom   = 1.0
        self.camera_zoom   = 1.0
        self.camera_target = np.array([self.base_w / 2, self.base_h / 2], dtype=np.float32)

        # Help overlay state
        self._help_open    = False
        self._help_section = 0   # 0 = Controls, 1 = Classes/Colors

    # -----------------------------------------------------------------------
    # Utility helpers
    # -----------------------------------------------------------------------
    def _tint_surface(self, surf, color):
        colored = surf.copy()
        colored.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return colored

    def ticks_to_years(self, ticks):
        years  = ticks // 1200
        months = (ticks % 1200) // 100
        return years, months

    def get_genome_name(self, idx, is_carnivore):
        syl1 = ["Gar", "Vor", "Som", "Rak", "Khar", "Vel", "Zor", "Bra"]
        syl2 = ["ra",  "az",  "bra", "rok", "th",   "ox",  "en",  "ka"]
        idx  = int(idx)
        name = syl1[idx % len(syl1)] + syl2[(idx * 7) % len(syl2)]
        return name + ("-R" if is_carnivore else "-X")

    def draw_status_bar(self, surface, x, y, width, height, value, max_value, color):
        pygame.draw.rect(surface, (40, 40, 40), (x, y, width, height), border_radius=4)
        if value > 0:
            fill_w = max(4, int((value / max_value) * width))
            pygame.draw.rect(surface, color, (x, y, fill_w, height), border_radius=4)
            pygame.draw.rect(surface, (255, 255, 255), (x, y, fill_w, height // 3), border_radius=4)

    def draw_vector_icon(self, surface, icon_type, x, y, color):
        s = 14
        if icon_type == "heart":
            pts = [(x, y-s//4), (x-s//2, y-s//2), (x-s, y-s//4),
                   (x-s, y+s//4), (x, y+s//1.5), (x+s, y+s//4), (x+s, y-s//4), (x+s//2, y-s//2)]
            pygame.draw.polygon(surface, color, pts)
        elif icon_type == "bolt":
            pts = [(x+s//4, y-s//2), (x-s//3, y+s//6), (x+s//6, y+s//6),
                   (x-s//4, y+s//2), (x+s//3, y-s//6), (x-s//6, y-s//6)]
            pygame.draw.polygon(surface, color, pts)
        elif icon_type == "skull":
            pygame.draw.circle(surface, color, (x, y-s//6), s//2)
            pygame.draw.rect(surface, color, (x-s//3, y, int(s/1.5), s//2))
            pygame.draw.circle(surface, (0, 0, 0), (x-s//4, y-s//6), s//4)
            pygame.draw.circle(surface, (0, 0, 0), (x+s//4, y-s//6), s//4)

    def draw_tracking_cam(self, target_surface, center_x, center_y, agent_idx, scale=1.0):
        pos  = self.sandbox.agent_positions[agent_idx]
        px, py = int(pos[0]), int(pos[1])
        sub_w, sub_h = 64, 64

        clip_x = np.clip(px - sub_w // 2, 0, self.base_w - sub_w)
        clip_y = np.clip(py - sub_h // 2, 0, self.base_h - sub_h)
        sub_rect = pygame.Rect(clip_x, clip_y, sub_w, sub_h)
        try:
            sub_surface = self.virtual_screen.subsurface(sub_rect)
            cam_dim     = int(128 * scale)
            scaled_cam  = pygame.transform.scale(sub_surface, (cam_dim, cam_dim))
            t_x, t_y    = center_x - cam_dim // 2, center_y - cam_dim // 2
            target_surface.blit(scaled_cam, (t_x, t_y))
            pygame.draw.rect(target_surface, (200, 200, 200, 150), (t_x, t_y, cam_dim, cam_dim), 1)
        except Exception:
            pass

    def draw_neural_radar(self, target_surface, center_x, center_y, actions, agent_idx, color, scale=1.0):
        out_labels  = ["Girar", "Acelerar", "Señal", "Morder", "Camo", "Pulso Q", "Overdrive"]
        num_outputs = len(out_labels)
        max_r       = 70 * scale

        active_points = []
        bg_points     = []
        for i in range(num_outputs):
            ang    = i * (2 * np.pi / num_outputs) - np.pi / 2
            bg_px  = center_x + max_r * np.cos(ang)
            bg_py  = center_y + max_r * np.sin(ang)
            bg_points.append((bg_px, bg_py))
            pygame.draw.line(target_surface, (50, 50, 50, 150),
                             (center_x, center_y), (bg_px, bg_py), 1)
            val   = actions[agent_idx, i]
            if np.isnan(val) or np.isinf(val):
                val = 0.0
            r_val = max(0.1, min(val, 1.0))
            active_points.append((center_x + (max_r * r_val) * np.cos(ang),
                                  center_y + (max_r * r_val) * np.sin(ang)))

        pygame.draw.polygon(target_surface, (50, 50, 50, 150), bg_points, 1)

        radar_dim  = int(150 * scale)
        radar_surf = pygame.Surface((radar_dim, radar_dim), pygame.SRCALPHA)
        local_active = [(p[0] - center_x + radar_dim // 2,
                         p[1] - center_y + radar_dim // 2) for p in active_points]

        if len(local_active) > 2:
            pygame.draw.polygon(radar_surf, (*color, 100), local_active)
            pygame.draw.polygon(radar_surf, (*color, 255), local_active, 2)
        target_surface.blit(radar_surf, (center_x - radar_dim // 2, center_y - radar_dim // 2))

        for i, (bx, by) in enumerate(bg_points):
            ang    = i * (2 * np.pi / num_outputs) - np.pi / 2
            lx     = center_x + (max_r + 15) * np.cos(ang)
            ly     = center_y + (max_r + 15) * np.sin(ang)
            l_ren  = self.small_font.render(out_labels[i], True, (180, 180, 180, 180))
            target_surface.blit(l_ren, (lx - l_ren.get_width() // 2, ly - l_ren.get_height() // 2))

    def get_agent_aura(self, idx, actions, active_conn_counts):
        if self.sandbox.is_carnivore[idx]:
            if self.sandbox.kill_count[idx] >= 7:
                return (255, 255, 0),  "Titán Alfa"
            elif self.sandbox.true_sight[idx]:
                return (180, 0, 180),  "Rastreador"
            else:
                return (200, 10, 10),  "Depredador"
        if self.sandbox.agent_age[idx] > 10000:
            return (255, 255, 255), "Sabio"
        elif self.sandbox.is_camouflaged[idx]:
            return (100, 100, 100), "Oculto"
        elif actions[idx, 5] > 0.7 and self.ema_velocity[idx] < 0.2:
            return (255, 165, 0),  "Territorial"
        elif self.ema_velocity[idx] > 0.8:
            return (50, 255, 100), "Explorador"
        else:
            return (0, 255, 255),  "Evasivo"

    def trigger_predation_sparks(self, event):
        x, y, victim = event
        for _ in range(25):
            vx, vy = np.random.uniform(-5, 5), np.random.uniform(-5, 5)
            self.particles.append([x, y, vx, vy, (255, 50, 50), 45, 4.0])
            if len(self.particles) > 500:
                self.particles = self.particles[20:]

    def draw_polygon_glow(self, surface, color, pos, angle, radius, idx, active_conn_counts):
        px, py = int(pos[0]), int(pos[1])
        radius = max(2, int(radius))
        is_carnivore = self.sandbox.is_carnivore[idx]

        s  = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
        dx, dy = radius * 2, radius * 2
        pygame.draw.circle(s, (*color, 60),  (dx, dy), radius + 4)
        pygame.draw.circle(s, (*color, 20),  (dx, dy), radius * 2)
        surface.blit(s, (px - dx, py - dy))

        if is_carnivore:
            sprite = pygame.transform.rotate(self.tex_predador, angle)
            if self.sandbox.kill_count[idx] >= 7:
                glow_s = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
                glow_s.fill((255, 50, 50, 100))
                sprite.blit(glow_s, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        else:
            base_tex = self.colored_chips.get(color, self.tex_presa)
            sprite   = pygame.transform.rotate(base_tex, angle)

        rect = sprite.get_rect(center=(px, py))
        surface.blit(sprite, rect.topleft)

    def update_and_draw_particles(self):
        surviving = []
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            p[5] -= 1
            if p[5] > 0:
                if p[4] == (200, 200, 200) and p[6] == 80.0:
                    rad         = max(1, int((1.0 - (p[5] / 20.0)) * p[6]))
                    layer_alpha = int(255 * (p[5] / 20.0))
                    surf        = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
                    pygame.draw.circle(surf, (150, 150, 150, layer_alpha), (rad, rad), rad, 6)
                    self.virtual_screen.blit(surf, (int(p[0] - rad), int(p[1] - rad)))
                elif p[4] == (255, 220, 100) and p[6] == 40.0:
                    rad         = max(1, int((1.0 - (p[5] / 30.0)) * p[6]))
                    layer_alpha = int(200 * (p[5] / 30.0))
                    surf        = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
                    pygame.draw.circle(surf, (255, 220, 100, layer_alpha), (rad, rad), rad, 3)
                    self.virtual_screen.blit(surf, (int(p[0] - rad), int(p[1] - rad)))
                else:
                    rad = max(1, int((p[5] / 45.0) * p[6]))
                    pygame.draw.circle(self.virtual_screen, p[4], (int(p[0]), int(p[1])), rad)
                surviving.append(p)
        self.particles = surviving

    def update_and_draw_trails(self, alive_indices):
        top_10    = sorted(alive_indices, key=lambda x: self.sandbox.agent_age[x], reverse=True)[:10]
        to_delete = [k for k in self.trails.keys() if k not in top_10]
        for k in to_delete:
            del self.trails[k]

        for aid in top_10:
            if self.sandbox.is_camouflaged[aid]:
                if aid in self.trails:
                    self.trails[aid].clear()
                continue
            if aid not in self.trails:
                self.trails[aid] = []
            pos = self.sandbox.agent_positions[aid]
            self.trails[aid].append((int(pos[0]), int(pos[1])))

            t_len = 100 if self.sandbox.is_overdriving[aid] else 50
            if len(self.trails[aid]) > t_len:
                self.trails[aid].pop(0)

            if len(self.trails[aid]) > 1:
                pts          = self.trails[aid]
                is_legendary = self.sandbox.kill_count[aid] >= 7
                c            = (20, 5, 20) if is_legendary else (100, 100, 100)
                for i in range(len(pts) - 1):
                    alpha     = int((i / len(pts)) * 200) if is_legendary else int((i / len(pts)) * 100)
                    thickness = 4 if is_legendary else 1
                    pygame.draw.line(self.virtual_screen, (*c, alpha), pts[i], pts[i + 1], thickness)

    DESERT_SAND = (210, 180, 140)

    # -----------------------------------------------------------------------
    # HUD: agent panel helper (draws one side card + radar + cam)
    # -----------------------------------------------------------------------
    def _draw_agent_panel(self, surf, panel_x, panel_y, panel_w, agent_idx,
                          badge_label, badge_color, accent_color,
                          actions, active_conn_counts,
                          extra_stats, state_badges,
                          radar_color, base_font, small_font,
                          window_w, show_radar):
        """
        Draws a full agent card panel at (panel_x, panel_y) with width panel_w.
        Background is painted first; all content is drawn on top with absolute coords.
        Returns the bottom y after all content is drawn.
        """
        sb    = self.sandbox
        f     = base_font
        fs    = small_font
        fh    = f.size("W")[1]
        fsh   = fs.size("W")[1]
        pad   = 8
        iw    = panel_w - pad * 2   # inner width

        # ── Pre-measure card height ─────────────────────────────────────────
        # Row heights (same order as draw pass below):
        #   badge pill row + name row + separator + E-bar + V-bar + 2×stat-rows + badges
        badge_surf_tmp = f.render(f" {badge_label} ", True, (0, 0, 0))
        pill_h         = badge_surf_tmp.get_height()

        badge_rows = 0
        if state_badges:
            bx_test = panel_x + pad
            rows    = 1
            for btxt, _ in state_badges:
                b_tmp = fs.render(btxt, True, (0, 0, 0))
                bw    = b_tmp.get_width() + 8
                if bx_test + bw > panel_x + panel_w - pad:
                    rows   += 1
                    bx_test = panel_x + pad
                bx_test += bw + 4
            badge_rows = rows

        card_h = (pad
                  + pill_h + 4          # badge
                  + fh + 4              # name
                  + 1 + 5               # separator
                  + 11                  # E-bar
                  + 13                  # V-bar
                  + (fh + 16) * 2 + 4  # 2×2 stat grid
                  + (fsh + 6) * badge_rows if state_badges else 0
                  + pad)
        # Clamp to a sane minimum
        card_h = max(card_h, 160)

        # ── 1. Panel background (opaque, drawn FIRST) ───────────────────────
        bg_surf = pygame.Surface((panel_w, card_h))
        bg_surf.set_alpha(210)
        bg_surf.fill((12, 12, 18))
        surf.blit(bg_surf, (panel_x, panel_y))
        pygame.draw.rect(surf, (60, 60, 72),
                         (panel_x, panel_y, panel_w, card_h), 1, border_radius=8)

        # ── 2. Content drawn on top with absolute coordinates ───────────────
        cy = panel_y + pad

        # Badge pill
        badge_surf = f.render(f" {badge_label} ", True, (10, 10, 10))
        pill_w, pill_h = badge_surf.get_size()
        pill_rect = pygame.Rect(panel_x + pad, cy, pill_w + 4, pill_h + 2)
        pygame.draw.rect(surf, badge_color, pill_rect, border_radius=4)
        surf.blit(badge_surf, (pill_rect.x + 2, pill_rect.y + 1))
        cy += pill_h + 4

        # Name + age
        name    = self.get_genome_name(agent_idx, sb.is_carnivore[agent_idx])
        age_str = format_age(sb.agent_age[agent_idx])
        energy  = sb.agent_energy[agent_idx]
        name_s  = f.render(name,    True, (220, 220, 225))
        age_s   = fs.render(age_str, True, (160, 160, 168))
        surf.blit(name_s, (panel_x + pad, cy))
        surf.blit(age_s,  (panel_x + panel_w - pad - age_s.get_width(), cy + 2))
        cy += fh + 4

        # Separator
        pygame.draw.line(surf, (55, 60, 72),
                         (panel_x + pad, cy), (panel_x + panel_w - pad, cy), 1)
        cy += 5

        # Energy bar
        e_lbl = fs.render("E", True, (140, 200, 155))
        surf.blit(e_lbl, (panel_x + pad, cy + 1))
        self.draw_status_bar(surf, panel_x + pad + 14, cy, iw - 14, 7,
                             energy, 100.0, (45, 184, 122))
        cy += 11

        # Velocity bar
        vel_mag = np.linalg.norm(sb.agent_velocity[agent_idx])
        v_lbl   = fs.render("V", True, (140, 148, 210))
        surf.blit(v_lbl, (panel_x + pad, cy + 1))
        self.draw_status_bar(surf, panel_x + pad + 14, cy, iw - 14, 7,
                             vel_mag, self.sandbox.max_speed, (100, 140, 255))
        cy += 13

        # Stats 2×2 grid
        half_w = (iw - 4) // 2
        for gi, (lbl_t, val_t) in enumerate(extra_stats):
            gx        = panel_x + pad + (gi % 2) * (half_w + 4)
            gy        = cy + (gi // 2) * (fh + 16)
            cell_rect = pygame.Rect(gx, gy, half_w, fh + 14)
            # Solid (non-alpha) cell background so it shows on the HUD surface
            cell_bg = pygame.Surface((half_w, fh + 14))
            cell_bg.fill((22, 24, 34))
            surf.blit(cell_bg, (gx, gy))
            pygame.draw.rect(surf, (40, 42, 55), cell_rect, 1, border_radius=4)
            lbl_s = fs.render(lbl_t, True, (110, 110, 120))
            val_s = f.render(val_t,  True, accent_color)
            surf.blit(lbl_s, (gx + 4, gy + 2))
            surf.blit(val_s, (gx + 4, gy + 2 + fsh))
        cy += (fh + 16) * 2 + 4

        # State badge pills
        if state_badges:
            bx = panel_x + pad
            for btxt, bcol in state_badges:
                b_s = fs.render(btxt, True, (240, 240, 240))
                bw  = b_s.get_width() + 8
                bh  = b_s.get_height() + 4
                if bx + bw > panel_x + panel_w - pad:
                    bx  = panel_x + pad
                    cy += bh + 2
                br = pygame.Rect(bx, cy, bw, bh)
                pygame.draw.rect(surf, bcol, br, border_radius=3)
                surf.blit(b_s, (bx + 4, cy + 2))
                bx += bw + 4
            cy += fsh + 8

        cy = panel_y + card_h + 6

        # ── Radar (inline, only if window wide enough) ──────────────────────
        if show_radar:
            radar_cx = panel_x + panel_w // 2
            radar_cy = cy + 78
            self.draw_neural_radar(surf, radar_cx, radar_cy, actions, agent_idx,
                                   radar_color, scale=0.75)
            cy = radar_cy + 85

        # ── Tracking cam ────────────────────────────────────────────────────
        cam_cx = panel_x + panel_w // 2
        cam_cy = cy + 68
        self.draw_tracking_cam(surf, cam_cx, cam_cy, agent_idx, scale=0.85)
        cy = cam_cy + 72

        return cy

    # -----------------------------------------------------------------------
    # HUD: main draw_hud  (called from render())
    # -----------------------------------------------------------------------
    def draw_hud(self, surf, actions, active_conn_counts, genetic_drift_active,
                 alive_indices, alpha_idx, legendary_idx, carnivores_alive, tick, generation):

        # ── Style constants ──────────────────────────────────────────────────
        COLOR_HERB   = (45,  184, 122)
        COLOR_CARN   = (224,  64,  64)
        COLOR_PURPLE = (167, 139, 250)
        COLOR_AMBER  = (251, 191,  36)
        COLOR_MUTED  = (180, 180, 190)
        COLOR_TEXT   = (200, 200, 205)
        panel_width  = 200
        panel_radius = 8

        window_w, window_h = surf.get_size()
        margin        = max(8, int(window_w * 0.01))
        base_font_sz  = max(13, window_h // 45)
        show_radar    = window_w >= 900

        # Scaled fonts on-the-fly (cache by size to avoid re-creating every frame)
        if not hasattr(self, '_hud_fonts') or self._hud_fonts[0] != base_font_sz:
            self._hud_fonts = (
                base_font_sz,
                pygame.font.SysFont("Consolas", base_font_sz),
                pygame.font.SysFont("Consolas", max(9, base_font_sz - 2)),
                pygame.font.SysFont("Consolas", base_font_sz + 4, bold=True),
            )
        _, f, fs, fl = self._hud_fonts
        fh = f.size("W")[1]

        # Layout anchors
        left_x   = margin
        right_x  = window_w - panel_width - margin
        center_x = panel_width + margin
        center_w = window_w - 2 * (panel_width + margin)

        sb = self.sandbox

        # ════════════════════════════════════════════════════════════════════
        # CENTER STRIP
        # ════════════════════════════════════════════════════════════════════
        cy = margin

        # Row 1: World name (large, spaced)
        world_spaced = "  ".join(self.world_name.upper())
        wn_s = fl.render(world_spaced, True, COLOR_TEXT)
        surf.blit(wn_s, (center_x + (center_w - wn_s.get_width()) // 2, cy))
        cy += wn_s.get_height() + 4

        # Row 2: Pop counters
        total_pop  = len(alive_indices)
        prey_count = total_pop - carnivores_alive
        pills = [
            (f"TOTAL  {total_pop}",        COLOR_TEXT),
            (f"PRESAS  {prey_count}",       COLOR_HERB),
            (f"CAZADORES  {carnivores_alive}", COLOR_CARN),
        ]
        pill_gap = 12
        pill_surfaces = [f.render(t, True, c) for t, c in pills]
        total_pill_w  = sum(s.get_width() for s in pill_surfaces) + pill_gap * (len(pills) - 1)
        px_start      = center_x + (center_w - total_pill_w) // 2
        for ps in pill_surfaces:
            surf.blit(ps, (px_start, cy))
            px_start += ps.get_width() + pill_gap
        cy += fh + 6

        # Row 3: Neural complexity bar
        alive_mask = sb.agent_alive
        avg_nexos  = int(np.mean(active_conn_counts[alive_mask])) if np.any(alive_mask) else 0
        bar_lbl    = fs.render("Complejidad", True, COLOR_MUTED)
        bar_val    = fs.render(f"{avg_nexos} nexos", True, COLOR_PURPLE)
        bar_x      = center_x + bar_lbl.get_width() + 6
        bar_w      = center_w - bar_lbl.get_width() - bar_val.get_width() - 16
        bar_h      = 6
        bar_y      = cy + (fh - bar_h) // 2
        surf.blit(bar_lbl, (center_x, cy))
        pygame.draw.rect(surf, (40, 40, 50), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        if avg_nexos > 0:
            fill_w = max(4, int(min(avg_nexos, 100) / 100 * bar_w))
            pygame.draw.rect(surf, COLOR_PURPLE, (bar_x, bar_y, fill_w, bar_h), border_radius=3)
        surf.blit(bar_val, (bar_x + bar_w + 4, cy))
        cy += fh + 5

        # Row 4: Oracle message
        if self.oracle_timer > 0 and not self.full_screen_overlay:
            first_line = self.oracle_msg.split('\n')[0]
            max_chars  = max(10, center_w // max(1, f.size("W")[0]))
            if len(first_line) > max_chars:
                first_line = first_line[:max_chars - 1] + "…"
            om_s  = f.render(first_line, True, COLOR_AMBER)
            om_x  = center_x + (center_w - om_s.get_width()) // 2
            om_y  = cy
            om_bg = pygame.Surface((om_s.get_width() + 8, fh + 4))
            om_bg.set_alpha(140)
            om_bg.fill((0, 0, 0))
            surf.blit(om_bg, (om_x - 4, om_y - 2))
            surf.blit(om_s, (om_x, om_y))
        cy += fh + 4

        # Row 5: Pill row — Gen / Tick / Deriva / Sequía
        if sb.drought_active:
            secs_left    = max(0, (400 - sb.drought_timer) // 30)
            drought_pill = f"SEQUÍA ACTIVA ({secs_left}s)"
            drought_col  = COLOR_CARN
        else:
            secs_next    = max(0, (5000 - sb.drought_timer) // 30)
            drought_pill = f"Sequía en {secs_next}s"
            drought_col  = COLOR_AMBER

        pills5 = [
            (f"Gen {generation}",                                   COLOR_MUTED),
            (f"Tick {tick}",                                        COLOR_MUTED),
            (f"Deriva: {'ACTIVA' if genetic_drift_active else 'EN ESPERA'}", COLOR_HERB if genetic_drift_active else COLOR_MUTED),
            (drought_pill,                                          drought_col),
        ]
        px5 = center_x
        for ptxt, pcol in pills5:
            ps5 = fs.render(ptxt, True, pcol)
            surf.blit(ps5, (px5, cy))
            px5 += ps5.get_width() + 10
        # cy += fh  # (no need — center strip done)

        # ════════════════════════════════════════════════════════════════════
        # LEFT PANEL — ALFA (longest-living agent)
        # ════════════════════════════════════════════════════════════════════
        if len(alive_indices) > 0:
            ai     = alpha_idx
            energy = sb.agent_energy[ai]
            age_t  = sb.agent_age[ai]
            nexos  = active_conn_counts[ai]
            kills  = sb.kill_count[ai]
            sig    = sb.agent_signals[ai]
            assists= sb.signal_assists[ai]

            state_badges_l = []
            if sb.in_thicket[ai]:
                state_badges_l.append(("En thicket", (30, 120, 60)))
            if sb.is_camouflaged[ai]:
                state_badges_l.append(("Camuflado", (30, 60, 160)))
            if sb.invulnerability_frames[ai] > 0:
                state_badges_l.append(("Invulnerable", (160, 130, 10)))

            self._draw_agent_panel(
                surf, left_x, margin, panel_width,
                ai,
                "ALFA",  (45, 184, 122),  (45, 184, 122),
                actions, active_conn_counts,
                [
                    ("Nexos",       str(nexos)),
                    ("Señal emit.", f"{sig:.2f}"),
                    ("Asistencias", str(assists)),
                    ("Kills",       str(kills)),
                ],
                state_badges_l,
                (0, 200, 220),
                f, fs,
                window_w, show_radar,
            )

        # ════════════════════════════════════════════════════════════════════
        # RIGHT PANEL — TITÁN (highest-kill carnivore)
        # ════════════════════════════════════════════════════════════════════
        if legendary_idx is not None:
            li     = legendary_idx
            energy_l = sb.agent_energy[li]
            age_l    = sb.agent_age[li]
            nexos_l  = active_conn_counts[li]
            kills_l  = sb.kill_count[li]

            # Kills/min: kill_count / (age_ticks / 1800) clamped min 1
            kpm = kills_l / max(1, age_l / 1800)

            # Fitness score
            fit_score = int(energy_l * 5 + age_l * 0.1 + kills_l * 50)

            badge_lbl  = "TITÁN"   if kills_l >= 7 else "DEPREDADOR"
            badge_col  = (160, 30, 30) if kills_l >= 7 else (130, 50, 50)

            state_badges_r = []
            if kills_l >= 7:
                state_badges_r.append(("Legendario ★", (100, 20, 160)))
            if sb.is_overdriving[li]:
                state_badges_r.append(("Overdrive", (160, 130, 10)))
            if sb.true_sight[li]:
                state_badges_r.append(("Rastreador", (160, 20, 160)))

            self._draw_agent_panel(
                surf, right_x, margin, panel_width,
                li,
                badge_lbl, badge_col, COLOR_CARN,
                actions, active_conn_counts,
                [
                    ("Nexos",      str(nexos_l)),
                    ("Kills",      str(kills_l)),
                    ("K/min",      f"{kpm:.1f}"),
                    ("Fitness",    str(fit_score)),
                ],
                state_badges_r,
                (220, 60, 60),
                f, fs,
                window_w, show_radar,
            )

        # ════════════════════════════════════════════════════════════════════
        # [?] Help button  — top-right corner
        # ════════════════════════════════════════════════════════════════════
        btn_sz   = 28
        btn_rect = pygame.Rect(window_w - btn_sz - 6, 6, btn_sz, btn_sz)
        pygame.draw.rect(surf, (30, 60, 100, 180), btn_rect, border_radius=6)
        pygame.draw.rect(surf, (100, 180, 255, 200), btn_rect, 1, border_radius=6)
        qm  = self.font.render("?", True, (255, 255, 255))
        surf.blit(qm, (btn_rect.centerx - qm.get_width() // 2,
                       btn_rect.centery - qm.get_height() // 2))

        return btn_rect   # caller uses for hit-test

    # -----------------------------------------------------------------------
    # Help overlay (two sections, tabbed)
    # -----------------------------------------------------------------------
    def draw_help_overlay(self, surf):
        """Draws the help overlay directly on `surf`. Call every frame while open."""
        window_w, window_h = surf.get_size()
        ow, oh  = 480, 340
        ox      = (window_w - ow) // 2
        oy      = (window_h - oh) // 2

        # Background
        bg = pygame.Surface((ow, oh), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 210))
        pygame.draw.rect(bg, (80, 80, 100, 120), (0, 0, ow, oh), 1, border_radius=12)
        surf.blit(bg, (ox, oy))

        f  = self.font
        fs = self.small_font
        fl = self.large_font

        # Section tabs
        tab_labels = ["CONTROLES", "CLASES Y COLORES"]
        tab_w      = ow // len(tab_labels)
        for ti, tlbl in enumerate(tab_labels):
            active  = ti == self._help_section
            tx      = ox + ti * tab_w
            tab_col = (40, 90, 150, 220) if active else (20, 20, 30, 180)
            pygame.draw.rect(surf, tab_col, (tx, oy, tab_w, 30))
            ts = f.render(tlbl, True, (220, 220, 225) if active else (90, 90, 100))
            surf.blit(ts, (tx + tab_w // 2 - ts.get_width() // 2, oy + 7))
        pygame.draw.line(surf, (60, 120, 200), (ox, oy + 30), (ox + ow, oy + 30), 1)

        content_y = oy + 38
        pad       = 20

        if self._help_section == 0:
            # ── Controls section ─────────────────────────────────
            entries = [
                ("ESC",        "Volver al menú"),
                ("ESPACIO",    "Big Crunch (colapso gravitatorio)"),
                ("M",          "Meteorito en cursor"),
                ("F",          "Inundación (regenera comida)"),
                ("R",          "Radiación (elimina 50% agentes)"),
                ("Click izq.", "Mini meteorito"),
                ("Scroll",     "Zoom manual"),
                ("H",          "Abrir/cerrar este panel"),
            ]
            for key_t, desc_t in entries:
                key_s  = f.render(key_t,  True, (100, 200, 255))
                desc_s = f.render(desc_t, True, (180, 180, 185))
                key_col_w = 100
                surf.blit(key_s,  (ox + pad, content_y))
                surf.blit(desc_s, (ox + pad + key_col_w, content_y))
                content_y += key_s.get_height() + 4
        else:
            # ── Classes & colors section ──────────────────────────
            entries = [
                ((0, 255, 255),   "Evasivo (Cian)",        "Comportamiento estándar de supervivencia."),
                ((50, 100, 255),  "Explorador (Azul)",     "Alta inercia, patrulla el mapa."),
                ((255, 100, 0),   "Territorial (Naranja)", "Estacionario, reclama zonas de comida."),
                ((100, 100, 100), "Oculto (Gris)",         "Usando neuronas de camuflaje biológico."),
                ((255, 215, 0),   "Sabio (Dorado)",        "Veterano (Edad >10000) o alta complejidad."),
                ((200, 10, 10),   "Depredador (Rojo)",     "Carnívoro de primer nivel."),
                ((180, 0, 180),   "Rastreador (Magenta)",  "Cazador mutante: inmune al camuflaje."),
                ((255, 255, 0),   "Titán Alfa (Amarillo)", "Leyenda con más de 7 víctimas directas."),
            ]
            for col, name_t, desc_t in entries:
                pygame.draw.circle(surf, col, (ox + pad + 6, content_y + 7), 6)
                name_s = f.render(name_t,  True, col)
                desc_s = fs.render(desc_t, True, (140, 140, 145))
                surf.blit(name_s, (ox + pad + 18, content_y))
                surf.blit(desc_s, (ox + pad + 18, content_y + name_s.get_height()))
                content_y += name_s.get_height() + desc_s.get_height() + 2

        # Navigation arrows and close button
        arrow_y  = oy + oh - 30
        # < prev
        prev_rect = pygame.Rect(ox + 14, arrow_y, 28, 22)
        pygame.draw.rect(surf, (40, 60, 90, 200), prev_rect, border_radius=4)
        surf.blit(f.render("<", True, (180, 180, 200)), (prev_rect.x + 8, prev_rect.y + 2))
        # > next
        next_rect = pygame.Rect(ox + 50, arrow_y, 28, 22)
        pygame.draw.rect(surf, (40, 60, 90, 200), next_rect, border_radius=4)
        surf.blit(f.render(">", True, (180, 180, 200)), (next_rect.x + 8, next_rect.y + 2))
        # hint
        hint_s = fs.render("← → o Tab para cambiar sección", True, (80, 80, 90))
        surf.blit(hint_s, (ox + 90, arrow_y + 5))
        # X close
        close_rect = pygame.Rect(ox + ow - 36, oy + 2, 28, 26)
        pygame.draw.rect(surf, (90, 30, 30, 200), close_rect, border_radius=4)
        surf.blit(f.render("X", True, (255, 100, 100)), (close_rect.x + 7, close_rect.y + 4))

        return prev_rect, next_rect, close_rect

    # -----------------------------------------------------------------------
    # Main render loop
    # -----------------------------------------------------------------------
    def render(self, actions, active_conn_counts, genetic_drift_active=False,
               tick=0, generation=0):
        # Fondo
        if self.sandbox.drought_active:
            self.virtual_screen.fill(self.DESERT_SAND)
        else:
            self.virtual_screen.blit(self.fade_surf, (0, 0))
        self.virtual_screen.blit(self.grid_surf, (0, 0))
        self.real_screen.fill((5, 5, 5))

        window_w, window_h = self.real_screen.get_size()
        sim_w  = window_w
        scale  = min(sim_w / self.base_w, window_h / self.base_h)
        scaled_w = int(self.base_w * scale)
        scaled_h = int(self.base_h * scale)
        offset_x = (window_w - scaled_w) // 2
        offset_y = (window_h - scaled_h) // 2

        panel_width = 200

        def get_virtual_mouse(m_pos):
            mx, my   = m_pos
            vx_scaled = mx - offset_x
            vy_scaled = my - offset_y
            if self.camera_zoom > 1.01:
                cw = self.base_w / self.camera_zoom
                ch = self.base_h / self.camera_zoom
                cx = np.clip(self.camera_target[0] - cw / 2, 0, self.base_w - cw)
                cy = np.clip(self.camera_target[1] - ch / 2, 0, self.base_h - ch)
                return (vx_scaled / scale / self.camera_zoom) + cx, \
                       (vy_scaled / scale / self.camera_zoom) + cy
            return vx_scaled / scale, vy_scaled / scale

        m_pos         = pygame.mouse.get_pos()
        old_vx, old_vy = get_virtual_mouse(m_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.should_quit = True
                return
            if event.type == pygame.VIDEORESIZE:
                self.real_screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_h:
                    self._help_open = not self._help_open

            if self._help_open:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE,):
                        self._help_open = False
                    elif event.key in (pygame.K_RIGHT, pygame.K_TAB):
                        self._help_section = (self._help_section + 1) % 2
                    elif event.key == pygame.K_LEFT:
                        self._help_section = (self._help_section - 1) % 2
                # Mouse handled after overlay draw (hit-test on returned rects)
                continue   # skip world interaction while help is open

            if event.type == pygame.MOUSEWHEEL:
                margin = max(8, int(window_w * 0.01))
                left_edge  = panel_width + margin
                right_edge = window_w - panel_width - margin
                if m_pos[0] < left_edge or m_pos[0] > right_edge:
                    continue
                self.manual_zoom = max(1.0, self.manual_zoom + event.y * 0.1)
                self.camera_zoom = self.manual_zoom
                if self.manual_zoom > 1.01:
                    vx_s = m_pos[0] - offset_x
                    vy_s = m_pos[1] - offset_y
                    new_tx = old_vx - (vx_s / scale / self.manual_zoom) + (self.base_w / (2 * self.manual_zoom))
                    new_ty = old_vy - (vy_s / scale / self.manual_zoom) + (self.base_h / (2 * self.manual_zoom))
                    cw = self.base_w / self.manual_zoom
                    ch = self.base_h / self.manual_zoom
                    self.camera_target[0] = np.clip(new_tx, cw / 2, self.base_w - cw / 2)
                    self.camera_target[1] = np.clip(new_ty, ch / 2, self.base_h - ch / 2)
                else:
                    self.camera_target = np.array([self.base_w / 2, self.base_h / 2], dtype=np.float32)

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
                margin     = max(8, int(window_w * 0.01))
                left_edge  = panel_width + margin
                right_edge = window_w - panel_width - margin
                # ? button (top-right corner area)
                if m_pos[0] >= window_w - 40 and m_pos[1] <= 40:
                    self._help_open = not self._help_open
                    continue
                if m_pos[0] < left_edge or m_pos[0] > right_edge:
                    continue
                vx, vy = get_virtual_mouse(event.pos)
                self.god_mode.trigger_meteor(vx, vy, radius=70.0)

        # ── World objects ────────────────────────────────────────────────────
        alive_mask    = self.sandbox.agent_alive
        alive_indices = np.where(alive_mask)[0]

        speeds            = np.linalg.norm(self.sandbox.agent_positions - self.previous_positions, axis=1)
        self.ema_velocity = self.ema_velocity * 0.98 + speeds * 0.02

        if self.sandbox.oracle_deaths >= 100:
            self.sandbox.oracle_deaths = 0
            if len(alive_indices) > 0:
                dom, col, stats = self.oracle.compute_archetype(active_conn_counts, actions, self.sandbox)
                self.oracle_msg   = f"ORÁCULO POST-MORTEM: La Era está dominada por {dom}.\n>>> {stats}"
                self.oracle_timer = 240
                self.full_screen_overlay = False

        if self.sandbox.big_crunch and self.sandbox.big_crunch_progress > 1.95 and not self.full_screen_overlay:
            if len(alive_indices) > 0:
                dom, col, stats = self.oracle.compute_archetype(active_conn_counts, actions, self.sandbox)
                alpha           = alive_indices[np.argmax(self.sandbox.agent_age[alive_indices])]
                self.oracle.save_epoch(dom, self.sandbox.agent_age[alpha], alpha,
                                       active_conn_counts[alpha], np.max(self.sandbox.kill_count))
                self.oracle_msg = (f"GRAN COLAPSO\nEra de {dom}\n"
                                   f"Complejidad del Alfa: {active_conn_counts[alpha]}\n"
                                   f">>> {stats}\nReiniciando Entorno...")
            else:
                self.oracle_msg = "GRAN COLAPSO\nExtinción Alcanzada.\nReiniciando Entorno..."
            self.oracle_timer        = 240
            self.full_screen_overlay = True

        frame_time = pygame.time.get_ticks() / 1000.0

        # Thickets
        for tx, ty, tr in self.sandbox.thickets:
            jitter     = np.sin(frame_time * 10.0 + tx) * 2.0
            r_jit      = tr + jitter
            scaled_thick = pygame.transform.scale(self.tex_thicket, (int(r_jit * 2), int(r_jit * 2)))
            self.virtual_screen.blit(scaled_thick, (int(tx - r_jit), int(ty - r_jit)))

        # Burrows
        for bx, by, br in self.sandbox.burrows:
            pygame.draw.circle(self.virtual_screen, (5, 5, 5),     (int(bx), int(by)), int(br))
            pygame.draw.circle(self.virtual_screen, (80, 20, 80),  (int(bx), int(by)), int(br), 2)

        # Food
        for fx, fy in self.sandbox.food_positions[self.sandbox.food_active]:
            pygame.draw.circle(self.virtual_screen, (40, 150, 40), (int(fx), int(fy)), 6)
            self.virtual_screen.blit(self.tex_comida, (int(fx) - 4, int(fy) - 4))

        alpha_idx      = None
        legendary_idx  = None
        carnivores_alive = 0

        if len(alive_indices) > 0:
            for px_, py_ in self.sandbox.pulse_events:
                self.particles.append([px_, py_, 0, 0, (200, 200, 200), 20, 80.0])
            for sx, sy in self.sandbox.spawn_events:
                self.particles.append([sx, sy, 0, 0, (255, 220, 100), 30, 40.0])
            for p_event in self.sandbox.predation_events:
                self.trigger_predation_sparks(p_event)

            for parent, child in self.sandbox.clones_produced_this_tick:
                p_pos  = self.sandbox.agent_positions[parent]
                c_pos  = self.sandbox.agent_positions[child]
                p_col, _ = self.get_agent_aura(parent, actions, active_conn_counts)
                c_col, _ = self.get_agent_aura(child,  actions, active_conn_counts)
                diff   = c_pos - p_pos
                dist   = np.linalg.norm(diff)
                if dist > 0.1:
                    dir_v  = diff / dist
                    perp_v = np.array([-dir_v[1], dir_v[0]])
                    for i in range(30):
                        t     = i / 29.0
                        mid_c = (int(p_col[0] + (c_col[0] - p_col[0]) * t),
                                 int(p_col[1] + (c_col[1] - p_col[1]) * t),
                                 int(p_col[2] + (c_col[2] - p_col[2]) * t))
                        bx_   = p_pos[0] + dir_v[0] * dist * t
                        by_   = p_pos[1] + dir_v[1] * dist * t
                        w1    = np.sin(t * np.pi * 4) * 8.0
                        self.particles.append([bx_ + perp_v[0] * w1, by_ + perp_v[1] * w1, 0, 0, mid_c, 45, 2.0])
                        w2    = np.sin(t * np.pi * 4 + np.pi) * 8.0
                        self.particles.append([bx_ + perp_v[0] * w2, by_ + perp_v[1] * w2, 0, 0, mid_c, 45, 2.0])
                        if len(self.particles) > 500:
                            self.particles = self.particles[20:]

            self.update_and_draw_trails(alive_indices)
            alpha_idx = alive_indices[np.argmax(self.sandbox.agent_age[alive_indices])]

            carnivore_idx = np.where(self.sandbox.is_carnivore & self.sandbox.agent_alive)[0]
            if len(carnivore_idx) > 0:
                legendary_idx = carnivore_idx[np.argmax(self.sandbox.kill_count[carnivore_idx])]

            if (self.last_alpha_id != -1 and self.last_alpha_id != alpha_idx
                    and self.sandbox.agent_alive[alpha_idx]):
                if not self.sandbox.agent_alive[self.last_alpha_id]:
                    old_pos = self.sandbox.agent_positions[self.last_alpha_id]
                    new_pos = self.sandbox.agent_positions[alpha_idx]
                    self.laser_coords = ((int(old_pos[0]), int(old_pos[1])),
                                        (int(new_pos[0]), int(new_pos[1])))
                    self.laser_timer  = 30
            self.last_alpha_id = alpha_idx

            for idx in alive_indices:
                pos = self.sandbox.agent_positions[idx].copy()
                if self.sandbox.is_overdriving[idx]:
                    pos += np.random.uniform(-1, 1, 2)

                prev_pos = self.previous_positions[idx]
                dx, dy   = pos[0] - prev_pos[0], pos[1] - prev_pos[1]
                if abs(dx) > 0.01 or abs(dy) > 0.01:
                    self.sandbox.agent_angles[idx] = math.degrees(math.atan2(-dy, dx))
                angle  = self.sandbox.agent_angles[idx]
                energy = self.sandbox.agent_energy[idx]
                color, _ = self.get_agent_aura(idx, actions, active_conn_counts)

                if self.sandbox.is_carnivore[idx] and energy < 20.0 and np.random.random() > 0.5:
                    color = (20, 0, 0)

                is_camo     = self.sandbox.is_camouflaged[idx]
                base_radius = max(2, int(np.log(energy + 1.0) * 2.5))

                if is_camo:
                    self.draw_polygon_glow(self.virtual_screen, color, pos, angle, base_radius // 2, idx, active_conn_counts)
                else:
                    self.draw_polygon_glow(self.virtual_screen, color, pos, angle, base_radius, idx, active_conn_counts)

                if self.sandbox.is_carnivore[idx]:
                    carnivores_alive += 1

                px_, py_ = int(pos[0]), int(pos[1])

                if idx == alpha_idx:
                    pygame.draw.circle(self.virtual_screen, (255, 255, 255), (px_, py_), base_radius + 4, 1)
                    arrow_y = py_ - base_radius - 14
                    arrow_pts = [(px_, arrow_y + 8), (px_ - 5, arrow_y), (px_ + 5, arrow_y)]
                    pygame.draw.polygon(self.virtual_screen, (255, 255, 255), arrow_pts, 0)
                    lbl = self.font.render("A", True, (255, 255, 255))
                    self.virtual_screen.blit(lbl, (px_ - lbl.get_width() // 2, arrow_y - 14))

                if self.sandbox.is_carnivore[idx] and self.sandbox.kill_count[idx] >= 7:
                    arrow_y   = py_ - base_radius - 14
                    arrow_pts = [(px_, arrow_y + 8), (px_ - 5, arrow_y), (px_ + 5, arrow_y)]
                    pygame.draw.polygon(self.virtual_screen, (180, 0, 255), arrow_pts, 0)
                    kills     = self.sandbox.kill_count[idx]
                    lbl       = self.font.render(f"★{kills}", True, (180, 0, 255))
                    self.virtual_screen.blit(lbl, (px_ - lbl.get_width() // 2, arrow_y - 14))

            if self.laser_timer > 0:
                self.laser_timer -= 1
                pygame.draw.line(self.virtual_screen, (255, 255, 255),
                                 self.laser_coords[0], self.laser_coords[1],
                                 max(1, int(self.laser_timer / 10)))

        self.update_and_draw_particles()

        if self.oracle_timer > 0:
            self.oracle_timer -= 1
            if self.full_screen_overlay:
                self.virtual_screen.blit(self.overlay_surf, (0, 0))
                lines = self.oracle_msg.split('\n')
                for i, ln in enumerate(lines):
                    ren = self.large_font.render(ln, True, (255, 255, 255))
                    self.virtual_screen.blit(ren, (self.base_w // 2 - ren.get_width() // 2,
                                                   self.base_h // 2 - 40 + 30 * i))

        # Screen shake
        shake_x = shake_y = 0
        if self.god_mode.screen_shake > 0.5:
            shake_x = np.random.uniform(-self.god_mode.screen_shake, self.god_mode.screen_shake) * 0.3
            shake_y = np.random.uniform(-self.god_mode.screen_shake, self.god_mode.screen_shake) * 0.3
            self.god_mode.screen_shake *= 0.8

        # Camera zoom sub-surface
        if self.camera_zoom > 1.01:
            cw_      = int(self.base_w / self.camera_zoom)
            ch_      = int(self.base_h / self.camera_zoom)
            cx_      = int(np.clip(self.camera_target[0] - cw_ / 2, 0, self.base_w - cw_))
            cy_      = int(np.clip(self.camera_target[1] - ch_ / 2, 0, self.base_h - ch_))
            sub_rect = pygame.Rect(cx_, cy_, cw_, ch_)
            sub_surf = self.virtual_screen.subsurface(sub_rect)
            scaled_virtual = pygame.transform.smoothscale(sub_surf, (scaled_w, scaled_h))
        else:
            scaled_virtual = pygame.transform.smoothscale(self.virtual_screen, (scaled_w, scaled_h))

        if self.sandbox.legendary_pulse_frames > 0:
            self.sandbox.legendary_pulse_frames -= 1

        self.real_screen.blit(scaled_virtual, (offset_x + shake_x, offset_y + shake_y))

        # HUD overlay
        self.hud_surface = pygame.Surface((window_w, window_h), pygame.SRCALPHA)

        btn_rect = None
        if len(alive_indices) > 0 and alpha_idx is not None:
            btn_rect = self.draw_hud(
                self.hud_surface, actions, active_conn_counts, genetic_drift_active,
                alive_indices, alpha_idx, legendary_idx, carnivores_alive, tick, generation,
            )

        self.real_screen.blit(self.hud_surface, (0, 0))

        # Help overlay (drawn on real_screen after hud)
        if self._help_open:
            help_surf = pygame.Surface((window_w, window_h), pygame.SRCALPHA)
            prev_r, next_r, close_r = self.draw_help_overlay(help_surf)
            self.real_screen.blit(help_surf, (0, 0))

            # Handle clicks on nav/close buttons this frame
            mpos = pygame.mouse.get_pos()
            if pygame.mouse.get_pressed()[0]:
                if not hasattr(self, '_help_click_consumed'):
                    self._help_click_consumed = False
                if not self._help_click_consumed:
                    if close_r.collidepoint(mpos):
                        self._help_open           = False
                        self._help_click_consumed = True
                    elif prev_r.collidepoint(mpos):
                        self._help_section        = (self._help_section - 1) % 2
                        self._help_click_consumed = True
                    elif next_r.collidepoint(mpos):
                        self._help_section        = (self._help_section + 1) % 2
                        self._help_click_consumed = True
            else:
                self._help_click_consumed = False

        self.previous_positions = np.copy(self.sandbox.agent_positions)
        pygame.display.flip()
        self.clock.tick(self.fps)

    # -----------------------------------------------------------------------
    # Extinction screen
    # -----------------------------------------------------------------------
    def show_extinction_screen(self):
        btn_restart = pygame.Rect(self.real_screen.get_width() // 2 - 160,
                                  self.real_screen.get_height() // 2 + 20, 320, 60)
        btn_exit    = pygame.Rect(self.real_screen.get_width() // 2 - 160,
                                  self.real_screen.get_height() // 2 + 100, 320, 60)
        while True:
            self.real_screen.fill((5, 5, 8))
            mx, my = pygame.mouse.get_pos()
            click  = False

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "EXIT"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    click = True

            title = self.large_font.render("EXTINCIÓN TOTAL", True, (255, 50, 50))
            self.real_screen.blit(title, (self.real_screen.get_width() // 2 - title.get_width() // 2,
                                          self.real_screen.get_height() // 3 - 30))
            sub = self.font.render("Todas las formas de vida han perecido.", True, (200, 200, 200))
            self.real_screen.blit(sub, (self.real_screen.get_width() // 2 - sub.get_width() // 2,
                                        self.real_screen.get_height() // 3 + 20))

            r_hover = btn_restart.collidepoint((mx, my))
            col_r   = (30, 100, 30) if r_hover else (20, 60, 20)
            pygame.draw.rect(self.real_screen, col_r, btn_restart, border_radius=10)
            pygame.draw.rect(self.real_screen, (0, 255, 0) if r_hover else (50, 120, 50),
                             btn_restart, 2, border_radius=10)
            txt_r = self.font.render("REINICIAR MUNDO", True, (255, 255, 255))
            self.real_screen.blit(txt_r, (btn_restart.centerx - txt_r.get_width() // 2,
                                          btn_restart.centery - txt_r.get_height() // 2))

            e_hover = btn_exit.collidepoint((mx, my))
            col_e   = (100, 30, 30) if e_hover else (60, 20, 20)
            pygame.draw.rect(self.real_screen, col_e, btn_exit, border_radius=10)
            pygame.draw.rect(self.real_screen, (255, 0, 0) if e_hover else (120, 50, 50),
                             btn_exit, 2, border_radius=10)
            txt_e = self.font.render("VOLVER AL MENÚ", True, (255, 255, 255))
            self.real_screen.blit(txt_e, (btn_exit.centerx - txt_e.get_width() // 2,
                                          btn_exit.centery - txt_e.get_height() // 2))

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

    # -----------------------------------------------------------------------
    # Legacy entry point kept for H-key / compatibility
    # -----------------------------------------------------------------------
    def show_codex_loop(self):
        self._help_open    = True
        self._help_section = 1   # open on colors section (old codex behaviour)
