import numpy as np

class GodMode:
    """
    Provides an API to intervene in the Sandbox directly.
    """
    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.screen_shake = 0.0

    def trigger_meteor(self, x, y, radius=100.0):
        alive = self.sandbox.agent_alive
        positions = self.sandbox.agent_positions
        diff = positions - np.array([x, y])
        dist_sq = diff[:, 0]**2 + diff[:, 1]**2
        in_blast = (dist_sq < radius**2) & alive
        self.sandbox.agent_alive[in_blast] = False
        self.screen_shake += 20.0
        print(f"[GOD MODE] Meteor struck at ({x},{y}). Killed {np.sum(in_blast)} agents.")

    def trigger_flood(self):
        self.sandbox._spawn_food(self.sandbox.num_food, overwrite=True)
        print("[GOD MODE] Flood! Re-spawned massive amounts of food.")

    def trigger_radiation(self):
        alive_idx = np.where(self.sandbox.agent_alive)[0]
        if len(alive_idx) > 0:
            kill_count = len(alive_idx) // 2
            kill_idx = np.random.choice(alive_idx, kill_count, replace=False)
            self.sandbox.agent_alive[kill_idx] = False
            self.screen_shake += 10.0
            print(f"[GOD MODE] Radiation hit. Killed {kill_count} agents randomly.")

    def trigger_big_crunch(self):
        self.sandbox.big_crunch = True
        self.sandbox.big_crunch_progress = 0.0
        self.screen_shake += 30.0
        print("[GOD MODE] BIG CRUNCH ACTIVATED: Gravity Sink initiated.")
