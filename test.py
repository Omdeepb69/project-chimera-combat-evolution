from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random
import math

# Initialize the game
app = Ursina()

# Set up window properties
window.title = 'Chimera FPS'
window.fullscreen = False
window.exit_button.visible = False
window.fps_counter.enabled = True

# Global variables
ENEMY_SPEED = 2
BULLET_SPEED = 30
ENEMY_HEALTH = 100
PLAYER_HEALTH = 100
ENEMY_DAMAGE = 10
GAME_OVER = False
SCORE = 0
AMMO = 30
MAX_AMMO = 30
RELOAD_TIME = 2
RELOADING = False
RELOAD_TIMER = 0

# Sky
sky = Sky(texture='sky_default')

# Create ground
ground = Entity(
    model='plane',
    scale=(100, 1, 100),
    color=color.green.tint(-.2),
    texture='white_cube',
    texture_scale=(100, 100),
    collider='box'
)

# Create walls
walls = []
def create_walls():
    # Outer walls
    for i in range(4):
        rotation_y = i * 90
        wall = Entity(
            model='cube',
            scale=(100, 5, 1),
            position=(0, 2.5, 50),
            rotation=(0, rotation_y, 0),
            color=color.gray,
            texture='white_cube',
            texture_scale=(10, 1),
            collider='box'
        )
        walls.append(wall)

    # Add some internal maze-like walls
    for _ in range(15):
        x = random.uniform(-40, 40)
        z = random.uniform(-40, 40)
        length = random.uniform(5, 20)
        rotation_y = random.choice([0, 90])
        wall = Entity(
            model='cube',
            scale=(length, 5, 1),
            position=(x, 2.5, z),
            rotation=(0, rotation_y, 0),
            color=color.gray.tint(random.uniform(-.2, .2)),
            texture='white_cube',
            texture_scale=(length/2, 1),
            collider='box'
        )
        walls.append(wall)

# Create some obstacles/decorations
obstacles = []
def create_obstacles():
    # Create some varied terrain features
    for _ in range(30):
        x = random.uniform(-45, 45)
        z = random.uniform(-45, 45)
        scale_x = random.uniform(1, 5)
        scale_y = random.uniform(1, 3)
        scale_z = random.uniform(1, 5)
        color_value = random.uniform(0.3, 0.8)
        
        # Random shape selection - use only cube and sphere to avoid model issues
        shape = random.choice(['cube', 'sphere'])
        
        obstacle = Entity(
            model=shape,
            scale=(scale_x, scale_y, scale_z),
            position=(x, scale_y/2, z),
            color=color.rgb(color_value, color_value, color_value),
            texture='white_cube',
            collider='box' if shape == 'cube' else 'sphere'
        )
        obstacles.append(obstacle)

# Create player
player = FirstPersonController(
    position=(0, 2, 0),
    speed=10,
    height=2
)

# Player health display
health_bar = Text(text=f"Health: {PLAYER_HEALTH}", x=-0.85, y=0.45)
ammo_text = Text(text=f"Ammo: {AMMO}/{MAX_AMMO}", x=-0.85, y=0.4)
score_text = Text(text=f"Score: {SCORE}", x=0.7, y=0.45)
game_over_text = Text(text="GAME OVER\nPress R to restart", origin=(0, 0), scale=3, color=color.red, visible=False)
reload_text = Text(text="Reloading...", x=-0.85, y=0.35, color=color.orange, visible=False)

# Create gun models
def create_gun_model():
    # Parent entity for the gun
    gun = Entity(parent=camera.ui, position=(0.5, -0.25, 0), scale=0.15)
    
    # Main body of the gun
    gun_body = Entity(
        parent=gun,
        model='cube',
        color=color.dark_gray,
        scale=(3, 1, 1)
    )
    
    # Gun barrel - use cube instead of cylinder to avoid model issues
    gun_barrel = Entity(
        parent=gun,
        model='cube',
        color=color.gray,
        scale=(3, 0.3, 0.3),
        position=(1.8, 0.2, 0)
    )
    
    # Gun handle
    gun_handle = Entity(
        parent=gun,
        model='cube',
        color=color.black,
        scale=(0.8, 1.8, 0.8),
        position=(0, -1.2, 0)
    )
    
    # Gun sight
    gun_sight = Entity(
        parent=gun,
        model='cube',
        color=color.red,
        scale=(0.1, 0.3, 0.1),
        position=(0.8, 0.6, 0)
    )
    
    return gun

# Create a simple crosshair using entities
def create_crosshair():
    # Parent entity for the crosshair
    crosshair_parent = Entity(parent=camera.ui, position=(0, 0, 0))
    
    # Center dot
    center_dot = Entity(
        parent=crosshair_parent,
        model='quad',
        color=color.red,
        scale=0.005
    )
    
    # Horizontal line
    horizontal_line = Entity(
        parent=crosshair_parent,
        model='quad',
        color=color.white,
        scale=(0.02, 0.002)
    )
    
    # Vertical line
    vertical_line = Entity(
        parent=crosshair_parent,
        model='quad',
        color=color.white,
        scale=(0.002, 0.02)
    )
    
    return crosshair_parent

# Create placeholder sound synthesizer
def create_sound_files():
    # Since we can't rely on external audio files, we'll use direct audio synthesis
    # or built-in Ursina sounds if available
    pass

# Enemies
enemies = []
class Enemy(Entity):
    def __init__(self, position):
        super().__init__(
            model='sphere',
            scale=1,
            position=position,
            color=color.red,
            collider='sphere'
        )
        # Add eye to make it look more menacing
        self.eye1 = Entity(
            parent=self,
            model='sphere',
            scale=(0.2, 0.2, 0.1),
            position=(0.3, 0.3, 0.48),
            color=color.yellow
        )
        self.eye2 = Entity(
            parent=self,
            model='sphere',
            scale=(0.2, 0.2, 0.1),
            position=(-0.3, 0.3, 0.48),
            color=color.yellow
        )
        
        # Add horns because it's called "Chimera" - use cubes for horns instead of cylinders
        self.horn1 = Entity(
            parent=self,
            model='cube',
            scale=(0.1, 0.5, 0.1),
            position=(0.3, 0.8, 0),
            rotation=(0, 0, 20),
            color=color.black
        )
        self.horn2 = Entity(
            parent=self,
            model='cube',
            scale=(0.1, 0.5, 0.1),
            position=(-0.3, 0.8, 0),
            rotation=(0, 0, -20),
            color=color.black
        )
        
        # Health properties
        self.max_health = ENEMY_HEALTH
        self.health = self.max_health
        
        # Health bar
        self.health_bar_bg = Entity(
            parent=self,
            model='quad',
            scale=(1.2, 0.1),
            position=(0, 1.2, 0),
            color=color.red,
            billboard=True
        )
        
        self.health_bar = Entity(
            parent=self.health_bar_bg,
            model='quad',
            scale=(1, 0.9),
            position=(-0.5 * (1 - self.health/self.max_health), 0, -0.01),
            color=color.green,
            billboard=True
        )
        
        enemies.append(self)
    
    def update(self):
        global PLAYER_HEALTH, GAME_OVER
        if GAME_OVER:
            return
            
        # Look at player
        self.look_at(player.position, 'forward')
        # Move towards player
        dir_vec = player.position - self.position
        distance = dir_vec.length()
        
        if distance > 2:  # Don't get too close
            dir_vec = dir_vec.normalized()
            new_pos = self.position + dir_vec * ENEMY_SPEED * time.dt
            
            # Collision check with walls
            hit_info = boxcast(
                self.position + Vec3(0, 0.5, 0),
                direction=dir_vec,
                distance=ENEMY_SPEED * time.dt + 0.5,
                ignore=(self,),
                debug=False
            )
            
            if not hit_info.hit:
                self.position = new_pos
        elif distance < 3 and random.random() < 0.01:  # Attack player when close
            PLAYER_HEALTH -= ENEMY_DAMAGE
            health_bar.text = f"Health: {PLAYER_HEALTH}"
            
            if PLAYER_HEALTH <= 0 and not GAME_OVER:
                GAME_OVER = True
                game_over_text.visible = True
                player.speed = 0
                mouse.locked = False
    
    def take_damage(self, damage):
        self.health -= damage
        # Update health bar
        self.health_bar.scale_x = self.health / self.max_health
        self.health_bar.x = -0.5 * (1 - self.health/self.max_health)
        
        if self.health <= 0:
            self.die()
    
    def die(self):
        global SCORE
        SCORE += 10
        score_text.text = f"Score: {SCORE}"
        
        # Simple death animation
        self.animate_scale((0, 0, 0), duration=0.5, curve=curve.out_expo)
        destroy(self, delay=0.5)
        enemies.remove(self)
        
        if len(enemies) < 10:
            spawn_enemy()

# Bullets
bullets = []
class Bullet(Entity):
    def __init__(self, position, direction):
        super().__init__(
            model='sphere',
            scale=0.3,
            position=position,
            color=color.yellow
        )
        self.direction = direction
        self.life_timer = 0
        bullets.append(self)
    
    def update(self):
        # Move bullet
        self.position += self.direction * BULLET_SPEED * time.dt
        self.life_timer += time.dt
        
        # Destroy after 2 seconds
        if self.life_timer > 2:
            self.die()
            return
        
        # Check for collisions with enemies
        for enemy in enemies[:]:
            if (self.position - enemy.position).length() < 1:
                enemy.take_damage(50)
                self.die()
                return
        
        # Check for collisions with walls
        hit_info = boxcast(
            self.position,
            direction=self.direction,
            distance=BULLET_SPEED * time.dt,
            ignore=(self,),
            debug=False
        )
        
        if hit_info.hit:
            # Create spark effect
            for _ in range(10):
                spark = Entity(
                    model='cube',
                    scale=0.1,
                    position=self.position,
                    color=color.yellow,
                    texture='white_cube'
                )
                spark.animate_position(
                    self.position + Vec3(
                        random.uniform(-1, 1),
                        random.uniform(-1, 1),
                        random.uniform(-1, 1)
                    ),
                    duration=0.2,
                    curve=curve.linear
                )
                spark.animate_scale(0, 0.2, curve=curve.linear)
                destroy(spark, delay=0.2)
            
            self.die()
    
    def die(self):
        destroy(self)
        if self in bullets:
            bullets.remove(self)

# Muzzle flash effect
muzzle_flash = Entity(
    parent=camera.ui,
    model='quad',
    scale=0,
    position=(0.7, -0.25, 0),
    color=color.yellow,
    texture='circle'
)

def shoot():
    global AMMO, RELOADING
    
    if GAME_OVER or RELOADING or AMMO <= 0:
        if AMMO <= 0:
            reload()
        return
    
    AMMO -= 1
    ammo_text.text = f"Ammo: {AMMO}/{MAX_AMMO}"
    
    # Shoot a bullet
    bullet_pos = player.position + Vec3(0, 1.8, 0)
    bullet_dir = Vec3(
        math.sin(math.radians(player.rotation.y)),
        math.sin(math.radians(-player.camera_pivot.rotation.x)),
        math.cos(math.radians(player.rotation.y))
    ).normalized()
    
    Bullet(bullet_pos, bullet_dir)
    
    # Gun recoil animation
    gun = camera.ui.children[0]
    gun.animate_position(
        gun.position + Vec3(0, 0.1, 0),
        duration=0.05,
        curve=curve.linear
    )
    gun.animate_position(
        Vec3(0.5, -0.25, 0),
        duration=0.1,
        delay=0.05,
        curve=curve.out_expo
    )
    
    # Muzzle flash
    muzzle_flash.scale = 0.4
    muzzle_flash.visible = True
    muzzle_flash.animate_scale(0, duration=0.05, curve=curve.linear)
    invoke(setattr, muzzle_flash, 'visible', False, delay=0.05)
    
    # Play sound
    play_sound('shoot', volume=0.5)

def reload():
    global RELOADING, RELOAD_TIMER
    
    if RELOADING or AMMO == MAX_AMMO or GAME_OVER:
        return
        
    RELOADING = True
    RELOAD_TIMER = 0
    reload_text.visible = True
    play_sound('reload', volume=0.5)

def spawn_enemy():
    # Find a valid spawn position away from player
    while True:
        x = random.uniform(-45, 45)
        z = random.uniform(-45, 45)
        pos = Vec3(x, 1, z)
        
        # Check if far enough from player
        if (pos - player.position).length() > 15:
            # Check no walls at position
            hit_info = boxcast(
                pos + Vec3(0, 5, 0),
                direction=Vec3(0, -1, 0),
                distance=10,
                ignore=(),
                debug=False
            )
            
            if hit_info.hit and hit_info.entity == ground:
                Enemy(pos)
                break

def restart_game():
    global PLAYER_HEALTH, GAME_OVER, SCORE, AMMO
    
    if not GAME_OVER:
        return
    
    # Reset game variables
    PLAYER_HEALTH = 100
    GAME_OVER = False
    SCORE = 0
    AMMO = MAX_AMMO
    
    # Reset UI
    health_bar.text = f"Health: {PLAYER_HEALTH}"
    ammo_text.text = f"Ammo: {AMMO}/{MAX_AMMO}"
    score_text.text = f"Score: {SCORE}"
    game_over_text.visible = False
    
    # Reset player
    player.position = Vec3(0, 2, 0)
    player.speed = 10
    mouse.locked = True
    
    # Clear enemies and bullets
    for enemy in enemies[:]:
        destroy(enemy)
        enemies.remove(enemy)
    
    for bullet in bullets[:]:
        destroy(bullet)
        bullets.remove(bullet)
    
    # Spawn new enemies
    for _ in range(5):
        spawn_enemy()

def input(key):
    global RELOADING
    
    if key == 'left mouse down' and not GAME_OVER:
        shoot()
    
    if key == 'r' and not RELOADING:
        if GAME_OVER:
            restart_game()
        else:
            reload()
    
    if key == 'escape':
        quit()

def update():
    global RELOADING, RELOAD_TIMER
    
    # Handle reloading
    if RELOADING:
        RELOAD_TIMER += time.dt
        if RELOAD_TIMER >= RELOAD_TIME:
            global AMMO
            AMMO = MAX_AMMO
            RELOADING = False
            RELOAD_TIMER = 0
            reload_text.visible = False
            ammo_text.text = f"Ammo: {AMMO}/{MAX_AMMO}"

# Override Audio class to use built-in sounds
def play_sound(sound_name, volume=0.5):
    if sound_name == 'shoot':
        # Use built-in click sound for shooting
        from ursina.prefabs.ursfx import ursfx
        ursfx([(0.0, 0.0), (0.1, 0.9), (0.15, 0.75), (0.3, 0.14), (0.6, 0.0)], 
              volume=volume, wave='noise', pitch=random.uniform(-13, -12), speed=3.0)
    elif sound_name == 'reload':
        # Use built-in click sound for reloading
        from ursina.prefabs.ursfx import ursfx
        ursfx([(0.0, 0.0), (0.1, 0.5), (0.2, 0.15), (0.7, 0.0)],
              volume=volume, wave='saw', pitch=-20, speed=2.0)

# Initialize the game world
def initialize_game():
    # Create game environment
    create_walls()
    create_obstacles()
    
    # Create gun
    create_gun_model()
    
    # Create sounds
    create_sound_files()
    
    # Create crosshair entity instead of texture
    global crosshair
    crosshair = create_crosshair()
    
    # Spawn initial enemies
    for _ in range(5):
        spawn_enemy()

# Start the game
initialize_game()
app.run()