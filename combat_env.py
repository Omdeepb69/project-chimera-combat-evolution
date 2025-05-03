import gymnasium as gym
import numpy as np
from ursina import *
from player import Player
from npc import EnemyNPC

class CombatEnvironment(gym.Env):
    metadata = {'render_modes': ['human'], 'render_fps': 60}

    def __init__(self, player, npcs, render_mode=None, max_steps=500):
        super().__init__()
        self.player = player
        self.npcs = npcs  # Should be a list
        self.max_steps = max_steps
        self.current_step = 0
        self.render_mode = render_mode

        # Define action and observation space
        # Action: 0: Idle, 1: Move towards player, 2: Strafe L, 3: Strafe R, 4: Seek Cover
        self.action_space = gym.spaces.Discrete(5)

        # Observation: Player Pos (3), NPC Pos (3*N), Player Health (1), NPC Health (N)
        # Needs normalization and careful design
        low = np.full(3 + 3*len(npcs) + 1 + len(npcs), -np.inf, dtype=np.float32)
        high = np.full(3 + 3*len(npcs) + 1 + len(npcs), np.inf, dtype=np.float32)
        self.observation_space = gym.spaces.Box(low, high, dtype=np.float32)

    def _get_obs(self):
        obs_list = []
        # Add player position as 3 values
        obs_list.extend([self.player.position.x, self.player.position.y, self.player.position.z])
        # Add NPC positions
        for npc in self.npcs:
            obs_list.extend([npc.position.x, npc.position.y, npc.position.z])
        # Add player health
        obs_list.append(self.player.health)
        # Add NPC health
        for npc in self.npcs:
            obs_list.append(npc.health)
        return np.array(obs_list, dtype=np.float32)

    def _get_info(self):
        # Provide auxiliary info if needed
        return {
            "player_health": self.player.health,
            "npc_health": [npc.health for npc in self.npcs],
            "distance_to_player": [distance(npc, self.player) for npc in self.npcs]
        }

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        # Reset player position and health
        self.player.position = Vec3(0, 1, 0)
        self.player.health = 100
        # Reset NPC positions and health
        for i, npc in enumerate(self.npcs):
            npc.position = Vec3(
                np.random.uniform(-15, 15),
                1,
                np.random.uniform(5, 20)
            )
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
            if self.npcs[0].state in ['seeking', 'strafing_left', 'strafing_right'] and self.current_step % 30 == 0:  # Shoot every 0.5 sec approx
                self.npcs[0].shoot_at_player()

        self.current_step += 1

        # --- Determine Reward ---
        reward = 0
        # Small penalty for existing
        reward -= 0.01
        
        # --- Check Termination/Truncation ---
        terminated = False
        truncated = False

        if self.player.health <= 0:
            print("Player defeated!")
            reward -= 100  # Large penalty for player dying
            terminated = True
        elif not self.npcs or all(npc.health <= 0 for npc in self.npcs):
            print("All NPCs defeated!")
            reward += 100  # Large reward for winning
            terminated = True

        if self.current_step >= self.max_steps:
            print("Max steps reached.")
            truncated = True  # Use truncated for time limit

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