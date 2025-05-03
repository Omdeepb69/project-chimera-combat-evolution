# main.py
# Main entry point for Project Chimera Combat Evolution.
# Initializes the Ursina engine, game world, player, NPCs, AI agent,
# and environment. Runs the main game loop.

import sys
import os
import numpy as np
import time
import random

try:
    from ursina import *
    from ursina.prefabs.first_person_controller import FirstPersonController
    from ursina.shaders import lit_with_shadows_shader
except ImportError as e:
    print(f"Error importing Ursina: {e}")
    print("Please ensure you have installed Ursina:")
    print("pip install ursina")
    sys.exit(1)

# --- RL/AI Imports ---
# Using Stable Baselines3 and Gymnasium
try:
    import gymnasium as gym
    from stable_baselines3 import PPO
    from stable_baselines3.common.env_checker import check_env
    from stable_baselines3.common.vec_env import DummyVecEnv
    from stable_baselines3.common.callbacks import BaseCallback
except ImportError as e:
    print(f"Error importing AI/RL libraries: {e}")
    print("Please ensure you have installed Gymnasium and Stable-Baselines3:")
    print("pip install gymnasium stable-baselines3[extra]")
    print("pip install tensorflow")  # or pip install torch torchvision torchaudio
    sys.exit(1)

# --- Project Module Imports ---
try:
    from player import Player
    from npc import EnemyNPC
    from combat_env import CombatEnvironment
    from ai_agent import CombatAgent
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print("Please ensure player.py, npc.py, combat_env.py, and ai_agent.py exist in the same directory.")
    sys.exit(1)

# --- Constants ---
AI_DECISION_INTERVAL = 0.25  # Seconds between AI decisions
ENABLE_SIMPLIFIED_TRAINING = False  # Set to True to enable periodic learning calls
TRAINING_INTERVAL_STEPS = 1000  # How many AI steps between learning calls
TRAINING_TIMESTEPS_PER_CALL = 500  # How many timesteps to train each time learn is called
MODEL_SAVE_PATH = "ppo_chimera_combat_agent"  # Base name for model files

# --- Global Game State ---
app = Ursina(title='Project Chimera Combat Evolution', borderless=False, fullscreen=False)

# Enable lighting
DirectionalLight(color=color.white, direction=(0.5, -0.65, -0.5), shadows=True)

# --- Environment Graphics ---
# Create a skybox for better visual environment
skybox = Sky()

# Create ground with better textures
ground = Entity(
    model='plane',
    scale=(100, 1, 100),
    color=color.rgb(50, 120, 50),  # Grass green color
    texture='white_cube',
    texture_scale=(100, 100),
    collider='box'
)

# Add environment objects
# Trees (using cubes instead of missing cylinders)
tree_positions = []
for _ in range(15):
    pos = (random.uniform(-45, 45), 0, random.uniform(-45, 45))
    # Ensure trees aren't too close to the player spawn
    if abs(pos[0]) < 8 and abs(pos[2]) < 8:
        continue
    tree_positions.append(pos)

trees = []
for pos in tree_positions:
    # Tree trunk (using cube instead of cylinder)
    trunk = Entity(
        model='cube',
        scale=(0.5, random.uniform(3, 5), 0.5),
        position=(pos[0], pos[1] + 1.5, pos[2]),
        color=color.rgb(80, 50, 30),  # Brown color
        texture='white_cube',
        shader=lit_with_shadows_shader
    )
    # Tree foliage
    foliage = Entity(
        model='sphere',
        scale=(2, 2, 2),
        position=(pos[0], trunk.y + trunk.scale_y * 0.8, pos[2]),
        color=color.rgb(20, 100, 20),  # Green color
        shader=lit_with_shadows_shader
    )
    trees.append((trunk, foliage))

# Cover objects with varied shapes and sizes
cover_types = [
    {'model': 'cube', 'color': color.rgb(110, 100, 80)},  # Light brown
    {'model': 'cube', 'color': color.rgb(60, 60, 90)},    # Blue-gray
    {'model': 'sphere', 'color': color.rgb(80, 80, 80)}   # Gray
]

cover_positions = [(10, 1, 10), (-10, 1, 15), (0, 1, 20), (15, 1, 5),
                   (8, 1, -10), (-12, 1, -15), (-20, 1, 0), (5, 1, 25),
                   (-5, 1, -20), (20, 1, -7), (-15, 1, 10)]

cover_objects = []
for pos in cover_positions:
    cover_type = random.choice(cover_types)
    scale = (random.uniform(1.5, 3), random.uniform(2, 4), random.uniform(1.5, 4))
    cover = Entity(
        model=cover_type['model'],
        scale=scale,
        position=pos,
        color=cover_type['color'],
        texture='white_cube',
        collider='box',
        shader=lit_with_shadows_shader
    )
    cover_objects.append(cover)

# Create a small terrain with hills
for i in range(20):
    x = random.uniform(-40, 40)
    z = random.uniform(-40, 40)
    # Avoid hills too close to player spawn
    if abs(x) < 10 and abs(z) < 10:
        continue
    hill = Entity(
        model='sphere',
        position=(x, -2.5, z),
        scale=(random.uniform(5, 12), random.uniform(2, 5), random.uniform(5, 12)),
        color=color.rgb(50, 120, 50),  # Green color
        texture='white_cube',
        collider='box'
    )

# --- Player Setup ---
player_entity = Player(position=(0, 1, 0), speed=5, jump_height=2)
player_entity.name = "Player"  # For debugging/identification

# --- NPC Setup ---
npc_list = []
npc_positions = [(5, 1, 15), (-8, 1, 10), (12, 1, -8)]
for i, pos in enumerate(npc_positions):
    npc = EnemyNPC(position=pos, player_ref=player_entity)
    npc.name = f"Chimera_Unit_{i+1:02d}"
    npc_list.append(npc)

# --- Environment Setup ---
combat_environment = CombatEnvironment(player=player_entity, npcs=npc_list)

# Wrap in a DummyVecEnv for SB3 compatibility
try:
    print("Setting up environment...")
    vec_env = DummyVecEnv([lambda: combat_environment])
except Exception as e:
    print(f"Error setting up environment: {e}")
    sys.exit(1)

# --- AI Agent Setup ---
combat_agent = CombatAgent(model_path=MODEL_SAVE_PATH, env=vec_env)  # Pass the VecEnv

# --- Game State Variables ---
current_observation = vec_env.reset()  # Get initial observation
last_ai_decision_time = time.time()
ai_step_counter = 0
is_game_paused = False

# --- HUD Setup ---
health_bar_bg = Entity(parent=camera.ui, model='quad', scale=(.3, .03), position=(.3, -.45), color=color.gray)
health_bar = Entity(parent=camera.ui, model='quad', scale=(.3, .03), position=(.3, -.45), color=color.red, origin_x=-.5)
health_text = Text(parent=camera.ui, text='Health: 100', position=(.17, -.45), color=color.white, scale=0.7)

ammo_text = Text(parent=camera.ui, text='Ammo: 30/90', position=(.72, -.45), color=color.white, scale=0.7)

# Custom crosshair (instead of using a texture)
crosshair_size = 0.01
crosshair_thickness = 0.002
crosshair_color = color.white

# Create crosshair elements
crosshair_vertical = Entity(parent=camera.ui, model='quad', color=crosshair_color, 
                           scale=(crosshair_thickness, crosshair_size))
crosshair_horizontal = Entity(parent=camera.ui, model='quad', color=crosshair_color, 
                             scale=(crosshair_size, crosshair_thickness))
crosshair_dot = Entity(parent=camera.ui, model='circle', color=crosshair_color, scale=crosshair_thickness)

# --- Help Text ---
help_text = Text(text="WASD=Move, Space=Jump\nLeft Click=Shoot, P=Pause\nEsc=Exit, F5=Save Model", y=0.45, origin=(0, 0), scale=1.0)
help_text.background = True
help_text.visible = True

# Custom sun entity (instead of using a texture)
sun = Entity(
    model='sphere',
    scale=20,
    position=(50, 40, -50),
    color=color.yellow,
)

# --- Main Game Loop (Ursina's update function) ---
def update():
    global last_ai_decision_time, current_observation, ai_step_counter, is_game_paused

    if is_game_paused:
        return

    # Update HUD
    health_percentage = player_entity.health / 100.0  # Assuming max health is 100
    health_bar.scale_x = max(0.01, health_percentage * 0.3)  # Min scale to avoid visual glitches
    health_text.text = f'Health: {int(player_entity.health)}'
    
    # You might need to implement these in your Player class
    if hasattr(player_entity, 'ammo') and hasattr(player_entity, 'reserve_ammo'):
        ammo_text.text = f'Ammo: {player_entity.ammo}/{player_entity.reserve_ammo}'

    # Simple pause toggle
    if held_keys['p'] and not hasattr(update, 'p_cooldown'):
        is_game_paused = not is_game_paused
        player_entity.enabled = not is_game_paused  # Disable player movement when paused
        mouse.locked = not is_game_paused
        print(f"Game {'Paused' if is_game_paused else 'Resumed'}")
        update.p_cooldown = True
        invoke(setattr, update, 'p_cooldown', False, delay=0.2)  # Better debounce

    current_time = time.time()

    # --- AI Decision Making ---
    if current_time - last_ai_decision_time >= AI_DECISION_INTERVAL:
        last_ai_decision_time = current_time

        if combat_agent.model and npc_list:  # Ensure model and NPCs exist
            # 1. Get Action from Agent
            action = combat_agent.predict(current_observation, deterministic=False)

            # 2. Step the Environment with the chosen action
            step_result = vec_env.step([action])

            # Handle both API versions (4 or 5 return values)
            if len(step_result) == 5:
                new_observation, rewards, terminated, truncated, info = step_result
                done = terminated[0] or truncated[0]
            else:
                new_observation, rewards, dones, info = step_result
                done = dones[0]
                terminated = [done]
                truncated = [False]

            # Update observation for the next prediction step
            current_observation = new_observation

            ai_step_counter += 1

            # Handle episode termination/truncation
            if done:
                print(f"Episode finished. Resetting environment. Reason: {'Terminated' if terminated[0] else 'Truncated'}")
                print(f"Final Info: {info[0]}")
                current_observation = vec_env.reset()
                ai_step_counter = 0  # Reset step counter for training interval

            # --- Simplified Real-time Training Trigger ---
            if ENABLE_SIMPLIFIED_TRAINING and ai_step_counter > 0 and ai_step_counter % TRAINING_INTERVAL_STEPS == 0:
                print(f"\n--- Triggering Simplified Training ---")
                combat_agent.learn(total_timesteps=TRAINING_TIMESTEPS_PER_CALL, reset_num_timesteps=False)
                print(f"--- Simplified Training Complete ---\n")

    # --- Player Input ---
    if held_keys['left mouse']:
        player_entity.shoot()

    # --- Check Game Over Conditions ---
    if player_entity.health <= 0:
        print("Game Over - Player Defeated")
        defeat_text = Text(text="GAME OVER", scale=3, origin=(0, 0), background=True, color=color.red)
        is_game_paused = True
        mouse.locked = False

    if not any(npc.health > 0 for npc in npc_list):
        print("Victory - All NPCs Defeated")
        victory_text = Text(text="VICTORY!", scale=3, origin=(0, 0), background=True, color=color.green)
        is_game_paused = True
        mouse.locked = False

# --- Input Handling for Saving/Exiting ---
def input(key):
    if key == 'escape':
        print("Exiting...")
        print("Attempting to save model before exit...")
        combat_agent.save_model()
        # Fixed quit method - use application.quit() instead of app.quit()
        application.quit()
    elif key == 'f5':  # Manual save key
        print("Manual save triggered...")
        combat_agent.save_model()
    elif key == 'f6':  # Manual train trigger
        if ENABLE_SIMPLIFIED_TRAINING:
            print("Manual simplified training triggered...")
            combat_agent.learn(total_timesteps=TRAINING_TIMESTEPS_PER_CALL, reset_num_timesteps=False)
            print("Manual training step complete.")
        else:
            print("Simplified training is disabled (ENABLE_SIMPLIFIED_TRAINING=False)")
    elif key == 'f1':  # Toggle help text
        help_text.visible = not help_text.visible

# --- Game Environment Effects ---
# Fog for atmosphere
scene.fog_color = color.rgb(150, 170, 190) 
scene.fog_density = 0.01

# --- Start the Ursina Application ---
print("Starting Project Chimera Combat Evolution...")
print("Controls: WASD=Move, Mouse=Look, Left Click=Shoot, P=Pause, Esc=Exit, F5=Save Model, F6=Manual Train Step")
app.run()