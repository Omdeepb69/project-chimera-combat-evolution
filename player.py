from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController

class Player(FirstPersonController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.health = 100
        self.cursor = Entity(parent=camera.ui, model='quad', color=color.white, scale=.008, rotation_z=45)

    def shoot(self):
        print("Player shoots")
        hit_info = raycast(self.world_position + self.camera_pivot.up * 1.5, self.forward, distance=100, ignore=[self])
        if hit_info.hit and hasattr(hit_info.entity, 'health'):
            hit_info.entity.health -= 10
            print(f"Hit {hit_info.entity.name}, health: {hit_info.entity.health}")
            # Add visual effect (e.g., bullet impact)
            impact = Entity(model='sphere', scale=0.2, color=color.yellow, position=hit_info.world_point)
            destroy(impact, delay=0.1)  # Destroy after a short time

    def update(self):
        super().update()  # Call the FirstPersonController update method
        # Add any additional player update logic here