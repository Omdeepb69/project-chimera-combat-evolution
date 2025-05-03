# main.py
# Enhanced Project Chimera Combat Evolution
# Features improved maps, lighting, guns, and adaptive NPCs
#do a few maps for the game do some lighting add a gun do good npc models(all this programatically using ursina no external models) with guns that shoot at u and learn your stretergies and adatep to them by ml and all 

#give the full codes back

import sys
import os
import numpy as np
import time
import random
import math
from pathlib import Path

try:
    from ursina import *
    from ursina.prefabs.first_person_controller import FirstPersonController
    from ursina.shaders import lit_with_shadows_shader
    from ursina.curve import curve_animator
except ImportError as e:
    print(f"Error importing Ursina: {e}")
    print("Please ensure you have installed Ursina:")
    print("pip install ursina")
    sys.exit(1)

# --- RL/AI Imports ---
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
    from weapons import Weapon
    from map_generator import MapGenerator
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print("Please ensure all required modules exist in the same directory.")
    sys.exit(1)

# --- Constants ---
AI_DECISION_INTERVAL = 0.2  # Seconds between AI decisions
ENABLE_TRAINING = True  # Set to True to enable learning during gameplay
TRAINING_INTERVAL_STEPS = 500  # How many AI steps between learning calls
TRAINING_TIMESTEPS_PER_CALL = 200  # How many timesteps to train each time
MODEL_SAVE_PATH = "models/ppo_chimera_combat_agent"  # Base name for model files
MAP_ROTATION = ["urban", "forest", "industrial", "desert"]  # Available maps

# --- Global Game State ---
app = Ursina(title='Project Chimera Combat Evolution', borderless=False, fullscreen=False)
window.vsync = True  # Enable vsync for smoother visuals

# Ensure model directory exists
Path("models").mkdir(exist_ok=True)

# --- Environment Setup ---
current_map_type = random.choice(MAP_ROTATION)
map_generator = MapGenerator()
map_entities = []

# --- Create Game World ---
def create_game_world(map_type):
    global map_entities
    
    # Clear previous map if exists
    for entity in map_entities:
        destroy(entity)
    map_entities = []
    
    # Generate new map layout
    generated_map = map_generator.generate_map(map_type)
    map_entities = generated_map["entities"]
    
    # Set appropriate lighting based on map type
    setup_lighting(map_type)
    
    return generated_map["player_spawn"], generated_map["npc_spawns"]

def setup_lighting(map_type):
    # Clear previous lights
    for entity in scene.entities:
        if isinstance(entity, Light):
            destroy(entity)
    
    # Setup map-specific lighting
    if map_type == "urban":
        # City environment with cool street lights
        scene.fog_color = color.rgb(20, 20, 30)
        scene.fog_density = 0.02
        
        # Main directional light (moonlight)
        DirectionalLight(color=color.rgb(150, 170, 200), direction=(0.3, -0.8, 0.3), shadows=True)
        
        # Street lights
        for i in range(8):
            x = random.uniform(-40, 40)
            z = random.uniform(-40, 40)
            point_light = PointLight(color=color.rgb(255, 220, 150), position=(x, 6, z), shadows=True)
            point_light.intensity = 1.5
            map_entities.append(point_light)
            
    elif map_type == "forest":
        # Forest with natural daylight
        scene.fog_color = color.rgb(180, 200, 150)
        scene.fog_density = 0.015
        
        # Soft directional sunlight through trees
        DirectionalLight(color=color.rgb(220, 210, 170), direction=(0.5, -0.65, -0.5), shadows=True)
        
        # Ambient glow from mushrooms/plants
        for i in range(12):
            x = random.uniform(-40, 40)
            z = random.uniform(-40, 40)
            ambient_light = AmbientLight(color=color.rgb(100, 150, 100), position=(x, 0.5, z))
            ambient_light.intensity = 0.3
            map_entities.append(ambient_light)

    elif map_type == "industrial":
        # Industrial setting with harsh lights
        scene.fog_color = color.rgb(100, 100, 100)
        scene.fog_density = 0.03
        
        # Main overhead lights
        DirectionalLight(color=color.rgb(200, 200, 200), direction=(0, -0.9, 0), shadows=True)
        
        # Factory spotlights
        for i in range(6):
            x = random.uniform(-40, 40)
            z = random.uniform(-40, 40)
            spot_light = SpotLight(color=color.rgb(255, 240, 200), position=(x, 8, z), 
                                  direction=(0, -1, 0), shadows=True)
            spot_light.intensity = 2.0
            map_entities.append(spot_light)
            
    elif map_type == "desert":
        # Desert with intense sunlight
        scene.fog_color = color.rgb(230, 210, 180)
        scene.fog_density = 0.01
        
        # Harsh desert sun
        DirectionalLight(color=color.rgb(255, 240, 220), direction=(0.2, -0.9, 0.3), shadows=True)
        
        # Heat distortion effect (simulated with ambient light)
        ambient = AmbientLight(color=color.rgb(255, 200, 150))
        ambient.intensity = 0.4
        map_entities.append(ambient)

# --- Player Setup ---
player_spawn, npc_spawns = create_game_world(current_map_type)
player_entity = Player(position=player_spawn, speed=8, jump_height=3)
player_entity.name = "Player"

# --- Weapon Setup ---
player_weapon = Weapon(owner=player_entity, weapon_type="assault_rifle")
player_entity.equip_weapon(player_weapon)

# --- NPC Setup ---
npc_list = []
for i, pos in enumerate(npc_spawns):
    npc = EnemyNPC(position=pos, player_ref=player_entity)
    npc.name = f"Chimera_Unit_{i+1:02d}"
    
    # Give NPCs different weapons for variety
    weapon_types = ["assault_rifle", "shotgun", "sniper", "pistol"]
    npc_weapon = Weapon(owner=npc, weapon_type=random.choice(weapon_types))
    npc.equip_weapon(npc_weapon)
    
    npc_list.append(npc)

# --- Combat Environment Setup ---
combat_environment = CombatEnvironment(player=player_entity, npcs=npc_list)
vec_env = DummyVecEnv([lambda: combat_environment])

# --- AI Agent Setup ---
combat_agent = CombatAgent(model_path=MODEL_SAVE_PATH, env=vec_env)

# --- Game State Variables ---
current_observation = vec_env.reset()
last_ai_decision_time = time.time()
ai_step_counter = 0
is_game_paused = False
show_debug = False
current_map_index = MAP_ROTATION.index(current_map_type)

# --- HUD Setup ---
# Health bar and indicators
health_bar_bg = Entity(parent=camera.ui, model='quad', scale=(.3, .03), position=(.3, -.45), color=color.gray)
health_bar = Entity(parent=camera.ui, model='quad', scale=(.3, .03), position=(.3, -.45), color=color.red, origin_x=-.5)
health_text = Text(parent=camera.ui, text='Health: 100', position=(.17, -.45), color=color.white, scale=0.7)

# Ammo counter
ammo_bg = Entity(parent=camera.ui, model='quad', scale=(.15, .03), position=(.72, -.45), color=color.gray.tint(-.2))
ammo_text = Text(parent=camera.ui, text='30/90', position=(.72, -.45), scale=0.7, origin=(0,0))

# Weapon name indicator
weapon_text = Text(parent=camera.ui, text='Assault Rifle', position=(.72, -.4), scale=0.6, origin=(0,0), color=color.rgba(255,255,255,150))

# Custom crosshair
crosshair_size = 0.01
crosshair_thickness = 0.002
crosshair_color = color.white

crosshair_vertical = Entity(parent=camera.ui, model='quad', color=crosshair_color, 
                           scale=(crosshair_thickness, crosshair_size))
crosshair_horizontal = Entity(parent=camera.ui, model='quad', color=crosshair_color, 
                             scale=(crosshair_size, crosshair_thickness))
crosshair_dot = Entity(parent=camera.ui, model='circle', color=crosshair_color, scale=crosshair_thickness)

# Enemy indicator (shows when enemies are in range)
enemy_indicator = Text(parent=camera.ui, text='', position=(0, .4), origin=(0,0), color=color.red, scale=0.8)
enemy_indicator.visible = False

# Map name
map_name_text = Text(parent=camera.ui, text=f"Map: {current_map_type.capitalize()}", position=(-.75, .45), origin=(-0.5,0), color=color.white, scale=0.7)

# Help text
help_text = Text(
    text="WASD=Move, Space=Jump, Shift=Sprint\nLeft Click=Shoot, R=Reload, P=Pause\nM=Change Map, F1=Toggle Help, Esc=Exit", 
    y=0.45, 
    origin=(0, 0), 
    scale=1.0
)
help_text.background = True
help_text.visible = True

# Debug info panel
debug_panel = Text(
    text="", 
    position=(-.75, .35),
    origin=(-0.5, 0),
    scale=0.6
)
debug_panel.visible = False

# --- Combat Effects ---
def create_muzzle_flash(position, direction):
    # Create muzzle flash effect
    flash = Entity(
        model='sphere',
        scale=0.5,
        position=position + direction * 2,
        color=color.yellow,
        billboard=True
    )
    # Animate flash
    flash.animate_scale((0,0,0), duration=0.1)
    flash.animate_color(color.clear, duration=0.1)
    destroy(flash, delay=0.1)
    
    # Add point light for flash illumination
    light = PointLight(
        color=color.yellow, 
        position=position + direction * 2,
        shadows=False
    )
    light.intensity = 2
    destroy(light, delay=0.1)

def create_impact_effect(position, normal):
    # Create bullet impact particles
    for _ in range(10):
        particle = Entity(
            model='sphere',
            scale=0.1,
            position=position,
            color=color.gray,
            billboard=True
        )
        # Randomize particle direction based on impact normal
        rand_dir = Vec3(
            normal.x + random.uniform(-0.5, 0.5),
            normal.y + random.uniform(-0.5, 0.5),
            normal.z + random.uniform(-0.5, 0.5)
        ).normalized()
        
        # Animate particles
        particle.animate_position(
            position + rand_dir * random.uniform(0.5, 1.5),
            duration=random.uniform(0.2, 0.5)
        )
        particle.animate_scale(0, duration=random.uniform(0.2, 0.5))
        destroy(particle, delay=0.5)

# --- Map Change Function ---
def change_map():
    global current_map_type, current_map_index, player_entity, npc_list, current_observation
    
    # Change to next map in rotation
    current_map_index = (current_map_index + 1) % len(MAP_ROTATION)
    current_map_type = MAP_ROTATION[current_map_index]
    
    # Generate new map
    player_spawn, npc_spawns = create_game_world(current_map_type)
    
    # Reset player position
    player_entity.world_position = player_spawn
    player_entity.health = 100
    
    # Reset NPCs
    for npc in npc_list:
        destroy(npc)
    
    npc_list = []
    for i, pos in enumerate(npc_spawns):
        npc = EnemyNPC(position=pos, player_ref=player_entity)
        npc.name = f"Chimera_Unit_{i+1:02d}"
        
        # Give NPCs different weapons for variety
        weapon_types = ["assault_rifle", "shotgun", "sniper", "pistol"]
        npc_weapon = Weapon(owner=npc, weapon_type=random.choice(weapon_types))
        npc.equip_weapon(npc_weapon)
        
        npc_list.append(npc)
    
    # Update combat environment
    combat_environment.npcs = npc_list
    
    # Reset observation
    current_observation = vec_env.reset()
    
    # Update map name text
    map_name_text.text = f"Map: {current_map_type.capitalize()}"
    
    print(f"Changed map to: {current_map_type}")

# --- Main Game Loop ---
def update():
    global last_ai_decision_time, current_observation, ai_step_counter, is_game_paused
    
    if is_game_paused:
        return
    
    # Update HUD
    health_percentage = player_entity.health / 100.0
    health_bar.scale_x = max(0.01, health_percentage * 0.3)
    health_text.text = f'Health: {int(player_entity.health)}'
    
    # Update weapon HUD
    if player_entity.current_weapon:
        weapon = player_entity.current_weapon
        ammo_text.text = f'{weapon.current_ammo}/{weapon.reserve_ammo}'
        weapon_text.text = weapon.weapon_name
    
    # Show enemy indicator when enemies are nearby
    nearby_enemies = [npc for npc in npc_list if npc.health > 0 and 
                     (npc.world_position - player_entity.world_position).length() < 20]
    if nearby_enemies:
        enemy_indicator.visible = True
        enemy_indicator.text = f"⚠ {len(nearby_enemies)} ENEMIES NEARBY ⚠"
    else:
        enemy_indicator.visible = False
    
    # Update debug panel if enabled
    if show_debug:
        debug_panel.visible = True
        debug_panel.text = (
            f"FPS: {int(1/time.dt)}\n"
            f"Player Pos: {player_entity.world_position.rounded()}\n"
            f"Active NPCs: {sum(1 for npc in npc_list if npc.health > 0)}\n"
            f"AI Steps: {ai_step_counter}\n"
            f"ML Enabled: {ENABLE_TRAINING}"
        )
    else:
        debug_panel.visible = False
    
    # Toggle pause with P
    if held_keys['p'] and not hasattr(update, 'p_cooldown'):
        is_game_paused = not is_game_paused
        player_entity.enabled = not is_game_paused
        mouse.locked = not is_game_paused
        print(f"Game {'Paused' if is_game_paused else 'Resumed'}")
        update.p_cooldown = True
        invoke(setattr, update, 'p_cooldown', False, delay=0.2)
    
    current_time = time.time()
    
    # --- AI Decision Making ---
    if current_time - last_ai_decision_time >= AI_DECISION_INTERVAL:
        last_ai_decision_time = current_time
        
        if combat_agent.model and npc_list:
            # Get action from agent
            action = combat_agent.predict(current_observation, deterministic=False)
            
            # Step environment with chosen action
            step_result = vec_env.step([action])
            
            if len(step_result) == 5:
                new_observation, rewards, terminated, truncated, info = step_result
                done = terminated[0] or truncated[0]
            else:
                new_observation, rewards, dones, info = step_result
                done = dones[0]
                terminated = [done]
                truncated = [False]
            
            # Update observation for next step
            current_observation = new_observation
            
            ai_step_counter += 1
            
            # Handle episode end
            if done:
                print(f"Episode finished. Reason: {'Terminated' if terminated[0] else 'Truncated'}")
                print(f"Final Info: {info[0]}")
                current_observation = vec_env.reset()
                ai_step_counter = 0
            
            # Training during gameplay
            if ENABLE_TRAINING and ai_step_counter > 0 and ai_step_counter % TRAINING_INTERVAL_STEPS == 0:
                print(f"\n--- Training in progress... ---")
                combat_agent.learn(total_timesteps=TRAINING_TIMESTEPS_PER_CALL, reset_num_timesteps=False)
                print(f"--- Training complete ---\n")
    
    # --- Player Input ---
    if held_keys['left mouse'] and player_entity.current_weapon:
        hit_info = player_entity.shoot()
        if hit_info and hit_info.hit:
            create_impact_effect(hit_info.world_point, hit_info.world_normal)
    
    if held_keys['r'] and player_entity.current_weapon:
        player_entity.current_weapon.reload()
    
    # --- Game Over Conditions ---
    if player_entity.health <= 0:
        defeat_text = Text(text="GAME OVER", scale=3, origin=(0, 0), background=True, color=color.red)
        restart_text = Text(text="Press 'R' to Restart", scale=1.5, y=-0.1, origin=(0, 0), background=True)
        is_game_paused = True
        mouse.locked = False
    
    if all(npc.health <= 0 for npc in npc_list):
        victory_text = Text(text="VICTORY!", scale=3, origin=(0, 0), background=True, color=color.green)
        next_text = Text(text="Press 'M' for Next Map", scale=1.5, y=-0.1, origin=(0, 0), background=True)
        is_game_paused = True
        mouse.locked = False

# --- Input Handling ---
def input(key):
    global show_debug
    
    if key == 'escape':
        print("Saving model and exiting...")
        combat_agent.save_model()
        application.quit()
    
    elif key == 'f1':  # Toggle help text
        help_text.visible = not help_text.visible
    
    elif key == 'f3':  # Toggle debug info
        show_debug = not show_debug
    
    elif key == 'f5':  # Manual save
        print("Manual save triggered...")
        combat_agent.save_model()
        
    elif key == 'm':  # Change map
        if not is_game_paused:
            change_map()
    
    elif key == 'r' and player_entity.health <= 0:  # Restart on death
        # Reset player
        player_entity.health = 100
        player_entity.world_position = player_spawn
        
        # Reset NPCs
        for npc in npc_list:
            if npc.health <= 0:
                npc.health = 100
        
        # Clear game over text
        for entity in scene.entities:
            if isinstance(entity, Text) and (entity.text == "GAME OVER" or entity.text == "Press 'R' to Restart"):
                destroy(entity)
        
        # Resume game
        is_game_paused = False
        mouse.locked = True
        player_entity.enabled = True

# --- Start Game ---
print("Starting Enhanced Project Chimera Combat Evolution...")
print(f"Current Map: {current_map_type}")
app.run()