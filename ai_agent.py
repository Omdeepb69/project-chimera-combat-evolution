# agent.py
# Defines the player agent behavior and state for Project Chimera Combat Evolution.
# Handles player movement, combat, health tracking, and interaction with the game world.

import sys
import os
import random
import math
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController

# Ensure project root is in path (consistent with other modules)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

class Player(FirstPersonController):
    """
    The player agent controlled by the human.
    Extends FirstPersonController to add combat capabilities, health tracking,
    and interactions with the game environment.
    """
    def __init__(self, position=(0, 1, 0), **kwargs):
        """
        Initialize the player agent.
        
        Args:
            position (tuple): Initial position of the player (x, y, z)
            **kwargs: Additional arguments to pass to FirstPersonController
        """
        # Set default values for FirstPersonController params if not specified
        kwargs.setdefault('speed', 5)
        kwargs.setdefault('jump_height', 2)
        kwargs.setdefault('gravity', 1)
        kwargs.setdefault('mouse_sensitivity', Vec2(40, 40))
        
        # Initialize the FirstPersonController base class
        super().__init__(position=position, **kwargs)
        
        # Health and damage properties
        self.max_health = 100.0
        self.health = self.max_health
        self.armor = 0  # Damage reduction (percentage)
        self.height = 2.0  # Used for raycasting
        self.is_vulnerable = True  # Set to False for debug invincibility
        self.last_damage_time = 0
        self.damage_cooldown = 0.1  # Minimum time between damage instances
        self.health_regeneration = 0.1  # Health points regenerated per second (when not in combat)
        self.regeneration_delay = 5.0  # Seconds after taking damage before health regeneration begins
        
        # Combat properties
        self.ammo = 100
        self.max_ammo = 100
        self.gun_damage = 15
        self.last_shot_time = 0
        self.shoot_cooldown = 0.2  # Time between shots in seconds
        self.shoot_range = 100  # Maximum distance for raycast
        self.bullet_spread = 0.02  # Accuracy/spread factor (higher = less accurate)
        
        # Flash effect when taking damage
        self.hit_flash = Entity(
            parent=camera.ui,
            model='quad',
            scale=(2, 1),
            color=color.rgba(255, 0, 0, 0),  # Start transparent
            texture='white_cube',
            z=-99
        )
        
        # Gun/weapon setup
        self.setup_weapon()
        
        # UI elements
        self.setup_ui()
        
        # Audio
        self.setup_audio()
        
        # Name for identification
        self.name = kwargs.get('name', "Player")
        
        # Flag to check if player is in editor mode (no clipping, invincible)
        self.editor_mode = False
        
        print(f"Player initialized at {self.position} with {self.health} HP")
    
    def setup_weapon(self):
        """Set up the player's weapon and related visual elements"""
        # Gun model (parented to camera for FPS view)
        self.gun = Entity(
            parent=camera,
            model='cube',
            color=color.dark_gray,
            scale=(0.2, 0.2, 1),
            position=(0.4, -0.3, 0.5),
            rotation=(0, 0, 0)
        )
        
        # Muzzle flash effect
        self.muzzle_flash = Entity(
            parent=self.gun,
            model='quad',
            scale=0.3,
            position=(0, 0, 0.6),
            color=color.yellow, 
            billboard=True,
            enabled=False
        )
        
        # Crosshair
        self.crosshair = Entity(
            parent=camera.ui,
            model='quad',
            scale=0.02,
            color=color.white,
            texture='crosshair',
            origin=(0, 0)
        )
    
    def setup_ui(self):
        """Set up the player's UI elements"""
        # Health bar
        self.health_bar_bg = Entity(
            parent=camera.ui,
            model='quad',
            scale=(0.3, 0.03),
            position=(-0.6, -0.4),
            color=color.dark_gray
        )
        self.health_bar = Entity(
            parent=camera.ui,
            model='quad',
            scale=(0.3, 0.03),
            position=(-0.6, -0.4),
            color=color.rgb(200, 50, 50),
            origin=(-0.5, 0)  # Left aligned for proper scaling
        )
        
        # Ammo counter
        self.ammo_text = Text(
            parent=camera.ui,
            text=f"Ammo: {self.ammo}/{self.max_ammo}",
            position=(0.6, -0.4),
            origin=(0.5, 0),
            color=color.white
        )
        
        # Health text
        self.health_text = Text(
            parent=camera.ui,
            text=f"Health: {int(self.health)}/{self.max_health}",
            position=(-0.6, -0.45),
            origin=(0, 0),
            color=color.white
        )
    
    def setup_audio(self):
        """Set up audio components"""
        self.shoot_sound = Audio('shoot', loop=False, autoplay=False, volume=0.5)
        self.hit_enemy_sound = Audio('hit', loop=False, autoplay=False, volume=0.4)
        self.take_damage_sound = Audio('hurt', loop=False, autoplay=False, volume=0.6)
        self.no_ammo_sound = Audio('empty', loop=False, autoplay=False, volume=0.3)
        self.footstep_sound = Audio('footstep', loop=False, autoplay=False, volume=0.2)
        self.footstep_timer = 0
    
    def update(self):
        """Called every frame by Ursina engine"""
        # Call parent class update for movement
        super().update()
        
        # Update health bar visualization
        health_percentage = self.health / self.max_health
        self.health_bar.scale_x = 0.3 * health_percentage
        
        # Update UI text elements
        self.health_text.text = f"Health: {int(self.health)}/{self.max_health}"
        self.ammo_text.text = f"Ammo: {self.ammo}/{self.max_ammo}"
        
        # Health regeneration when not recently damaged
        current_time = time.time()
        if (current_time - self.last_damage_time > self.regeneration_delay and 
            self.health < self.max_health):
            self.health = min(self.health + self.health_regeneration * time.dt, self.max_health)
        
        # Footstep sounds
        if self.moving and self.grounded:
            self.footstep_timer += time.dt
            if self.footstep_timer > 0.5:  # Every half second while moving
                self.footstep_timer = 0
                if self.footstep_sound:
                    self.footstep_sound.play()
        
        # Gun bob effect when walking
        if self.moving and self.grounded:
            # Simple sine wave bobbing
            self.gun.y = -0.3 + math.sin(time.time() * 8) * 0.02
            self.gun.x = 0.4 + math.cos(time.time() * 4) * 0.01
        else:
            # Smoothly return to default position
            self.gun.y = lerp(self.gun.y, -0.3, time.dt * 5)
            self.gun.x = lerp(self.gun.x, 0.4, time.dt * 5)
    
    def input(self, key):
        """Handle input events"""
        # Call parent class input handler first
        super().input(key)
        
        # Handle shooting - moved to main.py's update function for consistency
        # (should be checked with held_keys['left mouse'] there)
        
        # Toggle editor mode (no clip, invincible) - for testing
        if key == 'f1':
            self.editor_mode = not self.editor_mode
            self.gravity = 0 if self.editor_mode else 1
            self.is_vulnerable = not self.editor_mode
            print(f"Editor mode: {'ON' if self.editor_mode else 'OFF'}")
            
            # Confirmation message
            msg = Text(
                text=f"Editor Mode: {'ON' if self.editor_mode else 'OFF'}", 
                origin=(0, 0), 
                scale=2,
                color=color.yellow if self.editor_mode else color.white
            )
            destroy(msg, delay=1)  # Remove after 1 second
    
    def shoot(self):
        """Handle player shooting logic"""
        current_time = time.time()
        
        # Check cooldown
        if current_time - self.last_shot_time < self.shoot_cooldown:
            return False
        
        # Check ammo
        if self.ammo <= 0:
            if self.no_ammo_sound:
                self.no_ammo_sound.play()
            return False
        
        # Update shot timing and ammo
        self.last_shot_time = current_time
        self.ammo -= 1
        
        # Visual effects
        if self.muzzle_flash:
            self.muzzle_flash.enabled = True
            invoke(setattr, self.muzzle_flash, 'enabled', False, delay=0.05)
        
        # Play sound
        if self.shoot_sound:
            self.shoot_sound.play()
        
        # Add slight random spread to the shot
        spread_x = random.uniform(-self.bullet_spread, self.bullet_spread)
        spread_y = random.uniform(-self.bullet_spread, self.bullet_spread)
        direction = camera.forward + Vec3(spread_x, spread_y, 0)
        
        # Raycast to check for hits
        hit_info = raycast(
            origin=camera.world_position,
            direction=direction,
            distance=self.shoot_range,
            ignore=[self, self.gun, self.muzzle_flash],
            debug=False  # Set to True for visualization
        )
        
        if hit_info.hit:
            # Check if we hit an enemy
            if hasattr(hit_info.entity, 'tag') and hit_info.entity.tag == 'enemy':
                # Calculate damage based on distance
                distance_factor = 1.0 - (hit_info.distance / self.shoot_range) * 0.3
                damage = self.gun_damage * distance_factor * random.uniform(0.9, 1.1)
                
                # Apply damage to the entity
                if hasattr(hit_info.entity, 'take_damage'):
                    hit_info.entity.take_damage(damage)
                    
                    # Play hit confirmation sound
                    if self.hit_enemy_sound:
                        self.hit_enemy_sound.play()
                        
                # Create hit particle effect
                self.create_hit_effect(hit_info.world_point, hit_info.world_normal)
                
                return True
            else:
                # Hit something else (wall, prop, etc.)
                self.create_hit_effect(hit_info.world_point, hit_info.world_normal, is_enemy=False)
        
        return False
    
    def create_hit_effect(self, position, normal, is_enemy=True):
        """Create particle effect for bullet impact"""
        # Different effects for enemy hits vs. environment hits
        if is_enemy:
            # Blood/damage effect
            particles = ParticleSystem(
                position=position,
                rotation_y=random.uniform(0, 360),
                color=color.rgb(150, 0, 0),
                velocity=normal * 2,
                gravity=1,
                scale=0.1,
                lifetime=0.5,
                amount=10
            )
        else:
            # Sparks/dust for environment
            particles = ParticleSystem(
                position=position,
                rotation_y=random.uniform(0, 360),
                color=color.light_gray,
                velocity=normal * 1,
                gravity=0.5,
                scale=0.05,
                lifetime=0.3,
                amount=5
            )
        
        # Cleanup after effect finishes
        destroy(particles, delay=0.5)
    
    def take_damage(self, amount):
        """
        Handle player taking damage
        
        Args:
            amount (float): Amount of damage to take
            
        Returns:
            float: Current health after damage
        """
        current_time = time.time()
        
        # Invincibility check
        if not self.is_vulnerable:
            return self.health
        
        # Cooldown check to prevent damage spam
        if current_time - self.last_damage_time < self.damage_cooldown:
            return self.health
        
        self.last_damage_time = current_time
        
        # Apply armor reduction if any
        if self.armor > 0:
            amount *= (1.0 - (self.armor / 100.0))
        
        # Apply damage
        self.health -= amount
        
        # Clamp health
        self.health = max(0, self.health)
        
        # Play damage sound
        if self.take_damage_sound:
            self.take_damage_sound.play()
        
        # Visual feedback - red flash
        self.hit_flash.animate_color(color.rgba(255, 0, 0, 0.3), duration=0.05, curve=curve.linear)
        self.hit_flash.animate_color(color.rgba(255, 0, 0, 0), duration=0.3, delay=0.05, curve=curve.linear)
        
        # Camera shake for impact
        camera.shake(duration=0.2, magnitude=0.02)
        
        # Handle death
        if self.health <= 0:
            self.die()
        
        return self.health
    
    def heal(self, amount):
        """Heal the player by the specified amount"""
        if self.health <= 0:
            return  # Can't heal a dead player
            
        self.health = min(self.health + amount, self.max_health)
        
        # Visual feedback - green flash
        self.hit_flash.animate_color(color.rgba(0, 255, 0, 0.2), duration=0.1, curve=curve.linear)
        self.hit_flash.animate_color(color.rgba(0, 255, 0, 0), duration=0.3, delay=0.1, curve=curve.linear)
        
        # Sound effect for healing could be added here
    
    def add_ammo(self, amount):
        """Add ammo to the player's weapon"""
        self.ammo = min(self.ammo + amount, self.max_ammo)
        
        # UI feedback
        self.ammo_text.text = f"Ammo: {self.ammo}/{self.max_ammo}"
        self.ammo_text.animate_color(color.yellow, duration=0.1)
        self.ammo_text.animate_color(color.white, duration=0.3, delay=0.1)
    
    def die(self):
        """Handle player death"""
        self.health = 0
        self.is_vulnerable = False
        
        # Disable movement
        self.enabled = False
        mouse.locked = False
        
        print("Player has died!")
        
        # Visual effects for death (from first-person view)
        self.hit_flash.animate_color(color.rgba(255, 0, 0, 0.8), duration=0.5, curve=curve.linear)
        camera.animate_position(camera.position + Vec3(0, -1, 0), duration=1)
        camera.animate_rotation(Vec3(90, camera.rotation.y, 0), duration=0.5)
        
        # Hide gun
        if self.gun:
            self.gun.visible = False
        
        # Show death message
        death_message = Text(
            text="YOU DIED", 
            origin=(0, 0), 
            scale=3,
            color=color.red
        )
        
        # Victory/defeat logic handled in main.py
    
    def reset_state(self, position=None, health=None, ammo=None):
        """
        Reset the player state for a new game or respawn
        
        Args:
            position (Vec3): New position to reset to
            health (float): New health value
            ammo (int): New ammo count
        """
        # Re-enable player
        self.enabled = True
        mouse.locked = True
        self.is_vulnerable = True
        
        # Reset position
        if position is not None:
            self.position = position
        else:
            self.position = Vec3(0, 1, 0)  # Default spawn
        
        # Reset health
        if health is not None:
            self.health = health
            self.max_health = health
        else:
            self.health = self.max_health
        
        # Reset ammo
        if ammo is not None:
            self.ammo = ammo
            self.max_ammo = ammo
        else:
            self.ammo = self.max_ammo
        
        # Reset timers
        self.last_damage_time = 0
        self.last_shot_time = 0
        
        # Reset visual effects
        self.hit_flash.color = color.rgba(255, 0, 0, 0)
        camera.rotation = Vec3(0, 0, 0)
        
        # Show gun
        if self.gun:
            self.gun.visible = True
        
        print(f"Player reset at {self.position} with {self.health} HP and {self.ammo} ammo")
    
    def get_observation_info(self):
        """
        Returns a dict of player state information for the RL environment.
        Used by combat_env.py for building the observation space.
        """
        return {
            "position": self.position,
            "rotation": self.rotation,
            "health": self.health,
            "ammo": self.ammo,
            "grounded": self.grounded
        }

# For testing as standalone
if __name__ == '__main__':
    app = Ursina(title='Player Agent Test')
    
    # Simple test scene
    ground = Entity(model='plane', scale=(100, 1, 100), color=color.gray, texture='white_cube', texture_scale=(100, 100), collider='box')
    Sky()
    
    # Create some test blocks
    for i in range(10):
        Entity(model='cube', color=color.gray, position=(random.uniform(-10, 10), 1, random.uniform(-10, 10)), scale=(1, 2, 1), collider='box')
    
    # Create a test target
    target = Entity(model='cube', color=color.red, position=(0, 1.5, 10), scale=(1, 2, 1), collider='box')
    target.tag = 'enemy'
    target.health = 100
    
    def target_take_damage(damage):
        target.health -= damage
        print(f"Target hit! Health: {target.health}")
        target.animate_color(color.white, duration=0.1)
        target.animate_color(color.red, duration=0.1, delay=0.1)
        if target.health <= 0:
            target.color = color.black
    
    target.take_damage = target_take_damage
    
    # Create player
    player = Player(position=(0, 1, 0))
    
    # Test controls
    test_controls = Text(
        text="Controls: WASD = Move, Space = Jump, Left Click = Shoot\n" 
             "F1 = Toggle Editor Mode, R = Take Damage (Test), H = Heal (Test)",
        scale=1.5,
        origin=(0, 0),
        position=(0, 0.4)
    )
    
    def input(key):
        # Test damage
        if key == 'r':
            player.take_damage(20)
            print(f"Test damage applied. Health: {player.health}")
        
        # Test healing
        if key == 'h':
            player.heal(25)
            print(f"Test healing applied. Health: {player.health}")
        
        # Test ammo
        if key == 'e':
            player.add_ammo(30)
            print(f"Test ammo added. Ammo: {player.ammo}")
    
    def update():
        # Handle shooting in update for continuous fire
        if held_keys['left mouse']:
            player.shoot()
    
    print("Player Agent Test Running. Press Esc to quit.")
    app.run()
