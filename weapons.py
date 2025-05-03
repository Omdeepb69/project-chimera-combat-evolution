# weapons.py
# Weapon system for Project Chimera Combat Evolution
# Handles different gun types, ammunition, and firing mechanics

from ursina import *
import random
import math

class Weapon(Entity):
    def __init__(self, owner=None, weapon_type="assault_rifle"):
        # Pass owner as position to ensure weapon follows owner
        super().__init__(
            parent=owner,
            position=(0, 0, 0),
            rotation=(0, 0, 0)
        )
        
        self.owner = owner  # Reference to the entity owning this weapon
        self.weapon_type = weapon_type
        
        # Weapon properties based on type
        self.setup_weapon_properties()
        
        # Ammunition state tracking
        self.current_ammo = self.magazine_size
        self.reserve_ammo = self.max_reserve_ammo
        self.is_reloading = False
        
        # Firing state tracking
        self.last_shot_time = 0
        self.can_fire = True
        
        # Create weapon model
        self.create_weapon_model()
        
    def setup_weapon_properties(self):
        # Default properties
        self.damage = 10
        self.fire_rate = 0.1  # Time between shots in seconds
        self.magazine_size = 30
        self.max_reserve_ammo = 90
        self.reload_time = 2.0
        self.accuracy = 0.95  # 0-1, higher is better
        self.range = 100
        self.recoil = 2
        self.weapon_name = "Basic Weapon"
        self.automatic = False
        self.bullet_speed = 300
        self.bullet_drop = 0.01
        self.projectile_count = 1  # For shotguns and spread weapons
        
        # Set properties based on weapon type
        if self.weapon_type == "assault_rifle":
            self.damage = 15
            self.fire_rate = 0.1
            self.magazine_size = 30
            self.max_reserve_ammo = 120
            self.reload_time = 2.0
            self.accuracy = 0.9
            self.range = 80
            self.recoil = 2.5
            self.weapon_name = "Assault Rifle"
            self.automatic = True
            
        elif self.weapon_type == "shotgun":
            self.damage = 8  # Per pellet
            self.fire_rate = 0.8
            self.magazine_size = 8
            self.max_reserve_ammo = 32
            self.reload_time = 3.0
            self.accuracy = 0.7
            self.range = 40
            self.recoil = 5
            self.projectile_count = 8
            self.weapon_name = "Shotgun"
            self.automatic = False
            
        elif self.weapon_type == "sniper":
            self.damage = 90
            self.fire_rate = 1.5
            self.magazine_size = 5
            self.max_reserve_ammo = 30
            self.reload_time = 3.5
            self.accuracy = 0.99
            self.range = 200
            self.recoil = 8
            self.weapon_name = "Sniper Rifle"
            self.automatic = False
            
        elif self.weapon_type == "pistol":
            self.damage = 20
            self.fire_rate = 0.3
            self.magazine_size = 12
            self.max_reserve_ammo = 60
            self.reload_time = 1.5
            self.accuracy = 0.85
            self.range = 50
            self.recoil = 3
            self.weapon_name = "Pistol"
            self.automatic = False
    
    def create_weapon_model(self):
        # Create weapon components based on type
        if hasattr(self, 'model_parts'):
            for part in self.model_parts:
                destroy(part)
        
        self.model_parts = []
        
        # Different models based on weapon type
        if self.weapon_type == "assault_rifle":
            # Main body
            body = Entity(
                parent=self,
                model='cube',
                color=color.dark_gray,
                scale=(0.08, 0.08, 0.6),
                position=(0.3, -0.2, 0.3)
            )
            
            # Barrel
            barrel = Entity(
                parent=self,
                model='cylinder',
                color=color.dark_gray,
                scale=(0.03, 0.3, 0.03),
                rotation=(0, 0, 90),
                position=(0.3, -0.2, 0.6)
            )
            
            # Magazine
            magazine = Entity(
                parent=self,
                model='cube',
                color=color.gray,
                scale=(0.07, 0.2, 0.05),
                position=(0.3, -0.33, 0.3)
            )
            
            # Stock
            stock = Entity(
                parent=self,
                model='cube',
                color=color.dark_gray,
                scale=(0.04, 0.06, 0.15),
                position=(0.3, -0.2, 0.0)
            )
            
            # Sight
            sight = Entity(
                parent=self,
                model='cube',
                color=color.black,
                scale=(0.02, 0.02, 0.1),
                position=(0.3, -0.15, 0.4)
            )
            
            self.model_parts = [body, barrel, magazine, stock, sight]
            
        elif self.weapon_type == "shotgun":
            # Main body
            body = Entity(
                parent=self,
                model='cube',
                color=color.brown,
                scale=(0.08, 0.08, 0.7),
                position=(0.3, -0.2, 0.3)
            )
            
            # Barrel (double barrel)
            barrel1 = Entity(
                parent=self,
                model='cylinder',
                color=color.dark_gray,
                scale=(0.04, 0.35, 0.04),
                rotation=(0, 0, 90),
                position=(0.27, -0.2, 0.6)
            )
            
            barrel2 = Entity(
                parent=self,
                model='cylinder',
                color=color.dark_gray,
                scale=(0.04, 0.35, 0.04),
                rotation=(0, 0, 90),
                position=(0.33, -0.2, 0.6)
            )
            
            # Stock
            stock = Entity(
                parent=self,
                model='cube',
                color=color.brown,
                scale=(0.08, 0.1, 0.25),
                position=(0.3, -0.2, -0.05)
            )
            
            # Pump
            pump = Entity(
                parent=self,
                model='cube',
                color=color.light_gray,
                scale=(0.1, 0.1, 0.15),
                position=(0.3, -0.2, 0.2)
            )
            
            self.model_parts = [body, barrel1, barrel2, stock, pump]
            
        elif self.weapon_type == "sniper":
            # Main body
            body = Entity(
                parent=self,
                model='cube',
                color=color.black,
                scale=(0.07, 0.08, 0.8),
                position=(0.3, -0.2, 0.3)
            )
            
            # Barrel
            barrel = Entity(
                parent=self,
                model='cylinder',
                color=color.dark_gray,
                scale=(0.03, 0.4, 0.03),
                rotation=(0, 0, 90),
                position=(0.3, -0.2, 0.7)
            )
            
            # Scope
            scope = Entity(
                parent=self,
                model='cylinder',
                color=color.black,
                scale=(0.06, 0.15, 0.06),
                rotation=(0, 0, 90),
                position=(0.3, -0.13, 0.4)
            )
            
            # Scope lens (front)
            scope_lens1 = Entity(
                parent=self,
                model='sphere',
                color=color.azure,
                scale=(0.05, 0.01, 0.05),
                position=(0.3, -0.13, 0.48)
            )
            
            # Scope lens (back)
            scope_lens2 = Entity(
                parent=self,
                model='sphere',
                color=color.black,
                scale=(0.03, 0.01, 0.03),
                position=(0.3, -0.13, 0.32)
            )
            
            # Stock
            stock = Entity(
                parent=self,
                model='cube',
                color=color.dark_gray,
                scale=(0.05, 0.1, 0.3),
                position=(0.3, -0.2, 0.0)
            )
            
            # Magazine
            magazine = Entity(
                parent=self,
                model='cube',
                color=color.gray,
                scale=(0.06, 0.15, 0.06),
                position=(0.3, -0.3, 0.25)
            )
            
            self.model_parts = [body, barrel, scope, scope_lens1, scope_lens2, stock, magazine]
            
        elif self.weapon_type == "pistol":