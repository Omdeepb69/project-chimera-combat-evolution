```python
# combat_env.py

"""
Defines the Reinforcement Learning environment for Project Chimera Combat Evolution.

This environment uses the Gymnasium interface to bridge the Ursina game state
with an RL agent (e.g., from Stable Baselines3).
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import random

# Try importing Ursina specific types for type hinting if available
# This might require careful handling depending on the project structure
try:
    from ursina import Entity, Vec3, raycast, distance, time, lerp, clamp
    # Assuming Player and NPC classes exist in these modules
    from player import Player
    from npc import NPC
except ImportError:
    print("Warning: Ursina or project modules not found. Using placeholder types.")
    # Define placeholder types if Ursina isn't installed or modules aren't found
    # This allows type hinting to function without breaking the code structure.
    class Entity: pass
    class Vec3: pass
    class Player(Entity):
        health: float = 100.0
        max_health: float = 100.0
        position: Vec3 = Vec3(0,0,0)
        visible: bool = True # Placeholder
    class NPC(Entity):
        health: float = 100.0
        max_health: float = 100.0
        position: Vec3 = Vec3(0,0,0)
        rotation_y: float = 0.0
        forward: Vec3 = Vec3(0,0,1)
        ammo: int = 30
        max_ammo: int = 30
        last_damage_time: float = 0.0
        last_shot_time: float = 0.0
        shoot_cooldown: float = 0.2
        move_speed: float = 5.0
        turn_speed: float = 90.0

        def take_damage(self, amount: float):
            self.health -= amount
            self.health = max(0, self.health)
            self.last_damage_time = time.time() if 'time' in globals() else 0.0 # Use game time if available

        def shoot(self, target_pos: Vec3):
            # Placeholder: Actual shooting logic would be here
            # print(f"NPC {self.name} shoots towards {target_pos}")
            self.ammo -= 1
            self.last_shot_time = time.time() if 'time' in globals() else 0.0

        def move(self, direction: Vec3, speed_multiplier: float = 1.0):
            # Placeholder: Actual movement logic would be here
            # self.position += direction * self.move_speed * speed_multiplier * time.dt
            pass

        def turn(self, amount: float):
            # Placeholder: Actual turning logic would be here
            # self.rotation_y += amount * self.turn_speed * time.dt
            pass

        def reset_state(self, position: Vec3, health: float, ammo: int):
            self.position = position
            self.health = health
            self.max_health = health # Assume max health is reset health
            self.ammo = ammo
            self.max_ammo = ammo # Assume max ammo is reset ammo
            self.rotation_y = random.uniform(0, 360)
            self.last_damage_time = 0.0
            self.last_shot_time = 0.0


# Constants
MAX_STEPS_PER_EPISODE = 500
NPC_INITIAL_HEALTH = 100.0
NPC_INITIAL_AMMO = 30
PLAYER_INITIAL_HEALTH = 100.0
MAX_OBSERVATION_DISTANCE = 50.0 # Max distance to normalize player position/distance
LINE_OF_SIGHT_CHECK_INTERVAL = 0.2 # Seconds between LOS checks to save performance

# Reward structure
REWARD_DAMAGE_PLAYER = 15.0
REWARD_KILL_PLAYER = 200.0
REWARD_TAKE_DAMAGE = -10.0
REWARD_NPC_DEATH = -200.0
REWARD_STEP = -0.05 # Small penalty per step to encourage efficiency
REWARD_SHOOT_NO_AMMO = -1.0
REWARD_SHOOT_NO_LOS = -0.5 # Penalty for shooting without clear line of sight

class CombatEnvironment(gym.Env):
    """
    Gymnasium environment for the NPC combat AI in Project Chimera.

    Observation Space:
        - NPC Health (normalized 0-1)
        - NPC Ammo (normalized 0-1)
        - Relative Player X (normalized -1 to 1 based on MAX_OBSERVATION_DISTANCE)
        - Relative Player Z (normalized -1 to 1 based on MAX_OBSERVATION_DISTANCE)
        - Distance to Player (normalized 0-1 based on MAX_OBSERVATION_DISTANCE)
        - Angle to Player (normalized -1 to 1, where 0 is straight ahead)
        - Player Visible (0 or 1)
        - Time since last damage taken (normalized 0-1, e.g., over 5 seconds)
        - Time since last shot fired (normalized 0-1, e.g., over 2 seconds)

    Action Space (Discrete):
        - 0: Move Forward
        - 1: Move Backward
        - 2: Strafe Left
        - 3: Strafe Right
        - 4: Turn Left
        - 5: Turn Right
        - 6: Shoot
        - 7: Idle / Do Nothing
    """
    metadata = {'render_modes': ['human'], 'render_fps': 60} # 'human' implies Ursina window

    def __init__(self, player: Player, npc: NPC, npc_start_pos: Vec3, player_start_pos: Vec3):
        """
        Initializes the combat environment.

        Args:
            player: Reference to the Player object in the game.
            npc: Reference to the specific NPC this environment controls.
            npc_start_pos: Initial position for the NPC at episode reset.
            player_start_pos: Initial position for the player at episode reset.
        """
        super().__init__()

        if not isinstance(player, Player):
            raise TypeError(f"Expected Player object, got {type(player)}")
        if not isinstance(npc, NPC):
            raise TypeError(f"Expected NPC object, got {type(npc)}")
        if not isinstance(npc_start_pos, Vec3):
             raise TypeError(f"Expected Vec3 for npc_start_pos, got {type(npc_start_pos)}")
        if not isinstance(player_start_pos, Vec3):
             raise TypeError(f"Expected Vec3 for player_start_pos, got {type(player_start_pos)}")


        self.player = player
        self.npc = npc
        self.npc_start_pos = npc_start_pos
        self.player_start_pos = player_start_pos

        # --- Action Space ---
        # 0: Move Fwd, 1: Move Bwd, 2: Strafe L, 3: Strafe R,
        # 4: Turn L, 5: Turn R, 6: Shoot, 7: Idle
        self.action_space = spaces.Discrete(8)

        # --- Observation Space ---
        # Health, Ammo, RelX, RelZ, Dist, Angle, LOS, DmgTime, ShotTime
        obs_low = np.array([0, 0, -1, -1, 0, -1, 0, 0, 0], dtype=np.float32)
        obs_high = np.array([1, 1, 1, 1, 1, 1, 1, 1, 1], dtype=np.float32)
        self.observation_space = spaces.Box(low=obs_low, high=obs_high, dtype=np.float32)

        # Internal state
        self.current_step = 0
        self.last_npc_health = NPC_INITIAL_HEALTH
        self.last_player_health = PLAYER_INITIAL_HEALTH
        self.last_los_check_time = 0.0
        self.player_in_los = False # Cache LOS result

        # Ensure game time exists or use a fallback
        self._get_time = time.time if 'time' in globals() else lambda: 0.0

        print(f"CombatEnvironment initialized for NPC: {getattr(npc, 'name', 'Unnamed NPC')}")


    def _get_obs(self) -> np.ndarray:
        """
        Collects the current game state relevant to the NPC agent.

        Returns:
            np.ndarray: The observation array.
        """
        try:
            # --- NPC State ---
            npc_health_norm = self.npc.health / self.npc.max_health if self.npc.max_health > 0 else 0.0
            npc_ammo_norm = self.npc.ammo / self.npc.max_ammo if self.npc.max_ammo > 0 else 0.0

            # --- Player Relative State ---
            vec_to_player = self.player.position - self.npc.position
            dist_to_player = vec_to_player.length()

            # Normalize distance
            dist_norm = min(dist_to_player / MAX_OBSERVATION_DISTANCE, 1.0)

            # Relative position in NPC's local coordinates
            # Need npc.forward and npc.right vectors (assuming standard Ursina entity properties)
            npc_forward = getattr(self.npc, 'forward', Vec3(0, 0, 1))
            npc_right = getattr(self.npc, 'right', Vec3(1, 0, 0))

            # Project vec_to_player onto npc's forward and right vectors
            # Ensure vec_to_player is treated as direction for dot product if needed
            vec_to_player_dir = vec_to_player.normalized() if dist_to_player > 0 else Vec3(0,0,0)

            # Calculate relative X and Z (using dot products)
            # Note: Ursina's coordinate system might be Y-up. Assuming XZ plane for horizontal movement.
            rel_x = vec_to_player.dot(npc_right)
            rel_z = vec_to_player.dot(npc_forward)

            # Normalize relative coordinates
            rel_x_norm = clamp(rel_x / MAX_OBSERVATION_DISTANCE, -1.0, 1.0)
            rel_z_norm = clamp(rel_z / MAX_OBSERVATION_DISTANCE, -1.0, 1.0)

            # Angle to player (-1 to 1, 0 is straight ahead)
            angle_to_player = 0.0
            if dist_to_player > 0.1: # Avoid division by zero or unstable calculations at close range
                dot_product = npc_forward.dot(vec_to_player_dir)
                # Clamp dot_product to avoid potential floating point errors with acos
                dot_product = clamp(dot_product, -1.0, 1.0)
                angle_rad = np.arccos(dot_product)
                # Determine sign based on cross product (which side is the player on?)
                cross_product_y = npc_forward.cross(vec_to_player_dir).y
                if cross_product_y < 0:
                    angle_rad = -angle_rad
                # Normalize angle (e.g., to -1 to 1 range from -pi to pi)
                angle_to_player = angle_rad / np.pi

            # --- Line of Sight (LOS) ---
            # Perform LOS check periodically to save performance
            current_time = self._get_time()
            if current_time - self.last_los_check_time > LINE_OF_SIGHT_CHECK_INTERVAL:
                self.last_los_check_time = current_time
                if 'raycast' in globals() and hasattr(self.npc, 'world_position') and hasattr(self.player, 'world_position'):
                    # Add a small vertical offset to raycast origin/target to avoid hitting floor
                    npc_eye_pos = self.npc.world_position + Vec3(0, self.npc.height * 0.8, 0) if hasattr(self.npc, 'height') else self.npc.world_position + Vec3(0, 1.5, 0)
                    player_center_pos = self.player.world_position + Vec3(0, self.player.height * 0.5, 0) if hasattr(self.player, 'height') else self.player.world_position + Vec3(0, 0.9, 0)

                    hit_info = raycast(origin=npc_eye_pos,
                                       direction=(player_center_pos - npc_eye_pos).normalized(),
                                       distance=MAX_OBSERVATION_DISTANCE,
                                       ignore=[self.npc, self.player], # Ignore self and player
                                       debug=False) # Set debug=True for visualization
                    self.player_in_los = not hit_info.hit
                else:
                    # Fallback if raycast or positions are unavailable
                    self.player_in_los = True # Assume visible if raycast fails

            player_visible = 1.0 if self.player_in_los else 0.0

            # --- Temporal Information ---
            time_since_damage = clamp((current_time - self.npc.last_damage_time) / 5.0, 0.0, 1.0) if hasattr(self.npc, 'last_damage_time') else 0.0
            time_since_shot = clamp((current_time - self.npc.last_shot_time) / 2.0, 0.0, 1.0) if hasattr(self.npc, 'last_shot_time') else 0.0


            # --- Assemble Observation Vector ---
            observation = np.array([
                npc_health_norm,
                npc_ammo_norm,
                rel_x_norm,
                rel_z_norm,
                dist_norm,
                angle_to_player,
                player_visible,
                time_since_damage,
                time_since_shot
            ], dtype=np.float32)

            # Validate observation shape and bounds
            if observation.shape != self.observation_space.shape:
                 raise ValueError(f"Observation shape mismatch: expected {self.observation_space.shape}, got {observation.shape}")
            if not self.observation_space.contains(observation):
                 # Clamp values just in case of floating point issues, and issue warning
                 observation = np.clip(observation, self.observation_space.low, self.observation_space.high)
                 print(f"Warning: Observation out of bounds, clipped. Value: {observation}")


            return observation

        except Exception as e:
            print(f"Error in _get_obs: {e}")
            # Return a default observation in case of error to prevent crash
            return np.zeros(self.observation_space.shape, dtype=np.float32)


    def _calculate_reward(self) -> float:
        """
        Calculates the reward based on the change in game state since the last step.

        Returns:
            float: The calculated reward.
        """
        reward = 0.0

        # --- Health Changes ---
        npc_health_delta = self.npc.health - self.last_npc_health
        player_health_delta = self.player.health - self.last_player_health

        if npc_health_delta < 0:
            reward += REWARD_TAKE_DAMAGE * abs(npc_health_delta / 10.0) # Scale reward by damage amount

        if player_health_delta < 0:
            reward += REWARD_DAMAGE_PLAYER * abs(player_health_delta / 10.0) # Scale reward by damage amount

        # --- Terminal State Rewards ---
        if self.npc.health <= 0:
            reward += REWARD_NPC_DEATH
        if self.player.health <= 0:
            reward += REWARD_KILL_PLAYER

        # --- Action-Specific Rewards/Penalties (can be added in step based on action taken) ---
        # Example: Penalty for shooting without ammo/LOS handled in step()

        # --- Step Penalty ---
        reward += REWARD_STEP

        # Update health trackers for next step
        self.last_npc_health = self.npc.health
        self.last_player_health = self.player.health

        return reward

    def reset(self, seed=None, options=None):
        """
        Resets the environment for a new episode.

        Args:
            seed (int, optional): The seed for the random number generator. Defaults to None.
            options (dict, optional): Additional options for environment reset. Defaults to None.

        Returns:
            tuple: A tuple containing the initial observation and an info dictionary.
        """
        super().reset(seed=seed) # Important for reproducibility if seed is used

        # Reset NPC state (position, health, ammo, etc.)
        # Use the NPC's own reset method if it exists, otherwise set manually
        if hasattr(self.npc, 'reset_state'):
            self.npc.reset_state(position=self.npc_start_pos,
                                 health=NPC_INITIAL_HEALTH,
                                 ammo=NPC_INITIAL_AMMO)
        else:
            # Manual reset if method doesn't exist
            self.npc.position = self.npc_start_pos
            self.npc.health = NPC_INITIAL_HEALTH
            self.npc.max_health = NPC_INITIAL_HEALTH
            self.npc.ammo = NPC_INITIAL_AMMO
            self.npc.max_ammo = NPC_INITIAL_AMMO
            self.npc.rotation_y = random.uniform(0, 360) # Random initial orientation
            if hasattr(self.npc, 'last_damage_time'): self.npc.last_damage_time = 0.0
            if hasattr(self.npc, 'last_shot_time'): self.npc.last_shot_time = 0.0


        # Reset Player state (position, health) - Optional, depending on training setup
        # Usually, the player might reset independently or based on game logic
        # For isolated NPC training, resetting the player ensures consistent starting conditions.
        if hasattr(self.player, 'reset_state'): # Assuming player might also have a reset
             self.player.reset_state(position=self.player_start_pos, health=PLAYER_INITIAL_HEALTH)
        else:
             self.player.position = self.player_start_pos
             self.player.health = PLAYER_INITIAL_HEALTH
             self.player.max_health = PLAYER_INITIAL_HEALTH


        # Reset internal environment state
        self.current_step = 0
        self.last_npc_health = self.npc.health
        self.last_player_health = self.player.health
        self.last_los_check_time = self._get_time() # Reset LOS timer
        self.player_in_los = False # Reset cached LOS

        # Get initial observation
        observation = self._get_obs()
        info = self._get_info() # Get initial info dict

        # print(f"Environment reset. NPC Start Health: {self.npc.health}, Player Start Health: {self.player.health}")

        return observation, info

    def step(self, action: int):
        """
        Applies the agent's action, updates the environment state, and returns results.

        Args:
            action (int): The action chosen by the agent.

        Returns:
            tuple: A tuple containing:
                - observation (np.ndarray): The observation after the action.
                - reward (float): The reward received for the action.
                - terminated (bool): Whether the episode has ended (NPC or Player died).
                - truncated (bool): Whether the episode was cut short (e.g., max steps).
                - info (dict): Additional information.
        """
        if not self.action_space.contains(action):
            raise ValueError(f"Invalid action: {action}")

        self.current_step += 1
        action_reward_penalty = 0.0 # Specific penalties for certain actions

        # --- Apply Action to NPC ---
        # This part translates the discrete action index into NPC behavior calls.
        # IMPORTANT: In a live Ursina integration, these might set flags or desired states
        # that the NPC's own update() method reads in the main game loop.
        # The actual movement/shooting happens within Ursina's time step (time.dt).
        # For simplicity here, we assume direct calls or setting movement vectors.

        move_direction = Vec3(0, 0, 0)
        turn_amount = 0.0
        shoot_attempted = False

        if action == 0: # Move Forward
            move_direction = self.npc.forward if hasattr(self.npc, 'forward') else Vec3(0,0,1)
        elif action == 1: # Move Backward
            move_direction = -self.npc.forward if hasattr(self.npc, 'forward') else Vec3(0,0,-1)
        elif action == 2: # Strafe Left
            move_direction = -self.npc.right if hasattr(self.npc, 'right') else Vec3(-1,0,0)
        elif action == 3: # Strafe Right
            move_direction = self.npc.right if hasattr(self.npc, 'right') else Vec3(1,0,0)
        elif action == 4: # Turn Left
            turn_amount = -1.0 # Negative for left turn
        elif action == 5: # Turn Right
            turn_amount = 1.0 # Positive for right turn
        elif action == 6: # Shoot
            shoot_attempted = True
            current_time = self._get_time()
            can_shoot = (current_time - getattr(self.npc, 'last_shot_time', 0.0) >= getattr(self.npc, 'shoot_cooldown', 0.2))

            if can_shoot:
                if self.npc.ammo > 0:
                    if self.player_in_los: # Only shoot if player is visible (based on last check)
                        if hasattr(self.npc, 'shoot'):
                            self.npc.shoot(self.player.position) # Assumes shoot method handles ammo, cooldown etc.
                        else:
                            print("Warning: NPC has no 'shoot' method.")
                            self.npc.ammo = max(0, self.npc.ammo - 1) # Manual ammo decrement if no method
                            if hasattr(self.npc, 'last_shot_time'): self.npc.last_shot_time = current_time
                    else:
                        action_reward_penalty += REWARD_SHOOT_NO_LOS # Penalty for shooting without LOS
                else:
                    action_reward_penalty += REWARD_SHOOT_NO_AMMO # Penalty for trying to shoot with no ammo
            # else: cooldown active, do nothing specific here, handled by NPC logic potentially

        elif action == 7: # Idle
            pass # Do nothing

        # --- Update NPC state based on action (Simulated or Delegated) ---
        # If integrating with live Ursina, these calls might happen in NPC's update()
        if hasattr(self.npc, 'move') and move_direction.length_squared() > 0:
            self.npc.move(move_direction) # Assumes move handles speed and time.dt internally
        if hasattr(self.npc, 'turn') and turn_amount != 0:
            self.npc.turn(turn_amount) # Assumes turn handles speed and time.dt internally

        # --- Get Next State ---
        # Note: In a live game, we might need to wait for the next Ursina frame
        # before getting the observation and calculating reward.
        # For this structure, we assume the state is updated sufficiently after action intent.
        observation = self._get_obs()

        # --- Calculate Reward ---
        # Base reward from state changes + action-specific penalties
        reward = self._calculate_reward() + action_reward_penalty

        # --- Check Termination Conditions ---
        terminated = bool(self.npc.health <= 0 or self.player.health <= 0)

        # --- Check Truncation Conditions ---
        truncated = bool(self.current_step >= MAX_STEPS_PER_EPISODE)

        # --- Get Info ---
        info = self._get_info()
        info['action_taken'] = action # Add action to info if needed

        # --- Debugging Output (Optional) ---
        # if self.current_step % 50 == 0:
        #     print(f"Step: {self.current_step}, Action: {action}, Reward: {reward:.2f}, NPC HP: {self.npc.health:.1f}, Player HP: {self.player.health:.1f}, Term: {terminated}, Trunc: {truncated}")

        return observation, reward, terminated, truncated, info

    def render(self):
        """
        Rendering is handled by the main Ursina application loop.
        This method is included for Gym compatibility but typically does nothing.
        """
        pass # Rendering handled by Ursina externally

    def close(self):
        """
        Clean up any resources used by the environment.
        Usually not needed if resources are managed by the main Ursina app.
        """
        print("CombatEnvironment closed.")
        # If specific resources were allocated ONLY for this env instance, clean them here.
        pass

    def _get_info(self) -> dict:
        """
        Returns auxiliary information about the environment state.
        """
        return {
            "npc_health": self.npc.health,
            "player_health": self.player.health,
            "npc_ammo": self.npc.ammo,
            "distance_to_player": distance(self.npc.position, self.player.position) if 'distance' in globals() else -1.0,
            "player_in_los": self.player_in_los,
            "steps": self.current_step
        }

# Example Usage (for testing purposes, requires mock objects if Ursina isn't running)
if __name__ == '__main__':
    print("Testing CombatEnvironment...")

    # Create mock Player and NPC objects if Ursina isn't available/running
    # These mocks should have the attributes accessed by the environment
    class MockVec3:
        def __init__(self, x=0, y=0, z=0): self.x, self.y, self.z = x, y, z
        def __add__(self, other): return MockVec3(self.x + other.x, self.y + other.y, self.z + other.z)
        def __sub__(self, other): return MockVec3(self.x - other.x, self.y - other.y, self.z - other.z)
        def __mul__(self, scalar): return MockVec3(self.x * scalar, self.y * scalar, self.z * scalar)
        def __neg__(self): return MockVec3(-self.x, -self.y, -self.z)
        def length(self): return (self.x**2 + self.y**2 + self.z**2)**0.5
        def length_squared(self): return self.x**2 + self.y**2 + self.z**2
        def normalized(self): l = self.length(); return MockVec3(self.x/l, self.y/l, self.z/l) if l > 0 else MockVec3()
        def dot(self, other): return self.x *