import os
import pygame

def build_assets():
    pygame.init()
    os.makedirs("assets/textures", exist_ok=True)
    
    # 1. Presa (Microchip Cyan) 16x16
    surf_presa = pygame.Surface((16, 16), pygame.SRCALPHA)
    pygame.draw.rect(surf_presa, (40, 40, 45, 255), (2, 2, 12, 12), border_radius=2)
    pygame.draw.rect(surf_presa, (80, 80, 90, 255), (4, 4, 8, 8))
    # Contacts
    pygame.draw.line(surf_presa, (200, 200, 200, 255), (1, 4), (3, 4), 1)
    pygame.draw.line(surf_presa, (200, 200, 200, 255), (1, 11), (3, 11), 1)
    pygame.draw.line(surf_presa, (200, 200, 200, 255), (12, 4), (14, 4), 1)
    pygame.draw.line(surf_presa, (200, 200, 200, 255), (12, 11), (14, 11), 1)
    # Core
    pygame.draw.rect(surf_presa, (0, 255, 255, 255), (6, 6, 4, 4))
    pygame.draw.rect(surf_presa, (255, 255, 255, 255), (7, 7, 2, 2))
    pygame.image.save(surf_presa, "assets/textures/presa.png")

    # 2. Depredador (Aggressive Wedge Red) 24x24
    # Drawn facing RIGHT -> 0 degrees
    surf_pred = pygame.Surface((24, 24), pygame.SRCALPHA)
    pts = [(2, 4), (18, 12), (2, 20), (6, 12)]
    pygame.draw.polygon(surf_pred, (200, 10, 10, 255), pts)
    pygame.draw.polygon(surf_pred, (255, 100, 100, 255), pts, 1)
    # Mechanical ridges
    pygame.draw.line(surf_pred, (100, 5, 5, 255), (6, 10), (12, 12), 2)
    pygame.draw.line(surf_pred, (100, 5, 5, 255), (6, 14), (12, 12), 2)
    pygame.draw.circle(surf_pred, (255, 255, 0, 255), (12, 12), 2) # small eye
    pygame.image.save(surf_pred, "assets/textures/depredador.png")

    # 3. Comida (Data Crystal Lime-Green) 8x8
    surf_food = pygame.Surface((8, 8), pygame.SRCALPHA)
    pts_c = [(4, 0), (8, 4), (4, 8), (0, 4)]
    pygame.draw.polygon(surf_food, (100, 255, 100, 255), pts_c)
    pygame.draw.polygon(surf_food, (200, 255, 200, 255), pts_c, 1)
    pygame.image.save(surf_food, "assets/textures/comida.png")

    # 4. Thicket (Circular Mesh with Spikes) 32x32
    surf_thicket = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.circle(surf_thicket, (50, 255, 50, 60), (16, 16), 14)
    pygame.draw.circle(surf_thicket, (20, 200, 20, 150), (16, 16), 14, 2)
    # Spikes around the perimeter
    import math
    for deg in range(0, 360, 30):
        rad = math.radians(deg)
        x1 = 16 + 14 * math.cos(rad)
        y1 = 16 + 14 * math.sin(rad)
        x2 = 16 + 18 * math.cos(rad)
        y2 = 16 + 18 * math.sin(rad)
        pygame.draw.line(surf_thicket, (20, 255, 20, 200), (x1, y1), (x2, y2), 1)
    pygame.image.save(surf_thicket, "assets/textures/thicket.png")

    # 5. Sangre (Pixelated Glitch effect) 16x16
    surf_blood = pygame.Surface((16, 16), pygame.SRCALPHA)
    import random
    random.seed(42)
    for _ in range(15):
        rx, ry = random.randint(0, 15), random.randint(0, 15)
        c = random.choice([(255, 0, 0, 200), (150, 0, 0, 255), (200, 50, 50, 150)])
        pygame.draw.rect(surf_blood, c, (rx, ry, 2, 2))
    pygame.image.save(surf_blood, "assets/textures/sangre.png")

    print("[ASSETS] Generated 5 Pixel-Art Textures perfectly in assets/textures/")

if __name__ == "__main__":
    build_assets()
