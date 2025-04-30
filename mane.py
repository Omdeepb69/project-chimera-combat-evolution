from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random
import math
import numpy as np
from collections import deque

app = Ursina()

# Global game settings
GAME_MAP_SIZE = 30
WALL_HEIGHT = 3
MAX_ROUNDS = 5
current_round = 1
player_stats = {'kills': 0, 'deaths': 0, 'accuracy': 0, 'shots_fired': 0, 'shots_hit': 0}
game_over = False
round_in_progress = False
enemy_spawn_positions = []
player_spawn_position = Vec3(0, 1, 0)
bullets = []
hit_markers = []

# Texture and sound assets
gun_model = None
muzzle_flash = None
bullet_hole = None
crosshair = None
Entity(model='sphere', color=color.black, scale=1000, double_sided=True)  # Skybox

# Load textures
wall_texture = load_texture('white_cube')  # Will use default white texture if not found
floor_texture = load_texture('grass')  # Will use default white texture if not found

# Sound effects
shoot_sound = None
hit_sound = None
reload_sound = None

# Weapon class
class Weapon:
    def __init__(self):
        self.name = "Assault Rifle"
        self.damage = 25
        self.fire_rate = 0.1
        self.can_fire = True
        self.last_shot = 0
        self.ammo = 30
        self.max_ammo = 30
        self.reload_time = 2
        self.reloading = False
        self.reload_start_time = 0
        
        # Create weapon model
        self.model = Entity(
            parent=camera.ui,
            model='cube',
            texture=wall_texture,
            scale=(0.6, 0.2, 1),
            position=(0.7, -0.4, 1.5),
            rotation=(-5, -10, 0),
            color=color.dark_gray
        )
        
        # Muzzle flash
        self.muzzle_flash = Entity(
            parent=self.model,
            model='cube',
            scale=(0.1, 0.1, 0.1),
            position=(0, 0, -0.6),
            color=color.yellow,
            enabled=False
        )
        
    def update(self):
        if self.reloading:
            if time.time() - self.reload_start_time >= self.reload_time:
                self.ammo = self.max_ammo
                self.reloading = False
                print("Reload complete")
        
        # Weapon sway
        self.model.rotation = (-5 + math.sin(time.time() * 2) * 2, -10 + math.sin(time.time()) * 2, 0)
        self.model.position = (0.7, -0.4 + math.sin(time.time() * 2) * 0.01, 1.5)
        
    def fire(self):
        if not self.can_fire or self.ammo <= 0 or self.reloading:
            if self.ammo <= 0:
                self.reload()
            return False
        
        self.ammo -= 1
        self.last_shot = time.time()
        self.can_fire = False
        invoke(self.reset_fire, delay=self.fire_rate)
        
        # Animation
        self.model.animate_position((0.7, -0.3, 1.6), duration=0.05, curve=curve.linear)
        self.model.animate_position((0.7, -0.4, 1.5), duration=0.1, delay=0.05, curve=curve.linear)
        
        # Muzzle flash
        self.muzzle_flash.enabled = True
        invoke(setattr, self.muzzle_flash, 'enabled', False, delay=0.05)
        
        # Play sound
        if shoot_sound:
            shoot_sound.play()
            
        # Create bullet for visual effect
        bullet = Entity(model='sphere', color=color.yellow, scale=0.1, position=camera.world_position)
        bullets.append(bullet)
        bullet.animate_position(camera.world_position + camera.forward * 100, duration=0.5, curve=curve.linear)
        destroy(bullet, delay=0.5)
        
        # Ray casting for hit detection
        hit_info = raycast(camera.world_position, camera.forward, distance=100, ignore=[player])
        
        player_stats['shots_fired'] += 1
        
        if hit_info.hit:
            # Create hit marker
            hit_marker = Entity(model='quad', scale=0.2, texture=bullet_hole, position=hit_info.world_point + hit_info.world_normal * 0.01)
            hit_marker.look_at(hit_info.world_point + hit_info.world_normal)
            hit_markers.append(hit_marker)
            destroy(hit_marker, delay=10)
            
            # Check if hit an enemy
            if hasattr(hit_info.entity, 'is_enemy') and hit_info.entity.is_enemy:
                hit_info.entity.health -= self.damage
                player_stats['shots_hit'] += 1
                # Calculate accuracy
                player_stats['accuracy'] = (player_stats['shots_hit'] / player_stats['shots_fired']) * 100
                
                # Hit effect
                hit_info.entity.blink(color.red)
                
                if hit_info.entity.health <= 0:
                    hit_info.entity.die()
                    player_stats['kills'] += 1
        
        return True
    
    def reset_fire(self):
        self.can_fire = True
        
    def reload(self):
        if not self.reloading and self.ammo < self.max_ammo:
            self.reloading = True
            self.reload_start_time = time.time()
            # Play reload animation
            self.model.animate_position((0.7, -0.6, 1.5), duration=0.2, curve=curve.out_sine)
            self.model.animate_rotation((-5, -10, 90), duration=0.2, curve=curve.out_sine)
            
            # Return to original position
            invoke(self.model.animate_position, (0.7, -0.4, 1.5), duration=0.2, delay=self.reload_time - 0.4, curve=curve.out_sine)
            invoke(self.model.animate_rotation, (-5, -10, 0), duration=0.2, delay=self.reload_time - 0.4, curve=curve.out_sine)
            
            # Play sound
            if reload_sound:
                reload_sound.play()

# NPC AI class with adaptive behavior
class AdaptiveNPC(Entity):
    def __init__(self, position, team_id):
        super().__init__(
            model='cube',
            color=color.red if team_id == 1 else color.blue,
            scale=(1, 2, 1),
            position=position,
            collider='box'
        )
        
        # Basic attributes
        self.health = 100
        self.max_health = 100
        self.speed = 5
        self.is_enemy = True
        self.team_id = team_id
        self.alive = True
        self.respawn_time = 5
        self.death_time = 0
        
        # AI behavior attributes
        self.state = 'patrol'  # patrol, engage, retreat, hide
        self.target = None
        self.waypoints = []
        self.current_waypoint = 0
        self.last_seen_player_pos = None
        self.last_seen_player_time = 0
        self.memory_duration = 5  # How long they remember player's position
        
        # Generate random patrol path
        self.generate_patrol_path()
        
        # Learning parameters
        self.aggressiveness = random.uniform(0.3, 0.7)  # How likely to engage vs hide
        self.patience = random.uniform(5, 15)  # How long to wait in hiding
        self.reaction_time = random.uniform(0.5, 1.5)  # How quickly they respond to seeing player
        self.accuracy = random.uniform(0.5, 0.8)  # Hit probability
        self.tactical_preference = random.choice(['flanker', 'rusher', 'camper', 'sniper'])
        
        # Experience memory (for learning)
        self.experience = deque(maxlen=100)
        self.last_position = self.position
        self.stuck_timer = 0
        self.last_fire_time = 0
        self.fire_cooldown = random.uniform(0.8, 2)
        
        # Health bar
        self.health_bar = Entity(parent=self, model='quad', color=color.green, scale=(1.5, 0.1, 0.1), position=(0, 1.2, 0), billboard=True)
        
    def update(self):
        if not self.alive:
            if time.time() - self.death_time >= self.respawn_time and round_in_progress:
                self.respawn()
            return
            
        # Update health bar
        self.health_bar.scale_x = (self.health / self.max_health) * 1.5
        self.health_bar.color = color.lerp(color.red, color.green, self.health/self.max_health)
        
        # Check if stuck
        if (self.position - self.last_position).length() < 0.05:
            self.stuck_timer += time.dt
            if self.stuck_timer > 1.0:
                self.unstuck()
        else:
            self.stuck_timer = 0
            self.last_position = self.position
            
        # Main AI behavior state machine
        if self.state == 'patrol':
            self.patrol_behavior()
            self.look_for_player()
            
        elif self.state == 'engage':
            self.combat_behavior()
            
        elif self.state == 'retreat':
            self.retreat_behavior()
            
        elif self.state == 'hide':
            self.hide_behavior()
            
        # Check if player was seen recently but now lost
        if self.last_seen_player_pos and time.time() - self.last_seen_player_time > self.memory_duration:
            self.last_seen_player_pos = None
            if self.state == 'engage':
                self.state = 'patrol'
                self.generate_patrol_path()
    
    def patrol_behavior(self):
        if not self.waypoints:
            self.generate_patrol_path()
            return
            
        # Move toward current waypoint
        wp = self.waypoints[self.current_waypoint]
        direction = (wp - self.position).normalized()
        self.position += direction * self.speed * time.dt
        self.look_at(wp)
        
        # Check if reached waypoint
        if (self.position - wp).length() < 1:
            self.current_waypoint = (self.current_waypoint + 1) % len(self.waypoints)
    
    def combat_behavior(self):
        if not player.alive or not self.can_see_player():
            # Lost sight of player
            self.last_seen_player_time = time.time()
            
            # Decide to hide or continue searching based on aggressiveness
            if random.random() > self.aggressiveness:
                self.state = 'hide'
                self.find_hiding_spot()
            else:
                if self.last_seen_player_pos:
                    self.move_toward(self.last_seen_player_pos)
                    
        else:
            # Update last seen position
            self.last_seen_player_pos = player.position
            self.last_seen_player_time = time.time()
            
            # Look at player
            self.look_at(player.position)
            
            # Combat tactics based on preference
            if self.tactical_preference == 'flanker':
                # Try to get to player's side
                right_vector = player.right * (5 + random.uniform(-2, 2))
                target_pos = player.position + right_vector
                self.move_toward(target_pos)
                
            elif self.tactical_preference == 'rusher':
                # Move directly toward player
                self.move_toward(player.position)
                
            elif self.tactical_preference == 'camper':
                # Stay put if close enough, otherwise get a bit closer
                distance = (player.position - self.position).length()
                if distance > 15:
                    self.move_toward(player.position, factor=0.5)
                    
            elif self.tactical_preference == 'sniper':
                # Keep distance
                distance = (player.position - self.position).length()
                if distance < 10:
                    # Move away
                    direction = (self.position - player.position).normalized()
                    self.position += direction * self.speed * time.dt
                elif distance > 20:
                    # Move a bit closer
                    self.move_toward(player.position, factor=0.3)
            
            # Fire at player
            if time.time() - self.last_fire_time >= self.fire_cooldown:
                self.fire_at_player()
    
    def retreat_behavior(self):
        if not self.waypoints or self.current_waypoint >= len(self.waypoints):
            self.state = 'hide'
            self.find_hiding_spot()
            return
            
        # Move toward retreat point
        wp = self.waypoints[self.current_waypoint]
        self.move_toward(wp)
        
        # Check if reached waypoint
        if (self.position - wp).length() < 1:
            self.current_waypoint += 1
            if self.current_waypoint >= len(self.waypoints):
                self.state = 'hide'
                self.health += 20  # Recover some health when successfully retreated
                self.health = min(self.health, self.max_health)
    
    def hide_behavior(self):
        # If hidden for long enough, go back to patrol
        if not hasattr(self, 'hiding_start_time'):
            self.hiding_start_time = time.time()
            
        if time.time() - self.hiding_start_time > self.patience:
            self.state = 'patrol'
            self.generate_patrol_path()
            return
            
        # Check if player is visible while hiding
        if self.can_see_player():
            # Decide to engage based on aggressiveness and health
            health_factor = self.health / self.max_health
            engage_probability = self.aggressiveness * health_factor
            
            if random.random() < engage_probability:
                self.state = 'engage'
    
    def look_for_player(self):
        if self.can_see_player():
            # React based on reaction time
            if not hasattr(self, 'player_spotted_time'):
                self.player_spotted_time = time.time()
                
            if time.time() - self.player_spotted_time >= self.reaction_time:
                self.state = 'engage'
                self.last_seen_player_pos = player.position
                self.last_seen_player_time = time.time()
        else:
            # Reset spotted time if player not visible
            if hasattr(self, 'player_spotted_time'):
                delattr(self, 'player_spotted_time')
    
    def can_see_player(self):
        if not player.alive:
            return False
            
        # Check if player is within line of sight
        direction = player.position - self.position
        distance = direction.length()
        
        if distance > 30:  # Max vision range
            return False
            
        # Ray cast to check for obstacles
        hit_info = raycast(self.position + Vec3(0, 0.5, 0), direction.normalized(), distance=distance, ignore=[self])
        
        # Check if the hit entity is the player
        if hit_info.hit:
            return hit_info.entity == player
        
        return False
    
    def move_toward(self, target_pos, factor=1.0):
        direction = (target_pos - self.position).normalized()
        self.position += direction * self.speed * factor * time.dt
        self.look_at(target_pos)
        
        # Simple collision avoidance
        for wall in walls:
            if (self.position - wall.position).length() < 1.5:
                push_dir = (self.position - wall.position).normalized()
                self.position += push_dir * self.speed * time.dt
    
    def generate_patrol_path(self):
        # Generate random patrol points within the map
        self.waypoints = []
        num_points = random.randint(3, 6)
        
        for _ in range(num_points):
            x = random.uniform(-GAME_MAP_SIZE/2 + 2, GAME_MAP_SIZE/2 - 2)
            z = random.uniform(-GAME_MAP_SIZE/2 + 2, GAME_MAP_SIZE/2 - 2)
            self.waypoints.append(Vec3(x, 1, z))
            
        self.current_waypoint = 0
    
    def find_hiding_spot(self):
        # Find a wall to hide behind relative to player position
        best_spot = None
        best_score = 0
        
        # Check each wall as potential hiding spot
        for wall in walls:
            # Skip if too close to player
            if (wall.position - player.position).length() < 5:
                continue
                
            # Calculate how well this wall blocks line of sight to player
            player_to_wall = wall.position - player.position
            wall_to_self = self.position - wall.position
            
            # Prefer walls where player->wall and wall->self point in similar directions
            # (meaning the wall is between player and self)
            alignment = player_to_wall.normalized().dot(wall_to_self.normalized())
            distance_factor = 1.0 / (1.0 + (wall.position - self.position).length() * 0.1)
            
            score = alignment * distance_factor
            
            if score > best_score:
                best_score = score
                # Position slightly away from wall
                best_spot = wall.position + (wall.position - player.position).normalized() * 2
                
        if best_spot:
            self.waypoints = [best_spot]
            self.current_waypoint = 0
        else:
            # If no good hiding spot, just retreat away from player
            retreat_dir = (self.position - player.position).normalized()
            retreat_point = self.position + retreat_dir * 10
            self.waypoints = [retreat_point]
            self.current_waypoint = 0
            
        self.hiding_start_time = time.time()
    
    def fire_at_player(self):
        self.last_fire_time = time.time()
        
        # Visual effect of firing
        muzzle = Entity(model='sphere', color=color.yellow, scale=0.3, position=self.position + Vec3(0, 0.5, 0))
        destroy(muzzle, delay=0.05)
        
        # Create bullet effect
        direction = (player.position - self.position).normalized()
        bullet = Entity(model='sphere', color=color.yellow, scale=0.1, position=self.position + Vec3(0, 0.5, 0))
        bullet.animate_position(self.position + direction * 100, duration=0.5, curve=curve.linear)
        destroy(bullet, delay=0.5)
        
        # Hit calculation based on accuracy
        hit_chance = self.accuracy
        distance_factor = 1.0 / (1.0 + (player.position - self.position).length() * 0.05)
        final_hit_chance = hit_chance * distance_factor
        
        if random.random() < final_hit_chance and player.alive:
            player.take_damage(10)  # Deal damage
            
        # Record experience from this action
        self.record_experience({
            'action': 'fire',
            'hit': random.random() < final_hit_chance,
            'distance': (player.position - self.position).length(),
            'player_moving': player.velocity.length() > 0.1
        })
    
    def record_experience(self, data):
        # Store experience data for learning
        self.experience.append(data)
        
        # If we have enough data, maybe adapt behavior
        if len(self.experience) >= 5 and random.random() < 0.2:
            self.adapt_behavior()
    
    def adapt_behavior(self):
        # Analyze recent experiences to improve behavior
        hits = 0
        misses = 0
        distances = []
        player_movement = 0
        
        for exp in self.experience:
            if exp['action'] == 'fire':
                if exp['hit']:
                    hits += 1
                else:
                    misses += 1
                distances.append(exp['distance'])
                if exp['player_moving']:
                    player_movement += 1
        
        total_shots = hits + misses
        if total_shots > 0:
            hit_rate = hits / total_shots
            avg_distance = sum(distances) / len(distances) if distances else 0
            player_moves_factor = player_movement / len(self.experience)
            
            # Adjust accuracy based on performance
            if hit_rate < 0.3:
                # Struggling to hit, increase accuracy
                self.accuracy = min(0.9, self.accuracy + 0.05)
            elif hit_rate > 0.7:
                # Too accurate, make it more challenging
                self.accuracy = max(0.4, self.accuracy - 0.02)
            
            # Adjust tactical preference based on distance
            if avg_distance < 8:
                # Close combat, prefer rushing or flanking
                if random.random() < 0.6:
                    self.tactical_preference = random.choice(['rusher', 'flanker'])
            elif avg_distance > 15:
                # Long distance, prefer camping or sniping
                if random.random() < 0.6:
                    self.tactical_preference = random.choice(['camper', 'sniper'])
            
            # Adjust aggressiveness based on player movement
            if player_moves_factor > 0.7:
                # Player moves a lot, be more aggressive
                self.aggressiveness = min(0.9, self.aggressiveness + 0.05)
            elif player_moves_factor < 0.3:
                # Player is stationary, be more strategic
                self.aggressiveness = max(0.2, self.aggressiveness - 0.03)
    
    def die(self):
        if not self.alive:
            return
            
        self.alive = False
        self.death_time = time.time()
        self.visible = False
        self.collider = None
        
        # Death effect
        Entity(model='sphere', color=color.red, position=self.position, scale=0.1).animate_scale(3, duration=0.3)
        Entity(model='sphere', color=color.red, position=self.position, scale=0.1).animate_scale(2, duration=0.2)
        
        # Learn from death
        self.record_experience({
            'action': 'died',
            'killer_position': player.position,
            'distance': (player.position - self.position).length(),
            'time_alive': time.time() - (self.respawn_time if hasattr(self, 'last_respawn') else 0)
        })
        
        # Improve for next spawn
        self.adapt_after_death()
    
    def adapt_after_death(self):
        # Make smarter choices next time
        
        # Slightly randomize attributes to try new strategies
        self.aggressiveness = max(0.1, min(0.9, self.aggressiveness + random.uniform(-0.2, 0.2)))
        self.patience = max(3, min(20, self.patience + random.uniform(-2, 2)))
        self.reaction_time = max(0.3, min(2.0, self.reaction_time * random.uniform(0.8, 1.2)))
        
        # Sometimes completely change tactical preference
        if random.random() < 0.3:
            self.tactical_preference = random.choice(['flanker', 'rusher', 'camper', 'sniper'])
    
    def respawn(self):
        self.alive = True
        self.health = self.max_health
        self.visible = True
        self.collider = 'box'
        
        # Choose a spawn point away from player
        possible_spawns = [p for p in enemy_spawn_positions 
                          if (p - player.position).length() > 10]
        
        if not possible_spawns:
            possible_spawns = enemy_spawn_positions
            
        spawn_point = random.choice(possible_spawns)
        self.position = spawn_point
        
        # Reset state
        self.state = 'patrol'
        self.generate_patrol_path()
        self.last_respawn = time.time()
    
    def take_damage(self, amount):
        if not self.alive:
            return
            
        self.health -= amount
        self.blink(color.red)
        
        # Change behavior based on health
        if self.health < 30:
            # Low health, retreat
            self.state = 'retreat'
            self.find_retreat_path()
        elif random.random() < 0.3:
            # Sometimes change tactic when hit
            self.state = random.choice(['engage', 'retreat', 'hide'])
            if self.state == 'retreat':
                self.find_retreat_path()
            elif self.state == 'hide':
                self.find_hiding_spot()
        
        if self.health <= 0:
            self.die()
    
    def find_retreat_path(self):
        # Find path away from player toward health or safety
        retreat_dir = (self.position - player.position).normalized()
        
        # Generate a few waypoints in retreat direction
        self.waypoints = []
        current_pos = self.position
        
        for i in range(3):
            # Add some randomness to prevent predictable retreat
            random_offset = Vec3(
                random.uniform(-3, 3),
                0,
                random.uniform(-3, 3)
            )
            
            next_pos = current_pos + retreat_dir * 5 + random_offset
            # Ensure within map bounds
            next_pos.x = max(min(next_pos.x, GAME_MAP_SIZE/2 - 2), -GAME_MAP_SIZE/2 + 2)
            next_pos.z = max(min(next_pos.z, GAME_MAP_SIZE/2 - 2), -GAME_MAP_SIZE/2 + 2)
            
            self.waypoints.append(next_pos)
            current_pos = next_pos
            
        self.current_waypoint = 0
        
    def unstuck(self):
        # Get unstuck by moving in a random direction
        random_dir = Vec3(
            random.uniform(-1, 1),
            0,
            random.uniform(-1, 1)
        ).normalized()
        
        self.position += random_dir * self.speed * 2 * time.dt
        self.stuck_timer = 0

# Enhanced FPS player with health and respawn
class FPSPlayer(FirstPersonController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.gun = Weapon()
        self.health = 100
        self.max_health = 100
        self.alive = True
        self.deaths = 0
        self.respawn_time = 3
        self.death_time = 0
        
        # Health UI
        self.health_bar = Entity(parent=camera.ui, model='quad', color=color.green, 
                              scale=(0.4, 0.02), position=(0, -0.45))
        
        # Ammo counter
        self.ammo_text = Text(parent=camera.ui, text='30/30', position=(0.4, -0.45),
                             color=color.white, scale=1.5)
        
        # Crosshair
        self.crosshair = Entity(parent=camera.ui, model='quad', scale=0.01, color=color.white)
        
        # Stats
        self.stats_text = Text(parent=camera.ui, text='Kills: 0', position=(-0.6, 0.45),
                             scale=1.2, color=color.white)
        
        # Game messages
        self.message_text = Text(parent=camera.ui, text='', position=(0, 0.3),
                                color=color.white, scale=2, origin=(0,0))
        self.message_text.visible = False
        
    def update(self):
        if not self.alive:
            if time.time() - self.death_time >= self.respawn_time and round_in_progress:
                self.respawn()
            return
            
        super().update()
        
        # Update gun
        self.gun.update()
        
        # Update UI
        self.health_bar.scale_x = (self.health / self.max_health) * 0.4
        self.health_bar.color = color.lerp(color.red, color.green, self.health/self.max_health)
        self.ammo_text.text = f'{self.gun.ammo}/{self.gun.max_ammo}'
        self.stats_text.text = f'Kills: {player_stats["kills"]} | Deaths: {player_stats["deaths"]}\nAccuracy: {player_stats["accuracy"]:.1f}%\nRound: {current_round}/{MAX_ROUNDS}'
        
        # Fire gun
        if mouse.left and self.gun.can_fire and self.alive:
            self.gun.fire()
            
        # Reload
        if held_keys['r'] and not self.gun.reloading:
            self.gun.reload()
        
    def take_damage(self, amount):
        if not self.alive:
            return
            
        self.health -= amount
        camera.shake(duration=0.2, magnitude=0.1)
        
        # Red flash effect for damage
        damage_flash = Entity(parent=camera.ui, model='quad', color=color.red, scale_x=2, scale_y=1)
        damage_flash.animate_color(color.rgba(255, 0, 0, 0), duration=0.2)
        destroy(damage_flash, delay=0.2)
        
        if self.health <= 0:
            self.die()
    
    def die(self):
        if not self.alive:
            return
            
        self.alive = False
        self.death_time = time.time()
