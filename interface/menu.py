import pygame
import os
import json
import glob
from collections import Counter

class MainMenu:
    def __init__(self, width=1120, height=600):
        pygame.init()
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("IpaVerse: Menú Principal")
        
        self.title_font = pygame.font.SysFont("Consolas", 48, bold=True)
        self.font = pygame.font.SysFont("Consolas", 24)
        self.small_font = pygame.font.SysFont("Consolas", 16)
        
        self.clock = pygame.time.Clock()
        self.world_name = "default"
        self.input_text = ""
        self.scroll_offset = 0
        self.selected_world = None
        
    def draw_glowing_rect(self, surface, color, rect, hover=False):
        rx, ry, rw, rh = rect
        glow = 15 if hover else 5
        
        for i in range(glow, 0, -2):
            alpha = int((1.0 - (i/glow)) * 100)
            pygame.draw.rect(surface, (*color, alpha), (rx-i, ry-i, rw+i*2, rh+i*2), border_radius=10)
            
        pygame.draw.rect(surface, color, rect, border_radius=10)
        pygame.draw.rect(surface, (255,255,255) if hover else color, rect, 2, border_radius=10)

    def get_worlds(self):
        """Lista todos los mundos (subcarpetas en history/)."""
        history_dir = "history"
        if not os.path.exists(history_dir):
            os.makedirs(history_dir, exist_ok=True)
            return []
        worlds = []
        for d in sorted(os.listdir(history_dir)):
            full = os.path.join(history_dir, d)
            if os.path.isdir(full):
                epochs = glob.glob(os.path.join(full, "epoch_*.json"))
                worlds.append({"name": d, "epochs": len(epochs), "path": full})
        return worlds

    def get_epochs(self, world_name):
        """Carga todas las épocas de un mundo, ordenadas por timestamp."""
        world_dir = os.path.join("history", world_name)
        if not os.path.exists(world_dir):
            return []
        epochs = []
        for f in sorted(glob.glob(os.path.join(world_dir, "epoch_*.json"))):
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                    data["_filename"] = os.path.basename(f)
                    epochs.append(data)
            except:
                pass
        return epochs

    def run(self):
        state = "MAIN"
        btn_width = 320
        btn_height = 60
        btn_start = pygame.Rect(self.width//2 - btn_width//2, self.height//2 - 40, btn_width, btn_height)
        btn_hist = pygame.Rect(self.width//2 - btn_width//2, self.height//2 + 40, btn_width, btn_height)
        btn_exit = pygame.Rect(self.width//2 - btn_width//2, self.height//2 + 120, btn_width, btn_height)
        btn_confirm = pygame.Rect(self.width//2 - 160, self.height//2 + 60, 320, 60)
        btn_back = pygame.Rect(self.width//2 - btn_width//2, self.height - 80, btn_width, btn_height)
        
        temp_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.input_text = ""
        self.scroll_offset = 0
        self.selected_world = None
        cached_worlds = None
        cached_epochs = None
        
        while True:
            self.screen.fill((10, 15, 20))
            temp_surface.fill((0, 0, 0, 0))
            mx, my = pygame.mouse.get_pos()
            click = False
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "EXIT"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    click = True
                if event.type == pygame.MOUSEWHEEL:
                    if state in ("HISTORY", "HISTORY_WORLD"):
                        self.scroll_offset -= event.y * 40
                        self.scroll_offset = max(0, self.scroll_offset)
                if event.type == pygame.KEYDOWN and state == "NAME_INPUT":
                    if event.key == pygame.K_BACKSPACE:
                        self.input_text = self.input_text[:-1]
                    elif event.key == pygame.K_RETURN:
                        if len(self.input_text.strip()) > 0:
                            self.world_name = self.input_text.strip()
                            return "START"
                    elif event.key == pygame.K_ESCAPE:
                        state = "MAIN"
                        self.input_text = ""
                    else:
                        if len(self.input_text) < 24 and event.unicode.isprintable():
                            self.input_text += event.unicode
            
            if state == "MAIN":
                title = self.title_font.render("IPAVERSE SIMULATOR", True, (0, 255, 200))
                self.screen.blit(title, (self.width//2 - title.get_width()//2, self.height//3 - 50))
                
                start_hover = btn_start.collidepoint((mx, my))
                hist_hover = btn_hist.collidepoint((mx, my))
                exit_hover = btn_exit.collidepoint((mx, my))
                
                self.draw_glowing_rect(temp_surface, (20, 80, 20), btn_start, start_hover)
                self.draw_glowing_rect(temp_surface, (20, 20, 80), btn_hist, hist_hover)
                self.draw_glowing_rect(temp_surface, (80, 20, 20), btn_exit, exit_hover)
                
                self.screen.blit(temp_surface, (0,0))
                
                start_txt = self.font.render("INICIAR SIMULACIÓN", True, (255,255,255))
                hist_txt = self.font.render("HISTORIA", True, (255,255,255))
                exit_txt = self.font.render("SALIR", True, (255,255,255))
                
                self.screen.blit(start_txt, (btn_start.centerx - start_txt.get_width()//2, btn_start.centery - start_txt.get_height()//2))
                self.screen.blit(hist_txt, (btn_hist.centerx - hist_txt.get_width()//2, btn_hist.centery - hist_txt.get_height()//2))
                self.screen.blit(exit_txt, (btn_exit.centerx - exit_txt.get_width()//2, btn_exit.centery - exit_txt.get_height()//2))
                
                if click:
                    if start_hover: 
                        state = "NAME_INPUT"
                        self.input_text = ""
                    if hist_hover: 
                        state = "HISTORY"
                        cached_worlds = self.get_worlds()
                        self.scroll_offset = 0
                    if exit_hover: return "EXIT"

            elif state == "NAME_INPUT":
                current_input = self.input_text.strip()
                world_exists = False
                if len(current_input) > 0:
                    test_path = os.path.join("history", current_input, "neat_pop.pkl")
                    world_exists = os.path.exists(test_path)

                title = self.title_font.render("NOMBRE DEL MUNDO", True, (0, 255, 200))
                self.screen.blit(title, (self.width//2 - title.get_width()//2, self.height//3 - 60))
                
                sub = self.small_font.render("Ingrese un nombre para su universo (Enter para confirmar, Esc para volver)", True, (150, 150, 150))
                self.screen.blit(sub, (self.width//2 - sub.get_width()//2, self.height//3))
                
                # Input box
                input_rect = pygame.Rect(self.width//2 - 200, self.height//2 - 30, 400, 60)
                pygame.draw.rect(self.screen, (20, 25, 35), input_rect, border_radius=8)
                pygame.draw.rect(self.screen, (0, 200, 200), input_rect, 2, border_radius=8)
                
                cursor_char = "|" if (pygame.time.get_ticks() // 500) % 2 == 0 else ""
                txt = self.font.render(self.input_text + cursor_char, True, (255, 255, 255))
                self.screen.blit(txt, (input_rect.x + 15, input_rect.y + 15))
                
                # Confirm button
                confirm_hover = btn_confirm.collidepoint((mx, my))
                
                if world_exists:
                    btn_color = (180, 150, 20) # Gold
                    btn_text = "REANUDAR MUNDO"
                else:
                    btn_color = (20, 80, 20)   # Green
                    btn_text = "INICIAR NUEVO"
                    
                self.draw_glowing_rect(temp_surface, btn_color, btn_confirm, confirm_hover)
                self.screen.blit(temp_surface, (0,0))
                conf_txt = self.font.render(btn_text, True, (255,255,255))
                self.screen.blit(conf_txt, (btn_confirm.centerx - conf_txt.get_width()//2, btn_confirm.centery - conf_txt.get_height()//2))
                
                if click and confirm_hover and len(current_input) > 0:
                    self.world_name = current_input
                    return "START"
            
            elif state == "HISTORY":
                title = self.title_font.render("REGISTRO DE MUNDOS", True, (255, 255, 0))
                self.screen.blit(title, (self.width//2 - title.get_width()//2, 30))
                
                if cached_worlds is None:
                    cached_worlds = self.get_worlds()
                
                if len(cached_worlds) == 0:
                    no_data = self.font.render("No se encontraron mundos registrados.", True, (150, 150, 150))
                    self.screen.blit(no_data, (self.width//2 - no_data.get_width()//2, self.height//2))
                else:
                    y_start = 100 - self.scroll_offset
                    for i, w in enumerate(cached_worlds):
                        wy = y_start + i * 70
                        if wy < 80 or wy > self.height - 100:
                            continue
                        world_rect = pygame.Rect(100, wy, self.width - 200, 60)
                        w_hover = world_rect.collidepoint((mx, my))
                        
                        col = (30, 50, 80) if w_hover else (20, 30, 45)
                        pygame.draw.rect(self.screen, col, world_rect, border_radius=8)
                        pygame.draw.rect(self.screen, (0, 200, 200) if w_hover else (50, 70, 100), world_rect, 2, border_radius=8)
                        
                        name_txt = self.font.render(f"🌍 {w['name'].upper()}", True, (0, 255, 200))
                        epoch_txt = self.small_font.render(f"{w['epochs']} épocas registradas", True, (150, 150, 150))
                        self.screen.blit(name_txt, (world_rect.x + 20, world_rect.y + 8))
                        self.screen.blit(epoch_txt, (world_rect.x + 20, world_rect.y + 36))
                        
                        if click and w_hover:
                            self.selected_world = w['name']
                            cached_epochs = self.get_epochs(w['name'])
                            self.scroll_offset = 0
                            state = "HISTORY_WORLD"
                
                # Back button
                back_hover = btn_back.collidepoint((mx, my))
                self.draw_glowing_rect(temp_surface, (50, 50, 50), btn_back, back_hover)
                self.screen.blit(temp_surface, (0,0))
                back_txt = self.font.render("VOLVER AL MENÚ", True, (255,255,255))
                self.screen.blit(back_txt, (btn_back.centerx - back_txt.get_width()//2, btn_back.centery - back_txt.get_height()//2))
                if click and back_hover:
                    state = "MAIN"
                    self.scroll_offset = 0

            elif state == "HISTORY_WORLD":
                title = self.title_font.render(f"MUNDO: {self.selected_world.upper()}", True, (255, 255, 0))
                self.screen.blit(title, (self.width//2 - title.get_width()//2, 20))
                
                if cached_epochs is None or len(cached_epochs) == 0:
                    no_data = self.font.render("Sin épocas registradas en este mundo.", True, (150, 150, 150))
                    self.screen.blit(no_data, (self.width//2 - no_data.get_width()//2, self.height//2))
                else:
                    # Column headers
                    headers = ["#", "Fecha/Hora", "Era Dominante", "Complejidad", "Muertes"]
                    hx_positions = [30, 70, 330, 710, 880]
                    for hi, header in enumerate(headers):
                        h_ren = self.small_font.render(header, True, (0, 200, 200))
                        self.screen.blit(h_ren, (hx_positions[hi], 70))
                    
                    pygame.draw.line(self.screen, (50, 70, 100), (30, 90), (self.width - 30, 90), 1)
                    
                    y_start = 100 - self.scroll_offset
                    for i, ep in enumerate(cached_epochs):
                        ey = y_start + i * 35
                        if ey < 85 or ey > self.height - 100:
                            continue
                        
                        # Alternate row colors
                        if i % 2 == 0:
                            pygame.draw.rect(self.screen, (15, 20, 30), (25, ey - 2, self.width - 50, 32))
                        
                        ts = ep.get("timestamp_readable", "Desconocido")
                        era = ep.get("era_name", "Desconocido")
                        complexity = ep.get("alpha_complexity", 0)
                        blood = ep.get("blood_spilled", 0)
                        
                        row_data = [f"{i+1}", ts, era, str(complexity), str(blood)]
                        for ci, cell in enumerate(row_data):
                            c_ren = self.small_font.render(cell, True, (200, 200, 200))
                            self.screen.blit(c_ren, (hx_positions[ci], ey + 5))
                
                # Back button
                back_hover = btn_back.collidepoint((mx, my))
                self.draw_glowing_rect(temp_surface, (50, 50, 50), btn_back, back_hover)
                self.screen.blit(temp_surface, (0,0))
                back_txt = self.font.render("VOLVER A MUNDOS", True, (255,255,255))
                self.screen.blit(back_txt, (btn_back.centerx - back_txt.get_width()//2, btn_back.centery - back_txt.get_height()//2))
                if click and back_hover:
                    state = "HISTORY"
                    self.scroll_offset = 0
                    cached_epochs = None
                    
            pygame.display.flip()
            self.clock.tick(30)
