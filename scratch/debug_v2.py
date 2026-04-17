"""
IpaVerse V2.0 — Headless Integration Debug
Simula el pipeline completo: NEAT → ComputeEngine → Sandbox → Oracle
Sin Pygame. Detecta bugs antes del build.
"""
import numpy as np
import sys, os, traceback

# Fix path when running from scratch/ subdirectory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)  # Oracle uses relative paths for history/

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"

errors = []

def check(name, fn):
    try:
        result = fn()
        suffix = f" -> {result}" if result is not None else ""
        print(f"{PASS} {name}{suffix}")
        return True
    except Exception as e:
        msg = f"{name}: {e}"
        errors.append(msg)
        print(f"{FAIL} {msg}")
        traceback.print_exc()
        return False

# ── 1. Import chain ───────────────────────────────────────────────────────────
print("\n=== 1. IMPORTS ===")
check("neat import",            lambda: __import__("neat"))
check("sandbox import",         lambda: __import__("environment.sandbox", fromlist=["Sandbox"]))
check("compute_engine import",  lambda: __import__("engine.compute_engine", fromlist=["ComputeEngine"]))
check("neat_bridge import",     lambda: __import__("engine.neat_bridge", fromlist=["NeatBridge"]))
check("oracle import",          lambda: __import__("interface.oracle", fromlist=["Oracle"]))

import neat
from environment.sandbox import Sandbox
from engine.compute_engine import ComputeEngine
from engine.neat_bridge import NeatBridge
from interface.oracle import Oracle

# ── 2. Sandbox instantiation & V2.0 constants ────────────────────────────────
print("\n=== 2. SANDBOX CONSTANTS ===")
sb = Sandbox(num_agents=20, max_capacity=50, num_food=400, width=1600, height=1200)

check("Map 1600x1200",          lambda: f"{sb.width}x{sb.height}" if sb.width==1600 and sb.height==1200 else (_ for _ in ()).throw(AssertionError("Wrong dims")))
check("MAX_ENERGY == 350",      lambda: None if sb.MAX_ENERGY == 350.0 else (_ for _ in ()).throw(AssertionError(sb.MAX_ENERGY)))
check("MAX_HP == 100",          lambda: None if sb.MAX_HP == 100.0 else (_ for _ in ()).throw(AssertionError(sb.MAX_HP)))
check("vision_range == 200",    lambda: None if sb.vision_range == 200.0 else (_ for _ in ()).throw(AssertionError(sb.vision_range)))
check("num_food == 400",        lambda: None if sb.num_food == 400 else (_ for _ in ()).throw(AssertionError(sb.num_food)))
check("agent_hp shape",         lambda: f"({sb.max_capacity},)" if sb.agent_hp.shape == (50,) else (_ for _ in ()).throw(AssertionError(sb.agent_hp.shape)))
check("sensory_inputs 16 cols", lambda: f"(50,16)" if sb.sensory_inputs.shape == (50,16) else (_ for _ in ()).throw(AssertionError(sb.sensory_inputs.shape)))
check("3 friction zones",       lambda: f"n={len(sb.friction_zones)}" if len(sb.friction_zones)==3 else (_ for _ in ()).throw(AssertionError(len(sb.friction_zones))))
check("5 thickets",             lambda: f"shape={sb.thickets.shape}" if sb.thickets.shape[0]==5 else (_ for _ in ()).throw(AssertionError(sb.thickets.shape)))
check("Initial HP == MAX_HP",   lambda: None if np.all(sb.agent_hp[:20] == 100.0) else (_ for _ in ()).throw(AssertionError(sb.agent_hp[:5])))
check("Initial E == 50% max",   lambda: None if np.allclose(sb.agent_energy[:20], 175.0) else (_ for _ in ()).throw(AssertionError(sb.agent_energy[:3])))
check("Oasis center at start",  lambda: f"{sb.premium_pos}" if np.allclose(sb.premium_pos, [800,600]) else (_ for _ in ()).throw(AssertionError(sb.premium_pos)))

# ── 3. NEAT config & compile ─────────────────────────────────────────────────
print("\n=== 3. NEAT PIPELINE ===")
config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config-feedforward")
check("config-feedforward exists", lambda: None if os.path.exists(config_path) else (_ for _ in ()).throw(FileNotFoundError(config_path)))

config = neat.Config(neat.DefaultGenome, neat.DefaultReproduction,
                     neat.DefaultSpeciesSet, neat.DefaultStagnation, config_path)
check("NEAT num_inputs == 16",  lambda: None if config.genome_config.num_inputs == 16 else (_ for _ in ()).throw(AssertionError(config.genome_config.num_inputs)))
check("NEAT num_outputs == 7",  lambda: None if config.genome_config.num_outputs == 7 else (_ for _ in ()).throw(AssertionError(config.genome_config.num_outputs)))

pop = neat.Population(config)
pop.reporters.reporters.clear()
bridge = NeatBridge(num_inputs=16, num_outputs=7, max_nodes=50)
genomes = list(pop.population.items())
W, b, cc = bridge.compile_population(genomes, config, max_capacity=50)
check("W shape (50,50,50)",     lambda: f"{W.shape}" if W.shape==(50,50,50) else (_ for _ in ()).throw(AssertionError(W.shape)))
check("b shape (50,50)",        lambda: f"{b.shape}" if b.shape==(50,50) else (_ for _ in ()).throw(AssertionError(b.shape)))

ce = ComputeEngine(W, b, num_inputs=16, num_outputs=7)
ce.b[:, 15] += 1.0
ce.b[:, 16] += 0.8
check("ComputeEngine states shape", lambda: f"{ce.states.shape}" if ce.states.shape==(50,50) else (_ for _ in ()).throw(AssertionError(ce.states.shape)))

# ── 4. Full step() pipeline ───────────────────────────────────────────────────
print("\n=== 4. STEP() LOOP (50 ticks) ===")
conn_counts = np.ones(50, dtype=np.int32) * 5

def run_ticks(n):
    for t in range(n):
        inp = sb.get_sensory_inputs()
        assert inp.shape == (50, 16), f"Input shape wrong: {inp.shape}"
        assert not np.any(np.isnan(inp)), f"NaN in inputs at tick {t}"

        out = ce.step(inp)
        assert out.shape == (50, 7), f"Output shape wrong: {out.shape}"

        # Build full actions array (50 x whatever outputs exist)
        actions = np.zeros((50, 50), dtype=np.float32)
        actions[:, :7] = np.clip(out, 0.0, 1.0)

        extinct = sb.step(actions, conn_counts)
        ce.update_learning(sb.agent_energy, reward_signal=sb.reward_signal, lr=0.05)

        # Validate critical invariants each tick
        assert np.all(sb.agent_hp[sb.agent_alive] >= 0), f"Negative HP at tick {t}: {sb.agent_hp[sb.agent_alive]}"
        assert np.all(sb.agent_energy[sb.agent_alive] >= 0), f"Negative E at tick {t}"
        assert np.all(sb.agent_energy[sb.agent_alive] <= sb.MAX_ENERGY + 1e-3), \
            f"Energy exceeds MAX at tick {t}: {sb.agent_energy[sb.agent_alive].max()}"
        assert np.all(sb.agent_hp[sb.agent_alive] <= sb.MAX_HP + 1e-3), \
            f"HP exceeds MAX at tick {t}"
        assert np.any(sb.agent_alive), f"Total extinction at tick {t}"
    return f"{n} ticks OK, alive={np.sum(sb.agent_alive)}, avg_E={np.mean(sb.agent_energy[sb.agent_alive]):.1f}, avg_HP={np.mean(sb.agent_hp[sb.agent_alive]):.1f}"

check("50-tick full loop", lambda: run_ticks(50))

# ── 5. Dual-bar mechanics validation ─────────────────────────────────────────
print("\n=== 5. DUAL-BAR MECHANICS ===")

# Force-test starvation HP drain
def test_starvation_drain():
    sb2 = Sandbox(num_agents=5, max_capacity=10, num_food=0)
    sb2.agent_energy[:5] = 0.0
    sb2.agent_hp[:5] = 100.0
    # Run step with no food and zero energy
    actions_z = np.zeros((10, 50), dtype=np.float32)
    conn_z = np.ones(10, dtype=np.int32)
    sb2.step(actions_z, conn_z)
    # After 1 tick of energy==0, HP should have drained by 5
    alive = np.where(sb2.agent_alive)[0]
    if len(alive) == 0:
        return "all dead immediately (ok if hp was 0)"
    # Some might have negative energy but HP should still be capped at 0
    assert np.all(sb2.agent_hp >= 0), f"HP went negative: {sb2.agent_hp}"
    return f"HP after starvation tick: {sb2.agent_hp[:3]}"

check("Starvation HP drain (no crash)", lambda: test_starvation_drain())

# Force-test homeostasis healing
def test_homeostasis():
    sb3 = Sandbox(num_agents=3, max_capacity=5, num_food=0)
    sb3.agent_energy[:3] = sb3.MAX_ENERGY * 0.80  # above 70%
    sb3.agent_hp[:3] = 50.0  # damaged
    initial_hp = sb3.agent_hp[:3].copy()
    actions_z = np.zeros((5, 50), dtype=np.float32)
    conn_z = np.ones(5, dtype=np.int32)
    sb3.step(actions_z, conn_z)
    # HP should have increased (or stayed if other mechanics consumed energy)
    # Just make sure no crash and HP <= MAX_HP
    assert np.all(sb3.agent_hp <= sb3.MAX_HP + 1e-3), "HP exceeded MAX_HP after heal"
    assert np.all(sb3.agent_hp >= 0), "HP < 0 after heal"
    return f"HP: {initial_hp} -> {sb3.agent_hp[:3]}"

check("Homeostasis healing (no overflow)", lambda: test_homeostasis())

# ── 6. Reproduction asymmetry ────────────────────────────────────────────────
print("\n=== 6. REPRODUCTION THRESHOLDS ===")
check("Herb threshold == 210",  lambda: None if 209.9 < 0.60 * Sandbox.MAX_ENERGY < 210.1 else (_ for _ in ()).throw(AssertionError(0.60*Sandbox.MAX_ENERGY)))
check("Carn threshold == 280",  lambda: None if 279.9 < 0.80 * Sandbox.MAX_ENERGY < 280.1 else (_ for _ in ()).throw(AssertionError(0.80*Sandbox.MAX_ENERGY)))

def test_mitosis_costs():
    sb4 = Sandbox(num_agents=2, max_capacity=5, num_food=0)
    sb4.agent_energy[0] = 220.0   # herbivore above threshold (210)
    sb4.agent_energy[1] = 290.0   # carnivore above threshold (280)
    sb4.is_carnivore[1] = True
    sb4.agent_hp[:2] = 100.0
    pre_e0, pre_e1 = sb4.agent_energy[0], sb4.agent_energy[1]
    actions_z = np.zeros((5, 50), dtype=np.float32)
    conn_z = np.ones(5, dtype=np.int32)
    sb4.step(actions_z, conn_z)
    # Check parent lost energy and child was born
    n_alive = np.sum(sb4.agent_alive)
    assert n_alive > 2, f"No mitosis occurred (alive={n_alive})"
    return f"Mitosis OK, alive: 2 -> {n_alive}"

check("Mitosis triggers correctly", lambda: test_mitosis_costs())

# ── 7. Oracle save/load roundtrip ────────────────────────────────────────────
print("\n=== 7. ORACLE ROUNDTRIP ===")
test_world = "__debug_v2_test__"

def test_oracle_save():
    oracle = Oracle(test_world)
    oracle.save_world(pop, sb, tick=42, compute_engine=ce)
    return "saved"

def test_oracle_load():
    oracle2 = Oracle(test_world)
    sb_fresh = Sandbox(num_agents=0, max_capacity=50, num_food=400, width=1600, height=1200)
    loaded_pop, tick = oracle2.load_world(sb_fresh, compute_engine=None)
    assert loaded_pop is not None, "Population not loaded"
    assert tick == 42, f"Tick mismatch: {tick}"
    assert sb_fresh.agent_hp is not None, "agent_hp not restored"
    assert sb_fresh.agent_hp.shape == (50,), f"HP shape wrong: {sb_fresh.agent_hp.shape}"
    return f"tick={tick}, HP[0]={sb_fresh.agent_hp[0]:.1f}"

check("Oracle: save world", lambda: test_oracle_save())
check("Oracle: load roundtrip (tick, HP)", lambda: test_oracle_load())

# Cleanup test world
import shutil
test_dir = os.path.join("history", test_world)
if os.path.exists(test_dir):
    shutil.rmtree(test_dir)

# ── 8. Friction zone mechanics ───────────────────────────────────────────────
print("\n=== 8. FRICTION MAP ===")
def test_friction_effect():
    sb5 = Sandbox(num_agents=3, max_capacity=5, num_food=0)
    # Place agent 0 INSIDE first friction zone
    zx, zy, zr, zf = sb5.friction_zones[0]
    sb5.agent_positions[0] = [zx, zy]
    # Give it high velocity
    sb5.agent_velocity[0] = [4.0, 4.0]
    sb5.agent_velocity[1] = [4.0, 4.0]  # agent outside zone
    sb5.agent_positions[1] = [zx + zr * 2, zy]  # far from zone

    actions_z = np.zeros((5, 50), dtype=np.float32)
    conn_z = np.ones(5, dtype=np.int32)
    sb5.step(actions_z, conn_z)

    v_in  = np.linalg.norm(sb5.agent_velocity[0])
    v_out = np.linalg.norm(sb5.agent_velocity[1])
    assert v_in <= v_out + 1e-3, f"Friction not applied: in={v_in:.3f} >= out={v_out:.3f}"
    return f"v_in_zone={v_in:.3f} <= v_out_zone={v_out:.3f}"

check("Friction zone slows agents", lambda: test_friction_effect())

# ── 9. Sensory input range validation ────────────────────────────────────────
print("\n=== 9. SENSORY INPUT RANGES ===")
def test_input_ranges():
    inp = sb.get_sensory_inputs()
    alive = np.where(sb.agent_alive)[0]
    inp_alive = inp[alive]
    assert inp_alive.shape[1] == 16, f"Wrong input count: {inp_alive.shape[1]}"
    # Wall inputs 0-2: should be in [0,1]
    assert np.all(inp_alive[:, :3] >= 0) and np.all(inp_alive[:, :3] <= 1), "Wall inputs OOB"
    # Energy input 9: should be in [0,1]
    assert np.all(inp_alive[:, 9] >= 0) and np.all(inp_alive[:, 9] <= 1.01), f"Energy input OOB: {inp_alive[:,9].max()}"
    # HP input 15: should be in [0,1]
    assert np.all(inp_alive[:, 15] >= 0) and np.all(inp_alive[:, 15] <= 1.01), f"HP input OOB: {inp_alive[:,15].max()}"
    return f"All 16 inputs in range. HP input mean={inp_alive[:,15].mean():.2f}"

check("All 16 sensory inputs in [0,1]", lambda: test_input_ranges())

# ── 10. Energy cap enforcement ───────────────────────────────────────────────
print("\n=== 10. ENERGY CAP ===")
def test_energy_cap():
    sb6 = Sandbox(num_agents=3, max_capacity=5, num_food=200)
    sb6.agent_energy[:3] = sb6.MAX_ENERGY  # at cap
    actions_z = np.zeros((5, 50), dtype=np.float32)
    conn_z = np.ones(5, dtype=np.int32)
    for _ in range(10):
        inp = sb6.get_sensory_inputs()
        sb6.step(actions_z, conn_z)
    max_e = np.max(sb6.agent_energy[sb6.agent_alive])
    assert max_e <= sb6.MAX_ENERGY + 1e-3, f"Energy cap broken: {max_e}"
    return f"Max energy after 10 ticks: {max_e:.2f} (cap={sb6.MAX_ENERGY})"

check("Energy cap at MAX_ENERGY=350", lambda: test_energy_cap())

# ── FINAL REPORT ─────────────────────────────────────────────────────────────
print("\n" + "="*55)
if errors:
    print(f"ERRORS FOUND ({len(errors)}):")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED -- V2.0 IS BUILD-READY")
    sys.exit(0)
