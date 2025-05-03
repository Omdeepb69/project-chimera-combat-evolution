from ursina import *
import numpy as np

class EnemyNPC(Entity):
    def __init__(self, position=(0, 1, 5), player_ref=None, **kwargs):
        super().__init__(model='cube', color=color.red, collider='box', position=position, **kwargs)
        self.health = 100
        self.player = player_ref
        self.speed = 3
        self.target_position = self.position
        self.state = 'idle'  # idle, seeking, attacking, cover

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
        elif action_index == 2:  # Strafe Left
            self.state = 'strafing_left'
            if self.player:
                direction_to_player = (self.player.position - self.position).normalized()
                # Use np.cross instead of the undefined cross function
                strafe_dir = Vec3(*np.cross([direction_to_player.x, direction_to_player.y, direction_to_player.z], 
                                           [0, 1, 0])).normalized()
                self.target_position = self.position - strafe_dir * 2  # Move 2 units left relative to player
        elif action_index == 3:  # Strafe Right
            self.state = 'strafing_right'
            if self.player:
                direction_to_player = (self.player.position - self.position).normalized()
                # Use np.cross instead of the undefined cross function
                strafe_dir = Vec3(*np.cross([direction_to_player.x, direction_to_player.y, direction_to_player.z], 
                                           [0, 1, 0])).normalized()
                self.target_position = self.position + strafe_dir * 2  # Move 2 units right relative to player
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
            print("NPC Shoots at player")
            # Simple damage model
            self.player.health -= 5
            print(f"Player health: {self.player.health}")
            # Add visual effect (e.g., bullet tracer)