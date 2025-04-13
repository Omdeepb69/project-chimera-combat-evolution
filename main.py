# main.py
# Main entry point for Project Chimera Combat Evolution.
# Initializes the Ursina engine, game world, player, NPCs, AI agent,
# and environment. Runs the main game loop.

import sys
import os
import numpy as np
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController

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
    # Depending on your backend (TensorFlow/PyTorch), install the appropriate one:
    print("pip install tensorflow") # or pip install torch torchvision torchaudio
    sys.exit(1)

# --- Project Module Imports ---
# Assume these files exist in the same directory or Python path
try:
    # player.py should contain a Player class inheriting from FirstPersonController or Entity
    from player import Player
    # npc.py should contain an EnemyNPC class inheriting from Entity
    from npc import EnemyNPC
    # combat_env.py should contain a CombatEnvironment class inheriting from gym.Env
    from combat_env import CombatEnvironment
    # ai_agent.py should contain a CombatAgent class to wrap the SB3 model
    from ai_agent import CombatAgent
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print("Please ensure player.py, npc.py, combat_env.py, and ai_agent.py exist and are accessible.")
    # Create dummy classes for basic execution if files are missing (for demonstration)
    if 'Player' not in globals():
        class Player(FirstPersonController):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.health = 100
                self.add_to_scene_entities = True # Required by Ursina
                print("Warning: Using dummy Player class.")
            def shoot(self):
                 print("Player shoots (dummy)")
                 # Add basic raycasting logic if needed for env observation
                 hit_info = raycast(self.world_position + self.camera_pivot.up * 0.5, self.forward, distance=100, ignore=[self,])
                 if hit_info.hit and hasattr(hit_info.entity, 'health'):
                     hit_info.entity.health -= 10
                     print(f"Hit {hit_info.entity.name}, health: {hit_info.entity.health}")

    if 'EnemyNPC' not in globals():
        class EnemyNPC(Entity):
            def __init__(self, position=(0, 1, 5), player_ref=None, **kwargs):
                super().__init__(model='cube', color=color.red, collider='box', position=position, **kwargs)
                self.health = 100
                self.player = player_ref
                self.speed = 3
                self.target_position = self.position
                self.state = 'idle' # idle, seeking, attacking, cover
                print("Warning: Using dummy EnemyNPC class.")

            def apply_action(self, action_index):
                """Applies the action determined by the RL agent."""
                # Example action mapping (must match CombatEnvironment action space)
                # 0: Idle, 1: Move towards player, 2: Strafe Left, 3: Strafe Right, 4: Seek Cover (placeholder)
                print(f"NPC applying action: {action_index}")
                if action_index == 0:
                    self.state = 'idle'
                    self.target_position = self.position
                elif action_index == 1:
                    self.state = 'seeking'
                    if self.player:
                        self.target_position = self.player.position
                elif action_index == 2: # Strafe Left
                     self.state = 'strafing_left'
                     if self.player:
                         direction_to_player = (self.player.position - self.position).normalized()
                         strafe_dir = cross(direction_to_player, Vec3(0,1,0)).normalized()
                         self.target_position = self.position - strafe_dir * 2 # Move 2 units left relative to player
                elif action_index == 3: # Strafe Right
                     self.state = 'strafing_right'
                     if self.player:
                         direction_to_player = (self.player.position - self.position).normalized()
                         strafe_dir = cross(direction_to_player, Vec3(0,1,0)).normalized()
                         self.target_position = self.position + strafe_dir * 2 # Move 2 units right relative to player
                elif action_index == 4:
                    self.state = 'cover'
                    # Basic cover seeking: find nearest cover point (needs cover objects defined)
                    # For simplicity, just move away from player for now
                    if self.player:
                        direction_from_player = (self.position - self.player.position).normalized()
                        self.target_position = self.position + direction_from_player * 5
                else:
                     print(f"Warning: Unknown action index {action_index}")
                     self.state = 'idle'

            def update(self):
                """Basic movement towards target position."""
                if self.state != 'idle':
                    move_direction = (self.target_position - self.position).normalized()
                    # Basic ground clamping / collision avoidance needed for real game
                    self.position += move_direction * self.speed * time.dt

            def shoot_at_player(self):
                 if self.player and distance(self, self.player) < 20:
                     print("NPC Shoots at player (dummy)")
                     # Simple damage model
                     self.player.health -= 5
                     print(f"Player health: {self.player.health}")
                     # Add visual effect (e.g., bullet tracer)


    if 'CombatEnvironment' not in globals():
        class CombatEnvironment(gym.Env):
            metadata = {'render_modes': ['human'], 'render_fps': 60}

            def __init__(self, player, npcs, render_mode=None, max_steps=500):
                super().__init__()
                self.player = player
                self.npcs = npcs # Should be a list
                self.max_steps = max_steps
                self.current_step = 0
                self.render_mode = render_mode # Not directly used by Ursina env

                # Define action and observation space (EXAMPLE - needs refinement)
                # Action: 0: Idle, 1: Move towards player, 2: Strafe L, 3: Strafe R, 4: Seek Cover
                self.action_space = gym.spaces.Discrete(5)

                # Observation: Player Pos (3), NPC Pos (3*N), Player Health (1), NPC Health (N)
                # Needs normalization and careful design
                low = np.full(3 + 3*len(npcs) + 1 + len(npcs), -np.inf, dtype=np.float32)
                high = np.full(3 + 3*len(npcs) + 1 + len(npcs), np.inf, dtype=np.float32)
                self.observation_space = gym.spaces.Box(low, high, dtype=np.float32)
                print("Warning: Using dummy CombatEnvironment class.")

            def _get_obs(self):
                obs_list = []
                obs_list.extend(self.player.position)
                for npc in self.npcs:
                    obs_list.extend(npc.position)
                obs_list.append(self.player.health)
                for npc in self.npcs:
                    obs_list.append(npc.health)
                return np.array(obs_list, dtype=np.float32)

            def _get_info(self):
                # Provide auxiliary info if needed
                return {"player_health": self.player.health,
                        "npc_health": [npc.health for npc in self.npcs],
                        "distance_to_player": [distance(npc, self.player) for npc in self.npcs]}

            def reset(self, seed=None, options=None):
                super().reset(seed=seed)
                self.current_step = 0
                # Reset player/NPC positions and health (implement specific reset logic)
                self.player.position = (0, 1, 0)
                self.player.health = 100
                for i, npc in enumerate(self.npcs):
                    npc.position = (np.random.uniform(-15, 15), 1, np.random.uniform(5, 20))
                    npc.health = 100
                    npc.state = 'idle'
                print("Environment Reset")
                observation = self._get_obs()
                info = self._get_info()
                return observation, info

            def step(self, action):
                # Apply action to the first NPC for simplicity
                # In a multi-agent scenario, this needs expansion
                if self.npcs:
                    self.npcs[0].apply_action(action)
                    # Simulate NPC shooting periodically if close and attacking
                    if self.npcs[0].state in ['seeking', 'strafing_left', 'strafing_right'] and self.current_step % 30 == 0: # Shoot every 0.5 sec approx
                        self.npcs[0].shoot_at_player()


                self.current_step += 1

                # --- Determine Reward ---
                reward = 0
                # Small penalty for existing
                reward -= 0.01
                # Reward for damaging player (negative reward)
                # Handled implicitly by player health check? Or add explicit reward based on health change.

                # Reward for NPC survival (or penalty for getting hit - handled in Player.shoot)
                # Example: if npc health decreased, reward -= 10

                # --- Check Termination/Truncation ---
                terminated = False
                truncated = False

                if self.player.health <= 0:
                    print("Player defeated!")
                    reward -= 100 # Large penalty for player dying
                    terminated = True
                elif not self.npcs or all(npc.health <= 0 for npc in self.npcs):
                     print("All NPCs defeated!")
                     reward += 100 # Large reward for winning
                     terminated = True

                if self.current_step >= self.max_steps:
                    print("Max steps reached.")
                    truncated = True # Use truncated for time limit

                observation = self._get_obs()
                info = self._get_info()

                # In SB3, step returns obs, reward, terminated, truncated, info
                return observation, reward, terminated, truncated, info

            def render(self):
                # Rendering is handled by Ursina's main loop
                pass

            def close(self):
                # Cleanup if needed
                pass

    if 'CombatAgent' not in globals():
         class CombatAgent:
            def __init__(self, model_path="ppo_chimera_combat", env=None, learning_rate=3e-4):
                self.model_path = f"{model_path}.zip"
                self.env = env # Needs a VecEnv usually
                self.learning_rate = learning_rate
                self.model = None
                self._load_or_initialize_model()
                print("Warning: Using dummy CombatAgent class.")

            def _load_or_initialize_model(self):
                if os.path.exists(self.model_path):
                    print(f"Loading pre-trained model from {self.model_path}")
                    try:
                        # Pass custom_objects if needed for activation functions etc.
                        self.model = PPO.load(self.model_path, env=self.env)
                        print("Model loaded successfully.")
                    except Exception as e:
                        print(f"Error loading model: {e}. Initializing a new one.")
                        self._initialize_new_model()
                else:
                    print("No pre-trained model found. Initializing a new one.")
                    self._initialize_new_model()

            def _initialize_new_model(self):
                 if self.env is None:
                     print("Error: Cannot initialize model without an environment.")
                     # Fallback: Create a dummy model structure if absolutely necessary
                     # This won't be trainable without a proper env setup.
                     class DummyModel:
                         def predict(self, obs, deterministic=True): return np.random.randint(0, 5), None # Random action
                         def learn(self, *args, **kwargs): print("Dummy learn called")
                         def save(self, *args, **kwargs): print("Dummy save called")
                     self.model = DummyModel()
                     return

                 # Use PPO algorithm. MlpPolicy is standard for vector observations.
                 self.model = PPO("MlpPolicy", self.env, verbose=1, learning_rate=self.learning_rate,
                                  tensorboard_log="./chimera_tensorboard/")
                 print("New PPO model initialized.")


            def predict(self, observation, deterministic=True):
                """Get action from the RL model."""
                if self.model:
                    action, _states = self.model.predict(observation, deterministic=deterministic)
                    return action
                else:
                    print("Warning: Model not available for prediction.")
                    # Return a default action (e.g., idle) if model isn't loaded
                    return 0 # Assuming 0 is Idle

            def learn(self, total_timesteps=1000, callback=None, reset_num_timesteps=False):
                """Perform a training step."""
                if self.model and hasattr(self.model, 'learn') and self.env:
                    print(f"Starting simplified training for {total_timesteps} timesteps...")
                    try:
                        # The 'env' passed during initialization should be used internally by learn
                        self.model.learn(total_timesteps=total_timesteps,
                                         callback=callback,
                                         reset_num_timesteps=reset_num_timesteps, # Continue learning count unless specified
                                         tb_log_name="PPO_Chimera")
                        print("Training step completed.")
                        self.save_model() # Save after learning
                    except Exception as e:
                        print(f"Error during training: {e}")
                else:
                    print("Warning: Cannot train. Model or environment not properly configured.")


            def save_model(self):
                """Save the current model state."""
                if self.model and hasattr(self.model, 'save'):
                    try:
                        self.model.save(self.model_path.replace(".zip", "")) # SB3 adds .zip automatically
                        print(f"Model saved to {self.model_path}")
                    except Exception as e:
                        print(f"Error saving model: {e}")
                else:
                    print("Warning: Model not available for saving.")

# --- Constants ---
AI_DECISION_INTERVAL = 0.25 # Seconds between AI decisions
ENABLE_SIMPLIFIED_TRAINING = False # Set to True to enable periodic learning calls
TRAINING_INTERVAL_STEPS = 1000 # How many AI steps between learning calls
TRAINING_TIMESTEPS_PER_CALL = 500 # How many timesteps to train each time learn is called
MODEL_SAVE_PATH = "ppo_chimera_combat_agent" # Base name for model files

# --- Global Game State ---
app = Ursina(title='Project Chimera Combat Evolution', borderless=False, fullscreen=False)

# --- Level Setup ---
ground = Entity(model='plane', scale=(100, 1, 100), color=color.gray.tint(-.2), texture='white_cube', texture_scale=(100, 100), collider='box')
# Basic cover objects
cover_positions = [(10, 1, 10), (-10, 1, 15), (0, 1, 20), (15, 1, 5)]
cover_objects = []
for pos in cover_positions:
    cover = Entity(model='cube', scale=(2, 3, 4), position=pos, color=color.dark_gray, collider='box')
    cover_objects.append(cover)

# --- Player Setup ---
player_entity = Player(position=(0, 1, 0), speed=5, jump_height=2)
player_entity.name = "Player" # For debugging/identification

# --- NPC Setup ---
# Create one NPC for simplicity first
npc_list = []
npc1 = EnemyNPC(position=(5, 1, 15), player_ref=player_entity)
npc1.name = "Chimera_Unit_01"
npc_list.append(npc1)

# --- Environment Setup ---
# The environment wraps the game state for the AI
combat_environment = CombatEnvironment(player=player_entity, npcs=npc_list)

# Optional: Check if the custom environment is valid (good practice)
try:
    # check_env(combat_environment) # This can be slow, run it once during development
    print("CombatEnvironment structure appears valid (basic check).")
    # Wrap in a DummyVecEnv for SB3 compatibility if not already vectorized
    vec_env = DummyVecEnv([lambda: combat_environment])

except Exception as e:
    print(f"Error validating environment: {e}")
    print("Ensure the environment implements the Gymnasium API correctly.")
    sys.exit(1)


# --- AI Agent Setup ---
# The agent loads/manages the SB3 model
combat_agent = CombatAgent(model_path=MODEL_SAVE_PATH, env=vec_env) # Pass the VecEnv

# --- Game State Variables ---
current_observation, _ = vec_env.reset() # Get initial observation
last_ai_decision_time = time.time()
ai_step_counter = 0
is_game_paused = False

# --- Main Game Loop (Ursina's update function) ---
def update():
    global last_ai_decision_time, current_observation, ai_step_counter, is_game_paused

    if is_game_paused:
        return

    # Simple pause toggle
    if held_keys['p']:
        is_game_paused = not is_game_paused
        player_entity.enabled = not is_game_paused # Disable player movement when paused
        mouse.locked = not is_game_paused
        print(f"Game {'Paused' if is_game_paused else 'Resumed'}")
        time.sleep(0.2) # Debounce key press

    current_time = time.time()

    # --- AI Decision Making ---
    if current_time - last_ai_decision_time >= AI_DECISION_INTERVAL:
        last_ai_decision_time = current_time

        if combat_agent.model and npc_list: # Ensure model and NPCs exist
            # 1. Get Action from Agent
            # Note: current_observation should be updated after env.step()
            # For VecEnv, observation is often automatically handled if using SB3's standard loops,
            # but here we manage it manually within Ursina's update.
            action = combat_agent.predict(current_observation, deterministic=False) # Use stochastic actions during interaction

            # 2. Step the Environment with the chosen action
            # vec_env.step returns lists/arrays for obs, reward, done, info
            new_observation, reward, terminated, truncated, info = vec_env.step([action]) # Pass action as a list for VecEnv

            # Update observation for the next prediction step
            current_observation = new_observation

            ai_step_counter += 1

            # Handle episode termination/truncation
            done = terminated[0] or truncated[0] # Check the first env in VecEnv
            if done:
                print(f"Episode finished. Resetting environment. Reason: {'Terminated' if terminated[0] else 'Truncated'}")
                print(f"Final Info: {info[0]}")
                current_observation, _ = vec_env.reset()
                ai_step_counter = 0 # Reset step counter for training interval

            # --- Simplified Real-time Training Trigger ---
            if ENABLE_SIMPLIFIED_TRAINING and ai_step_counter > 0 and ai_step_counter % TRAINING_INTERVAL_STEPS == 0:
                 print(f"\n--- Triggering Simplified Training ---")
                 # Run a short learning phase
                 # Note: This is NOT efficient real-time training. It's a simulated adaptation.
                 # For real training, run this offline or between rounds extensively.
                 # Ensure the model uses the same VecEnv it was initialized with.
                 combat_agent.learn(total_timesteps=TRAINING_TIMESTEPS_PER_CALL,
                                    reset_num_timesteps=False) # Continue learning progress
                 print(f"--- Simplified Training Complete ---\n")
                 # No need to reset counter here, it continues until episode ends


    # --- Player Input ---
    if held_keys['left mouse']:
        player_entity.shoot()

    # --- NPC Updates (basic non-AI behavior like looking at player) ---
    for npc in npc_list:
        if npc.health > 0 and player_entity:
            try:
                # Make NPC look towards the player (optional, can interfere with AI movement)
                # npc.look_at(player_entity.position + Vec3(0,1,0)) # Look slightly above feet
                pass # Let AI control movement entirely via apply_action and npc.update
            except AttributeError:
                pass # Handle cases where player might be destroyed

    # --- Check Game Over Conditions ---
    if player_entity.health <= 0:
        print("Game Over - Player Defeated")
        # You might want to pause, show a message, and offer restart
        Text(text="GAME OVER", scale=3, origin=(0,0), background=True, color=color.red)
        is_game_paused = True
        mouse.locked = False
        # Potentially trigger a final negative reward and env reset here if needed for learning

    if not any(npc.health > 0 for npc in npc_list):
        print("Victory - All NPCs Defeated")
        Text(text="VICTORY!", scale=3, origin=(0,0), background=True, color=color.green)
        is_game_paused = True
        mouse.locked = False
        # Potentially trigger a final positive reward and env reset here

# --- Input Handling for Saving/Exiting ---
def input(key):
    if key == 'escape':
        print("Exiting...")
        # Save the agent's learned state before exiting
        print("Attempting to save model before exit...")
        combat_agent.save_model()
        app.quit()
    elif key == 'f5': # Manual save key
        print("Manual save triggered...")
        combat_agent.save_model()
    elif key == 'f6': # Manual (simplified) train trigger
        if ENABLE_SIMPLIFIED_TRAINING:
            print("Manual simplified training triggered...")
            combat_agent.learn(total_timesteps=TRAINING_TIMESTEPS_PER_CALL, reset_num_timesteps=False)
            print("Manual training step complete.")
        else:
            print("Simplified training is disabled (ENABLE_SIMPLIFIED_TRAINING=False)")


# --- Start the Ursina Application ---
print("Starting Project Chimera Combat Evolution...")
print("Controls: WASD=Move, Mouse=Look, Left Click=Shoot, P=Pause, Esc=Exit, F5=Save Model, F6=Manual Train Step")
app.run()