# player.py - Defines the player character for Project Chimera Combat Evolution

import sys
import os

# Ensure the project root is in the Python path
# This allows importing modules from the project root, like potential RL environment definitions
# Adjust the number of '..' based on the depth of this file relative to the project root
# Assuming 'player.py' is directly inside the project root or a subdirectory like 'src'
# If 'player.py' is in the root:
# project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
# If 'player.py' is in 'src':
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import time # For cooldowns

# --- Potentially Required Project-Wide Imports (Commented out if not directly used here) ---
# import numpy as np
# import gymnasium as gym
# --- Choose one ML backend ---
# import tensorflow as tf
# import torch
# --- Choose one RL Library ---
# from stable_baselines3 import PPO # Example
# from tf_agents.agents.dqn import dqn_agent # Example
# -----------------------------------------------------------------------------------------

class Player(FirstPersonController):
    """
    Represents the player character in the game.
    Handles movement, aiming, shooting, and player state (health).
    Inherits from Ursina's FirstPersonController for built-in FPS mechanics.
    """
    def __init__(self, position=(0, 2, 0), speed=5, jump_height=2.0, **kwargs):
        """
        Initializes the Player entity.

        Args:
            position (tuple, optional): Starting position. Defaults to (0, 2, 0).
            speed (int, optional): Movement speed. Defaults to 5.
            jump_height (float, optional): Jump height. Defaults to 2.0.
            **kwargs: Additional keyword arguments for Entity.
        """
        super().__init__(
            position=position,
            speed=speed,
            jump_height=jump_height,
            gravity=0.8, # Adjusted gravity for a slightly heavier feel
            collider='box', # Use a box collider for physics interactions
            **kwargs
        )

        # --- Player State ---
        self.max_health = 100
        self.health = self.max_health
        self.is_alive = True

        # --- Shooting Mechanics ---
        self.shoot_cooldown = 0.2  # Seconds between shots
        self._last_shot_time = -self.shoot_cooldown # Allow shooting immediately
        self.gun_damage = 15 # Damage per shot

        # --- Visuals / Audio (Optional but good for feedback) ---
        # Simple representation of a gun attached to the camera
        self.gun = Entity(
            parent=camera.ui, # Attach to UI camera for consistent view
            model='cube',
            scale=(0.1, 0.1, 0.5),
            position=(0.3, -0.25, 0.5), # Position relative to camera
            rotation=(-5, 10, 0),
            color=color.dark_gray,
            texture='white_cube'
        )
        # Muzzle flash effect
        self.muzzle_flash = Entity(
            parent=self.gun,
            model='quad',
            scale=0.2,
            position=(0, 0, 0.55), # Position at the tip of the gun model
            color=color.yellow,
            billboard=True,
            enabled=False
        )
        # Basic crosshair
        self.crosshair = Entity(
            parent=camera.ui,
            model='quad',
            texture='crosshair', # Assumes 'crosshair.png' exists in assets
            scale=0.03,
            color=color.white,
            rotation_z=45 # Optional rotation
        )

        # Load sounds (ensure these files exist in your project's assets folder)
        self.shoot_sound = Audio('shoot', loop=False, autoplay=False, volume=0.5)
        self.hit_sound = Audio('hit', loop=False, autoplay=False, volume=0.7)
        self.death_sound = Audio('death', loop=False, autoplay=False, volume=0.8)

        # Disable default FPC mouse lock toggle (usually F) if desired
        # self.cursor.lock_sequence = Sequence() # Disables F key toggle

        print(f"Player initialized at {self.position} with {self.health} HP.")


    def input(self, key):
        """
        Handles player input, specifically shooting.
        Movement input is handled by the parent FirstPersonController.
        """
        if not self.is_alive:
            return # Don't process input if dead

        if key == 'left mouse down':
            self.shoot()

        # Let the parent class handle its inputs (like jumping with 'space')
        super().input(key)


    def update(self):
        """
        Called every frame. Handles ongoing logic like checking for death.
        Movement/camera updates are handled by the parent FirstPersonController.
        """
        if not self.is_alive:
            return # Don't process updates if dead

        # Check if player fell out of the world (example death condition)
        if self.y < -10:
            self.die("Fell out of the world")

        # Update gun position slightly for bobbing effect (optional)
        # self.gun.y = self.gun.original_y + math.sin(time.time() * 10) * 0.01


    def shoot(self):
        """
        Handles the shooting action: cooldown check, raycasting, effects.
        """
        current_time = time.time()
        if current_time - self._last_shot_time < self.shoot_cooldown:
            return # Cooldown active

        self._last_shot_time = current_time

        # Play sound and show muzzle flash
        if self.shoot_sound:
            self.shoot_sound.play()
        self.muzzle_flash.enabled = True
        invoke(setattr, self.muzzle_flash, 'enabled', False, delay=0.05) # Hide flash quickly

        # Perform raycast from camera center
        # Ignore the player and the gun itself in the raycast
        hit_info = raycast(
            origin=camera.world_position,
            direction=camera.forward,
            distance=100,
            ignore=(self, self.gun, self.muzzle_flash), # Ignore player and gun parts
            debug=False # Set to True to visualize the ray
        )

        if hit_info.hit:
            # print(f"Hit: {hit_info.entity} at {hit_info.world_point}") # Debugging
            # Check if the hit entity is an enemy (requires enemy entities to have a 'tag' or specific class/attribute)
            if hasattr(hit_info.entity, 'tag') and hit_info.entity.tag == 'enemy':
                # print(f"Dealing {self.gun_damage} damage to {hit_info.entity}") # Debugging
                if hasattr(hit_info.entity, 'take_damage'):
                    hit_info.entity.take_damage(self.gun_damage)
                else:
                    print(f"Warning: Hit entity {hit_info.entity} has tag 'enemy' but no 'take_damage' method.")
            # Optional: Create a visual impact effect
            # impact_effect = Entity(model='sphere', scale=0.1, position=hit_info.world_point, color=color.red)
            # destroy(impact_effect, delay=0.1)


    def take_damage(self, amount):
        """
        Reduces player health and handles death if health drops to zero or below.

        Args:
            amount (int): The amount of damage to take.
        """
        if not self.is_alive:
            return

        self.health -= amount
        print(f"Player took {amount} damage, health: {self.health}/{self.max_health}")

        if self.hit_sound:
            self.hit_sound.play()

        # Optional: Add visual feedback for taking damage (e.g., screen flash)
        # camera.shake(duration=0.1, magnitude=2)
        # red_flash = Panel(scale=10, color=color.rgba(255, 0, 0, 150), alpha=0)
        # red_flash.animate_alpha(0, duration=0.2)

        if self.health <= 0:
            self.health = 0
            self.die("Eliminated")


    def die(self, reason="Defeated"):
        """
        Handles the player's death.
        """
        if not self.is_alive:
            return # Already dead

        print(f"Player Died: {reason}")
        self.is_alive = False
        self.health = 0
        self.enabled = False # Disable player movement and input processing
        self.gun.enabled = False
        self.crosshair.enabled = False

        if self.death_sound:
            self.death_sound.play()

        # Optional: Show a death message or trigger a game over screen
        Text(text=f"YOU DIED\n({reason})", origin=(0,0), scale=2, background=True)

        # Optional: Respawn logic after a delay
        # invoke(self.respawn, delay=3)


    def respawn(self, position=(0, 2, 0)):
        """
        Resets player state and position.
        """
        print("Player Respawning...")
        self.position = position
        self.health = self.max_health
        self.is_alive = True
        self.enabled = True
        self.gun.enabled = True
        self.crosshair.enabled = True
        # Reset any death UI elements
        # find_entity('YOU DIED').disable() # Example if using a Text entity

# --- Example Usage (if running this file directly) ---
if __name__ == '__main__':
    app = Ursina()

    # Simple ground for testing
    ground = Entity(model='plane', scale=(100, 1, 100), color=color.gray, texture='white_cube', texture_scale=(100, 100), collider='box')
    # Some obstacles
    box1 = Entity(model='cube', scale=(5, 5, 5), position=(10, 2.5, 10), color=color.blue, collider='box', texture='white_cube')
    box2 = Entity(model='cube', scale=(3, 8, 3), position=(-8, 4, 5), color=color.green, collider='box', texture='white_cube')

    # Create the player
    player = Player(position=(0, 1, 0), speed=8)

    # Dummy enemy for testing shooting
    class DummyEnemy(Entity):
        def __init__(self, position=(5, 0.5, 15)):
            super().__init__(
                model='cube',
                color=color.red,
                collider='box',
                position=position,
                tag='enemy' # Important tag for raycast detection
            )
            self.health = 50

        def take_damage(self, amount):
            self.health -= amount
            print(f"DummyEnemy took {amount} damage, health: {self.health}")
            self.blink(color.white, duration=0.1) # Visual feedback
            if self.health <= 0:
                print("DummyEnemy destroyed!")
                destroy(self)

    enemy = DummyEnemy()

    # Basic sky
    Sky()

    # Lock mouse and hide cursor
    mouse.locked = True
    mouse.visible = False

    app.run()