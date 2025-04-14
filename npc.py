# npc.py
# Defines the enemy NPC behavior and state for Project Chimera Combat Evolution.

import sys
import os
import random
import math
from ursina import *

# Ensure project root is in path (similar to player.py approach)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

class EnemyNPC(Entity):
    """
    An enemy NPC that can be controlled by AI.
    Handles movement, shooting, health tracking, and communication with the AI agent.
    """
    def __init__(self, position=(0, 1, 5), player_ref=None, **kwargs):
        """
        Initialize an enemy NPC entity.
        
        Args:
            position (tuple): Initial position of the NPC (x, y, z)
            player_ref: Reference to the player entity
            **kwargs: Additional arguments to pass to Entity
        """
        # Basic entity setup
        super().__init__(
            model='cube',
            scale=(1, 2, 1),
            color=color.red,
            collider='box',
            position=position,
            **kwargs
        )
        
        # Reference to player
        self.player = player_ref
        
        # Name for identification (can be set externally)
        self.name = kwargs.get('name', f"NPC_{random.randint(1000, 9999)}")
        
        # Tag for identifying entity type (used by player.shoot())
        self.tag = 'enemy'
        
        # Health and damage properties
        self.max_health = 100.0
        self.health = self.max_health
        self.height = 2.0  # Used for raycasting (eye height)
        
        # Combat properties
        self.ammo = 30
        self.max_ammo = 30
        self.gun_damage = 10
        self.last_damage_time = 0
        self.last_shot_time = 0
        self.shoot_cooldown = 0.5  # Time between shots in seconds
        
        # Movement properties
        self.move_speed = 5.0
        self.turn_speed = 120.0  # Degrees per second
        self.target_position = None
        self.last_known_player_pos = None
        
        # AI state tracking
        self.state = 'idle'  # idle, seeking, strafing_left, strafing_right, cover
        self.action_history = []  # For analysis if needed
        
        # Visual feedback
        self.hit_flash_duration = 0.1
        self.is_flashing = False
        
        # Debug visualization (optional)
        self.debug_text = Text(text='', parent=self, billboard=True, scale=10, y=2.5, visible=False)
        
        # Weapon visuals
        self.gun = Entity(
            parent=self,
            model='cube',
            scale=(0.2, 0.2, 0.8),
            position=(0.5, 0.5, 0.6),
            color=color.dark_gray
        )
        
        # Muzzle flash effect
        self.muzzle_flash = Entity(
            parent=self.gun,
            model='quad',
            scale=0.3,
            position=(0, 0, 0.5), 
            color=color.yellow,
            billboard=True,
            enabled=False
        )
        
        # Sounds
        self.shoot_sound = Audio('shoot', loop=False, autoplay=False, volume=0.3)
        self.hit_sound = Audio('hit', loop=False, autoplay=False, volume=0.4)
        self.death_sound = Audio('death', loop=False, autoplay=False, volume=0.5)
        
        print(f"Enemy NPC {self.name} initialized at {self.position}")

    def update(self):
        """Called every frame by Ursina engine"""
        if self.health <= 0:
            return  # Skip update if dead
            
        # Face player when in direct combat (basic behavior, AI will override this via turn())
        if self.player and self.state in ['seeking', 'strafing_left', 'strafing_right']:
            # Only try to face player if we're actively engaging
            direction_to_player = self.player.position - self.position
            # Get angle using atan2 for better directional awareness
            target_angle = math.degrees(math.atan2(direction_to_player.x, direction_to_player.z))
            # Smoothly rotate towards target angle (basic version, overridden by AI)
            if not hasattr(self, '_ai_controlled_rotation') or not self._ai_controlled_rotation:
                self.rotation_y = lerp(self.rotation_y, target_angle, time.dt * 5)
                
        # Update gun positioning (aim slightly toward player if visible)
        if self.player and self.gun:
            # Point gun roughly at player height
            player_height_diff = (self.player.position.y + 1) - (self.position.y + 0.5)
            self.gun.rotation_x = clamp(-player_height_diff * 15, -45, 45)
            
        # Update debug text if enabled
        if self.debug_text.visible:
            self.debug_text.text = f"{self.name}\nHP: {self.health}/{self.max_health}\nAmmo: {self.ammo}\nState: {self.state}"

    def apply_action(self, action_index):
        """
        Apply an action based on the RL agent's decision.
        Called from CombatEnvironment.step().
        
        Args:
            action_index (int): Action to perform (matches combat_env.py's action space)
                0: Move Forward
                1: Move Backward
                2: Strafe Left
                3: Strafe Right  
                4: Turn Left
                5: Turn Right
                6: Shoot
                7: Idle/Do Nothing
        """
        self._ai_controlled_rotation = False  # Reset flag
        
        # Record action for analysis
        self.action_history.append(action_index)
        if len(self.action_history) > 100:
            self.action_history.pop(0)  # Keep history manageable
            
        if action_index == 0:  # Move Forward
            self.state = 'seeking'
            self.move(self.forward)
            
        elif action_index == 1:  # Move Backward
            self.state = 'retreating'
            self.move(-self.forward)
            
        elif action_index == 2:  # Strafe Left
            self.state = 'strafing_left'
            self.move(-self.right)
            
        elif action_index == 3:  # Strafe Right
            self.state = 'strafing_right'
            self.move(self.right)
            
        elif action_index == 4:  # Turn Left
            self.state = self.state if self.state != 'idle' else 'searching'
            self.turn(-1.0)
            self._ai_controlled_rotation = True
            
        elif action_index == 5:  # Turn Right
            self.state = self.state if self.state != 'idle' else 'searching'
            self.turn(1.0)
            self._ai_controlled_rotation = True
            
        elif action_index == 6:  # Shoot
            self.state = 'attacking'
            self.shoot_at_player()
            
        elif action_index == 7:  # Idle/Do Nothing
            self.state = 'idle'
            # No action needed
            
        else:
            print(f"Warning: Unknown action index {action_index}")

    def move(self, direction, speed_multiplier=1.0):
        """
        Move in the specified direction.
        
        Args:
            direction (Vec3): Direction vector to move in
            speed_multiplier (float): Multiplier for move_speed
        """
        if direction.length() > 0:
            normalized_dir = direction.normalized()
            movement = normalized_dir * self.move_speed * speed_multiplier * time.dt
            
            # Optional: Add ray-based ground clamping for uneven terrain
            if hasattr(self, '_ground_raycast') and self._ground_raycast:
                ground_hit = raycast(self.position + Vec3(0, 0.1, 0), Vec3(0, -1, 0), distance=10)
                if ground_hit.hit:
                    new_pos = self.position + movement
                    new_pos.y = ground_hit.world_point.y + 1  # Adjust y to ground + offset
                    self.position = new_pos
                else:
                    self.position += movement
            else:
                self.position += movement

    def turn(self, amount):
        """
        Turn left or right.
        
        Args:
            amount (float): Amount to turn (-1 for left, 1 for right)
        """
        self.rotation_y += amount * self.turn_speed * time.dt

    def shoot_at_player(self):
        """Shoot at the player if possible"""
        if not self.player:
            return
            
        current_time = time.time()
        if current_time - self.last_shot_time < self.shoot_cooldown:
            return  # On cooldown
            
        if self.ammo <= 0:
            # Play empty click sound or handle reload
            return
            
        # Check line of sight
        npc_eye_pos = self.world_position + Vec3(0, self.height * 0.8, 0)
        player_center_pos = self.player.world_position + Vec3(0, self.player.height * 0.5, 0) if hasattr(self.player, 'height') else self.player.world_position + Vec3(0, 0.9, 0)
        
        hit_info = raycast(
            origin=npc_eye_pos,
            direction=(player_center_pos - npc_eye_pos).normalized(),
            distance=100,
            ignore=[self, self.gun, self.muzzle_flash],
            debug=False  # Change to True to visualize
        )
        
        self.last_shot_time = current_time
        self.ammo -= 1
        
        # Visual effects
        if self.muzzle_flash:
            self.muzzle_flash.enabled = True
            invoke(setattr, self.muzzle_flash, 'enabled', False, delay=0.05)
            
        if self.shoot_sound:
            self.shoot_sound.play()
            
        # Check if hit connects with player
        if hit_info.hit and hit_info.entity == self.player:
            # Calculate accuracy based on distance and movement
            distance_factor = clamp(1.0 - (distance(self, self.player) / 50.0), 0.2, 0.9)
            hit_chance = distance_factor
            
            # Apply dodge chance if player is moving fast
            player_speed = getattr(self.player, 'velocity', Vec3(0,0,0)).length()
            if player_speed > 3:
                hit_chance *= 0.7  # Harder to hit moving targets
                
            # Roll for hit
            if random.random() <= hit_chance:
                damage = self.gun_damage * random.uniform(0.8, 1.2)  # Slight damage variation
                if hasattr(self.player, 'take_damage'):
                    self.player.take_damage(damage)
                    return True
        
        return False  # Miss or no line of sight

    def take_damage(self, amount):
        """
        Take damage and handle death if needed.
        
        Args:
            amount (float): Amount of damage to take
        """
        if self.health <= 0:
            return  # Already dead
            
        self.health -= amount
        self.last_damage_time = time.time()
        
        # Visual feedback
        if not self.is_flashing:
            self.is_flashing = True
            self.color = color.white
            invoke(self._end_hit_flash, delay=self.hit_flash_duration)
            
        if self.hit_sound:
            self.hit_sound.play()
            
        if self.health <= 0:
            self.die()
            
        return self.health

    def _end_hit_flash(self):
        """End the damage visual feedback"""
        self.color = color.red
        self.is_flashing = False

    def die(self):
        """Handle death state"""
        self.health = 0
        self.state = 'dead'
        
        if self.death_sound:
            self.death_sound.play()
            
        # Disable collision
        if hasattr(self, 'collider') and self.collider:
            destroy(self.collider)
            
        # Visual indication of death
        self.animate_position(self.position + Vec3(0, -0.5, 0), duration=0.2)
        self.animate_rotation((80, self.rotation_y, 0), duration=0.3)
        self.color = color.rgba(100, 0, 0, 255)
        
        # Disable gun
        if self.gun:
            self.gun.visible = False
            
        # Create "defeated" text
        Text(text="Defeated!", parent=self, billboard=True, scale=15, color=color.yellow, y=2)
        
        print(f"NPC {self.name} has been defeated!")

    def reset_state(self, position=None, health=None, ammo=None):
        """
        Reset the NPC state for a new training episode or game round.
        
        Args:
            position (Vec3): New position to reset to
            health (float): New health value
            ammo (int): New ammo count
        """
        if position is not None:
            self.position = position
            
        if health is not None:
            self.health = health
            self.max_health = health
            
        if ammo is not None:
            self.ammo = ammo
            self.max_ammo = ammo
            
        # Reset rotation (random or specified)
        self.rotation_y = random.uniform(0, 360)
        
        # Reset timers
        self.last_damage_time = 0
        self.last_shot_time = 0
        
        # Reset state
        self.state = 'idle'
        self.action_history.clear()
        
        # Reset visuals
        self.color = color.red
        self.is_flashing = False
        if self.gun:
            self.gun.visible = True
            
        # Restore collider if needed
        if not hasattr(self, 'collider') or not self.collider:
            self.collider = BoxCollider(self, center=Vec3(0, 0, 0), size=Vec3(1, 2, 1))
            
        print(f"NPC {self.name} reset at {self.position} with {self.health} HP and {self.ammo} ammo")

    def get_observation_info(self):
        """
        Returns a dict of state information for debugging or display.
        """
        return {
            "health": self.health,
            "ammo": self.ammo,
            "position": self.position,
            "state": self.state,
            "last_damage_time": self.last_damage_time,
            "last_shot_time": self.last_shot_time
        }

# For testing as standalone
if __name__ == '__main__':
    app = Ursina()
    
    # Simple test scene
    ground = Entity(model='plane', scale=(100, 1, 100), color=color.gray, texture='white_cube', texture_scale=(100, 100), collider='box')
    
    from player import Player
    player = Player(position=(0, 1, 0))
    
    # Create test NPC
    enemy = EnemyNPC(position=(5, 1, 10), player_ref=player)
    enemy.debug_text.visible = True
    
    def update():
        # Test actions with keyboard
        if held_keys['1']: enemy.apply_action(0)  # Forward 
        if held_keys['2']: enemy.apply_action(1)  # Backward
        if held_keys['3']: enemy.apply_action(2)  # Strafe Left
        if held_keys['4']: enemy.apply_action(3)  # Strafe Right
        if held_keys['5']: enemy.apply_action(4)  # Turn Left
        if held_keys['6']: enemy.apply_action(5)  # Turn Right
        if held_keys['7']: enemy.apply_action(6)  # Shoot
        if held_keys['8']: enemy.apply_action(7)  # Idle
        
    def input(key):
        if key == 't':
            # Test damage
            enemy.take_damage(20)
        if key == 'r':
            # Test reset
            enemy.reset_state(position=Vec3(random.uniform(-10, 10), 1, random.uniform(5, 15)))
            
    Sky()
    
    app.run()
