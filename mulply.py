import sys
import socket
import pickle
import random
import time
import threading
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from ursina.prefabs.health_bar import HealthBar
from ursina.shaders import lit_with_shadows_shader

# Network Constants
PORT = 5555
HEADER_SIZE = 10
SERVER_TICK_RATE = 60  # Server updates per second
MAX_PLAYERS = 10

# Game Constants
TEAM_RED = 0
TEAM_BLUE = 1
TEAM_NAMES = ["RED", "BLUE"]
TEAM_COLORS = {
    TEAM_RED: color.red,
    TEAM_BLUE: color.blue
}

ROLES = {
    "ASSAULT": {
        "health": 100,
        "speed": 5,
        "damage": 20,
        "fire_rate": 0.2,
        "weapon_range": 50,
        "model_scale": 0.15,
        "description": "Balanced fighter with automatic rifle"
    },
    "SNIPER": {
        "health": 75,
        "speed": 4,
        "damage": 90,
        "fire_rate": 1.5,
        "weapon_range": 200,
        "model_scale": 0.18,
        "description": "Long-range specialist with high damage"
    },
    "SHOTGUN": {
        "health": 125,
        "speed": 3.5,
        "damage": 80,
        "fire_rate": 1.0,
        "weapon_range": 20,
        "model_scale": 0.14,
        "description": "Close-range powerhouse with wide spread"
    },
    "FLANKER": {
        "health": 80,
        "speed": 7,
        "damage": 15,
        "fire_rate": 0.15,
        "weapon_range": 30,
        "model_scale": 0.13,
        "description": "Fast mover with SMG for surprise attacks"
    }
}

MAPS = {
    "WAREHOUSE": {
        "size": (100, 20, 100),
        "obstacles": 20,
        "description": "Indoor map with crates and corridors"
    },
    "JUNGLE": {
        "size": (120, 25, 120),
        "obstacles": 30,
        "description": "Dense vegetation with hills and trenches"
    },
    "URBAN": {
        "size": (150, 30, 150),
        "obstacles": 40,
        "description": "City blocks with buildings and alleyways"
    },
    "FACILITY": {
        "size": (80, 15, 80),
        "obstacles": 25,
        "description": "Laboratory complex with tight spaces"
    }
}

MATCH_DURATIONS = {
    "5 Minutes": 300,
    "10 Minutes": 600,
    "15 Minutes": 900,
    "20 Minutes": 1200
}

# Game State
class GameState:
    def __init__(self):
        self.players = {}  # {player_id: {"position": Vec3, "rotation": Vec3, "team": team_id, "role": role_name, "health": health, "name": name}}
        self.projectiles = []  # [{position, velocity, owner_id, damage, remaining_range}]
        self.scores = {TEAM_RED: 0, TEAM_BLUE: 0}
        self.map_name = "WAREHOUSE"
        self.match_time = 600  # 10 minutes default
        self.match_start_time = 0
        self.match_active = False
        self.obstacles = []  # [{position, scale, color}]

# Network Message Types
MSG_JOIN = "JOIN"  # Client sends name to join server
MSG_ACCEPT = "ACCEPT"  # Server accepts client and assigns ID
MSG_REJECT = "REJECT"  # Server rejects client
MSG_UPDATE = "UPDATE"  # Server sends game state update
MSG_MOVE = "MOVE"  # Client sends movement data
MSG_SHOOT = "SHOOT"  # Client sends shoot action
MSG_CHAT = "CHAT"  # Chat message
MSG_TEAM_SELECT = "TEAM"  # Client selects team
MSG_ROLE_SELECT = "ROLE"  # Client selects role
MSG_START_GAME = "START"  # Host starts the game
MSG_END_GAME = "END"  # Game ends
MSG_SETUP = "SETUP"  # Host sets up game parameters
MSG_DISCONNECT = "DISCONNECT"  # Client disconnects
MSG_HIT = "HIT"  # Player was hit

# UI Helper Functions
def create_menu_button(text, position, scale=(0.3, 0.05), on_click=None):
    """Creates a standard button for menus"""
    button = Button(
        text=text,
        position=position,
        scale=scale,
        color=color.dark_gray,
        highlight_color=color.light_gray,
        text_color=color.white
    )
    if on_click:
        button.on_click = on_click
    return button

def create_menu_text(text, position, scale=1, color=color.white):
    """Creates text for menus"""
    return Text(
        text=text,
        position=position,
        scale=scale,
        color=color,
        origin=(0, 0)
    )

# Main Game Class
class Chimera(Entity):
    def __init__(self):
        super().__init__()
        
        # Initialize Ursina window
        window.title = "Chimera"
        window.borderless = False
        window.fullscreen = False
        window.exit_button.visible = False
        window.fps_counter.enabled = True
        
        # Game state
        self.game_state = GameState()
        self.player_id = None
        self.player_name = ""
        self.team = None
        self.role = None
        self.player_entity = None
        self.players_entities = {}
        self.projectile_entities = []
        self.is_host = False
        self.network_thread = None
        self.server_thread = None
        self.server_socket = None
        self.client_socket = None
        self.room_id = None
        self.server_ip = None
        self.bullet_cooldown = 0
        self.hit_markers = []
        self.kills = 0
        self.deaths = 0
        
        # UI elements
        self.main_menu = None
        self.role_selection_menu = None
        self.team_selection_menu = None
        self.host_setup_menu = None
        self.scoreboard = None
        self.game_hud = None
        self.chat_box = None
        
        # Create main menu
        self.create_main_menu()
        
        # Setup lighting
        self.directional_light = DirectionalLight()
        self.directional_light.look_at(Vec3(1, -1, 1))
        
        # Setup sky
        self.sky = Sky()
        
        # Set up mouse
        mouse.locked = False
        mouse.visible = True
        
        # Create crosshair
        self.crosshair = Entity(
            model='quad',
            parent=camera.ui,
            scale=.008,
            color=color.white,
            texture='circle',
            visible=False
        )
        
    def create_main_menu(self):
        """Create the main menu UI"""
        # First destroy any existing UI
        if self.main_menu:
            destroy(self.main_menu)
        
        self.main_menu = Entity(parent=camera.ui)
        
        # Title
        Text(
            "CHIMERA",
            parent=self.main_menu,
            scale=3,
            origin=(0, 0),
            y=0.3,
            color=color.yellow
        )
        
        # Name input
        self.name_input = InputField(
            parent=self.main_menu,
            y=0.1,
            placeholder="Enter your name",
            character_limit=15
        )
        
        # Host button
        self.host_button = create_menu_button(
            "HOST GAME",
            (0, -0.05),
            on_click=self.host_game
        )
        self.host_button.parent = self.main_menu
        
        # Join button
        self.join_button = create_menu_button(
            "JOIN GAME",
            (0, -0.15),
            on_click=self.show_join_menu
        )
        self.join_button.parent = self.main_menu
        
        # Quit button
        self.quit_button = create_menu_button(
            "QUIT",
            (0, -0.25),
            on_click=self.quit_game
        )
        self.quit_button.parent = self.main_menu
        
        # Version info
        Text(
            "Chimera v1.0",
            parent=self.main_menu,
            position=(0, -0.45),
            scale=0.7,
            color=color.gray
        )
        
    def show_join_menu(self):
        """Show the menu for joining a game"""
        destroy(self.main_menu)
        
        self.join_menu = Entity(parent=camera.ui)
        
        Text(
            "JOIN GAME",
            parent=self.join_menu,
            scale=2,
            origin=(0, 0),
            y=0.3,
            color=color.yellow
        )
        
        # Server IP input
        Text(
            "Server IP:",
            parent=self.join_menu,
            position=(-0.15, 0.1),
            scale=1,
            origin=(0, 0)
        )
        
        self.ip_input = InputField(
            parent=self.join_menu,
            position=(0.1, 0.1),
            scale=(0.3, 0.05),
            placeholder="192.168.1.x"
        )
        
        # Room ID input
        Text(
            "Room ID:",
            parent=self.join_menu,
            position=(-0.15, 0),
            scale=1,
            origin=(0, 0)
        )
        
        self.room_id_input = InputField(
            parent=self.join_menu,
            position=(0.1, 0),
            scale=(0.3, 0.05),
            placeholder="12345"
        )
        
        # Connect button
        self.connect_button = create_menu_button(
            "CONNECT",
            (0, -0.15),
            on_click=self.connect_to_game
        )
        self.connect_button.parent = self.join_menu
        
        # Back button
        self.back_button = create_menu_button(
            "BACK",
            (0, -0.25),
            on_click=self.back_to_main_menu
        )
        self.back_button.parent = self.join_menu
        
    def back_to_main_menu(self):
        """Return to main menu"""
        if hasattr(self, 'join_menu'):
            destroy(self.join_menu)
        if hasattr(self, 'host_setup_menu'):
            destroy(self.host_setup_menu)
        if hasattr(self, 'team_selection_menu'):
            destroy(self.team_selection_menu)
        if hasattr(self, 'role_selection_menu'):
            destroy(self.role_selection_menu)
        
        self.create_main_menu()
    
    def host_game(self):
        """Show host setup menu"""
        if not self.name_input.text.strip():
            print("Please enter a name first")
            return
            
        self.player_name = self.name_input.text.strip()
        self.is_host = True
        destroy(self.main_menu)
        
        self.host_setup_menu = Entity(parent=camera.ui)
        
        # Title
        Text(
            "HOST GAME SETUP",
            parent=self.host_setup_menu,
            scale=2,
            origin=(0, 0),
            y=0.4,
            color=color.yellow
        )
        
        # --- Improved Map Selector ---
        self.selected_map = list(MAPS.keys())[0]
        def show_map_dropdown():
            self.map_dropdown_list.enabled = not self.map_dropdown_list.enabled
        self.map_selector_btn = Button(
            text=f"{self.selected_map} ({MAPS[self.selected_map]['description']})",
            parent=self.host_setup_menu,
            position=(0.1, 0.25),
            scale=(0.5, 0.06),
            color=color.rgba(30, 30, 30, 220),
            text_color=color.white,
            highlight_color=color.azure,
            font='VeraMono.ttf',
            border=(0.005, 0.005),
            border_color=color.yellow,
            on_click=show_map_dropdown
        )
        self.map_dropdown_list = Entity(parent=self.host_setup_menu, enabled=False)
        for i, map_name in enumerate(MAPS.keys()):
            b = Button(
                text=f"{map_name} ({MAPS[map_name]['description']})",
                parent=self.map_dropdown_list,
                position=(0.1, 0.19 - i*0.06),
                scale=(0.5, 0.06),
                color=color.rgba(50, 50, 50, 240),
                text_color=color.white,
                highlight_color=color.azure,
                font='VeraMono.ttf',
                border=(0.005, 0.005),
                border_color=color.yellow,
                on_click=lambda m=map_name: self.select_map_option(m)
            )
        def hide_map_dropdown():
            self.map_dropdown_list.enabled = False
        self.map_dropdown_list.on_mouse_exit = hide_map_dropdown

        # --- Improved Time Selector ---
        self.selected_time = "5 Minutes"
        def show_time_dropdown():
            self.time_dropdown_list.enabled = not self.time_dropdown_list.enabled
        self.time_selector_btn = Button(
            text=self.selected_time,
            parent=self.host_setup_menu,
            position=(0.1, 0.15),
            scale=(0.3, 0.06),
            color=color.rgba(30, 30, 30, 220),
            text_color=color.white,
            highlight_color=color.azure,
            font='VeraMono.ttf',
            border=(0.005, 0.005),
            border_color=color.yellow,
            on_click=show_time_dropdown
        )
        self.time_dropdown_list = Entity(parent=self.host_setup_menu, enabled=False)
        for i, t in enumerate(MATCH_DURATIONS.keys()):
            b = Button(
                text=t,
                parent=self.time_dropdown_list,
                position=(0.1, 0.09 - i*0.06),
                scale=(0.3, 0.06),
                color=color.rgba(50, 50, 50, 240),
                text_color=color.white,
                highlight_color=color.azure,
                font='VeraMono.ttf',
                border=(0.005, 0.005),
                border_color=color.yellow,
                on_click=lambda tt=t: self.select_time_option(tt)
            )
        def hide_time_dropdown():
            self.time_dropdown_list.enabled = False
        self.time_dropdown_list.on_mouse_exit = hide_time_dropdown

        # Room ID display
        self.room_id = random.randint(10000, 99999)
        
        Text(
            f"ROOM ID: {self.room_id}",
            parent=self.host_setup_menu,
            position=(0, 0.05),
            scale=1.5,
            origin=(0, 0),
            color=color.green
        )
        
        # IP display
        hostname = socket.gethostname()
        self.server_ip = socket.gethostbyname(hostname)
        
        Text(
            f"YOUR IP: {self.server_ip}",
            parent=self.host_setup_menu,
            position=(0, -0.05),
            scale=1,
            origin=(0, 0),
            color=color.yellow
        )
        
        Text(
            "Share IP and Room ID with players",
            parent=self.host_setup_menu,
            position=(0, -0.1),
            scale=0.8,
            origin=(0, 0),
            color=color.gray
        )
        
        # Create server button
        self.create_server_button = create_menu_button(
            "CREATE SERVER",
            (0, -0.2),
            scale=(0.3, 0.05),
            on_click=self.create_server
        )
        self.create_server_button.parent = self.host_setup_menu
        
        # Back button
        self.back_button = create_menu_button(
            "BACK",
            (0, -0.3),
            scale=(0.3, 0.05),
            on_click=self.back_to_main_menu
        )
        self.back_button.parent = self.host_setup_menu
    
    def select_map_option(self, map_name):
        self.selected_map = map_name
        self.map_selector_btn.text = f"{map_name} ({MAPS[map_name]['description']})"
        self.map_dropdown_list.enabled = False

    def select_time_option(self, time_name):
        self.selected_time = time_name
        self.time_selector_btn.text = time_name
        self.time_dropdown_list.enabled = False

    def create_server(self):
        """Start server and proceed to team selection"""
        # Get selected map and time
        selected_map = getattr(self, 'selected_map', None)
        selected_time = getattr(self, 'selected_time', None)
        if not selected_map:
            import random
            selected_map = random.choice(list(MAPS.keys()))
        if not selected_time:
            selected_time = "5 Minutes"
        # Set game parameters
        self.game_state.map_name = selected_map
        self.game_state.match_time = MATCH_DURATIONS[selected_time]
        
        # Start server
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((self.server_ip, PORT))
            self.server_socket.listen(MAX_PLAYERS)
            
            # Start server thread
            self.server_thread = threading.Thread(target=self.run_server)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            print(f"Server started on {self.server_ip}:{PORT}")
            
            # Connect to own server
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.server_ip, PORT))
            
            # Join as host
            join_data = {
                "type": MSG_JOIN,
                "name": self.player_name,
                "room_id": self.room_id,
                "is_host": True
            }
            self.send_to_server(join_data)
            
            # Start client thread
            self.network_thread = threading.Thread(target=self.client_receive)
            self.network_thread.daemon = True
            self.network_thread.start()
            
            # Show team selection
            self.show_team_selection()
            
        except Exception as e:
            print(f"Error creating server: {e}")
            # Show error message
            Text(
                f"Error: {str(e)}",
                parent=self.host_setup_menu,
                position=(0, -0.4),
                scale=1,
                color=color.red,
                origin=(0, 0)
            )
    
    def connect_to_game(self):
        """Connect to an existing game server"""
        if not self.name_input.text.strip():
            print("Please enter a name first")
            return
            
        self.player_name = self.name_input.text.strip()
        self.server_ip = self.ip_input.text.strip()
        self.room_id = self.room_id_input.text.strip()
        
        if not self.server_ip or not self.room_id:
            print("Please enter server IP and Room ID")
            return
            
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.server_ip, PORT))
            
            # Join as client
            join_data = {
                "type": MSG_JOIN,
                "name": self.player_name,
                "room_id": self.room_id,
                "is_host": False
            }
            self.send_to_server(join_data)
            
            # Start client thread
            self.network_thread = threading.Thread(target=self.client_receive)
            self.network_thread.daemon = True
            self.network_thread.start()
            
            # Show team selection
            self.show_team_selection()
            
        except Exception as e:
            print(f"Error connecting to server: {e}")
            # Show error message
            Text(
                f"Error: {str(e)}",
                parent=self.join_menu,
                position=(0, -0.4),
                scale=1,
                color=color.red,
                origin=(0, 0)
            )
    
    def show_team_selection(self):
        """Show the team selection menu"""
        # Clean up previous menus
        if hasattr(self, 'join_menu'):
            destroy(self.join_menu)
        if hasattr(self, 'host_setup_menu'):
            destroy(self.host_setup_menu)
            
        self.team_selection_menu = Entity(parent=camera.ui)
        
        # Title
        Text(
            "SELECT TEAM",
            parent=self.team_selection_menu,
            scale=2,
            origin=(0, 0),
            y=0.3,
            color=color.yellow
        )
        
        # Team Red button
        self.red_team_button = Button(
            text="TEAM RED",
            parent=self.team_selection_menu,
            position=(-0.2, 0),
            scale=(0.3, 0.15),
            color=color.red.tint(-.3),
            highlight_color=color.red,
            on_click=lambda: self.select_team(TEAM_RED)
        )
        
        # Team Blue button
        self.blue_team_button = Button(
            text="TEAM BLUE",
            parent=self.team_selection_menu,
            position=(0.2, 0),
            scale=(0.3, 0.15),
            color=color.blue.tint(-.3),
            highlight_color=color.blue,
            on_click=lambda: self.select_team(TEAM_BLUE)
        )
        
        # Player list
        Text(
            "PLAYERS:",
            parent=self.team_selection_menu,
            position=(-0.4, -0.15),
            scale=1,
            origin=(-0.5, 0)
        )
        
        self.player_list = Entity(parent=self.team_selection_menu)
        self.update_player_list()
        
        # Host controls
        if self.is_host:
            self.start_game_button = create_menu_button(
                "START GAME",
                (0, -0.4),
                scale=(0.3, 0.05),
                on_click=self.start_game
            )
            self.start_game_button.parent = self.team_selection_menu
    
    def update_player_list(self):
        """Update the displayed player list"""
        # Only update if player_list UI exists
        if not hasattr(self, 'player_list') or self.player_list is None:
            return
        # Clear existing list
        for child in self.player_list.children:
            destroy(child)
        # Add players to list
        red_y = 0
        blue_y = 0
        Text(
            "RED TEAM",
            parent=self.player_list,
            position=(-0.3, -0.2),
            scale=0.8,
            color=color.red,
            origin=(0, 0)
        )
        Text(
            "BLUE TEAM",
            parent=self.player_list,
            position=(0.3, -0.2),
            scale=0.8,
            color=color.blue,
            origin=(0, 0)
        )
        for player_id, player_data in self.game_state.players.items():
            name = player_data.get("name", "Unknown")
            team = player_data.get("team")
            role = player_data.get("role", "")
            if team == TEAM_RED:
                Text(
                    f"{name} ({role})" if role else name,
                    parent=self.player_list,
                    position=(-0.3, -0.25 - (red_y * 0.04)),
                    scale=0.7,
                    color=color.white,
                    origin=(0, 0)
                )
                red_y += 1
            elif team == TEAM_BLUE:
                Text(
                    f"{name} ({role})" if role else name,
                    parent=self.player_list,
                    position=(0.3, -0.25 - (blue_y * 0.04)),
                    scale=0.7,
                    color=color.white,
                    origin=(0, 0)
                )
                blue_y += 1
    
    def select_team(self, team):
        """Select a team and proceed to role selection"""
        self.team = team
        self.send_to_server({
            "type": MSG_TEAM_SELECT,
            "team": team
        })
        
        self.show_role_selection()
    
    def show_role_selection(self):
        """Show the role selection menu"""
        # Clean up team selection menu
        destroy(self.team_selection_menu)
            
        self.role_selection_menu = Entity(parent=camera.ui)
        
        # Title
        Text(
            "SELECT ROLE",
            parent=self.role_selection_menu,
            scale=2,
            origin=(0, 0),
            y=0.4,
            color=color.yellow
        )
        
        # Role buttons
        positions = [(-0.3, 0.2), (0.3, 0.2), (-0.3, -0.1), (0.3, -0.1)]
        i = 0
        
        for role_name, role_data in ROLES.items():
            pos = positions[i]
            
            # Container for role info
            role_container = Entity(
                parent=self.role_selection_menu,
                position=pos,
                scale=(0.35, 0.25)
            )
            
            # Role name
            Text(
                role_name,
                parent=role_container,
                position=(0, 0.1),
                scale=1.2,
                origin=(0, 0),
                color=TEAM_COLORS[self.team]
            )
            
            # Role description
            Text(
                role_data["description"],
                parent=role_container,
                position=(0, 0.05),
                scale=0.6,
                origin=(0, 0),
                color=color.light_gray
            )
            
            # Role stats
            Text(
                f"Health: {role_data['health']}",
                parent=role_container,
                position=(0, 0),
                scale=0.6,
                origin=(0, 0)
            )
            
            Text(
                f"Speed: {role_data['speed']}",
                parent=role_container,
                position=(0, -0.03),
                scale=0.6,
                origin=(0, 0)
            )
            
            Text(
                f"Damage: {role_data['damage']}",
                parent=role_container,
                position=(0, -0.06),
                scale=0.6,
                origin=(0, 0)
            )
            
            # Select button
            select_button = create_menu_button(
                "SELECT",
                (0, -0.1),
                scale=(0.15, 0.04),
                on_click=lambda r=role_name: self.select_role(r)
            )
            select_button.parent = role_container
            
            i += 1
            
        # Back button
        self.back_to_team_button = create_menu_button(
            "BACK TO TEAM SELECTION",
            (0, -0.4),
            scale=(0.3, 0.05),
            on_click=self.show_team_selection
        )
        self.back_to_team_button.parent = self.role_selection_menu
    
    def select_role(self, role):
        """Select a role and wait for game to start"""
        self.role = role
        self.send_to_server({
            "type": MSG_ROLE_SELECT,
            "role": role
        })
        
        # Hide role selection buttons
        for child in self.role_selection_menu.children:
            if isinstance(child, Button):
                child.visible = False
                
        # Show waiting message
        Text(
            f"Role selected: {role}",
            parent=self.role_selection_menu,
            position=(0, 0),
            scale=1.5,
            origin=(0, 0),
            color=color.green
        )
        
        Text(
            "Waiting for game to start...",
            parent=self.role_selection_menu,
            position=(0, -0.1),
            scale=1,
            origin=(0, 0)
        )
        
        # Show option to return to team selection
        self.back_to_team_button.visible = True
        
    def start_game(self):
        """Host starts the game"""
        if self.is_host:
            self.send_to_server({
                "type": MSG_START_GAME
            })
    
    def setup_game(self):
        """Set up the 3D game world"""
        # Clean up UI
        if hasattr(self, 'role_selection_menu'):
            destroy(self.role_selection_menu)
        if hasattr(self, 'team_selection_menu'):
            destroy(self.team_selection_menu)
            
        # Lock mouse
        mouse.locked = True
        mouse.visible = False
        self.crosshair.visible = True
        
        # Create game world
        self.create_world()
        
        # Create player
        self.create_player()
        
        # Create HUD
        self.create_hud()
        
        # Create scoreboard (initially hidden)
        self.create_scoreboard()
        
        # Start game loop
        self.game_state.match_active = True
        
    def create_world(self):
        """Create the game world based on the selected map"""
        map_data = MAPS[self.game_state.map_name]
        size_x, size_y, size_z = map_data["size"]
        
        # Create ground
        self.ground = Entity(
            model='plane',
            scale=(size_x, 1, size_z),
            color=color.dark_gray.tint(-.2),
            collider='box',
            shader=lit_with_shadows_shader
        )
        
        # Create outer walls
        wall_thickness = 2
        
        # North wall
        Entity(
            model='cube',
            position=(0, size_y/2, size_z/2 + wall_thickness/2),
            scale=(size_x, size_y, wall_thickness),
            color=color.dark_gray,
            collider='box',
            shader=lit_with_shadows_shader
        )
        
        # South wall
        Entity(
            model='cube',
            position=(0, size_y/2, -size_z/2 - wall_thickness/2),
            scale=(size_x, size_y, wall_thickness),
            color=color.dark_gray,
            collider='box',
            shader=lit_with_shadows_shader
        )
        
        # East wall
        Entity(
            model='cube',
            position=(size_x/2 + wall_thickness/2, size_y/2, 0),
            scale=(wall_thickness, size_y, size_z),
            color=color.dark_gray,
            collider='box',
            shader=lit_with_shadows_shader
        )
        
        # West wall
        Entity(
            model='cube',
            position=(-size_x/2 - wall_thickness/2, size_y/2, 0),
            scale=(wall_thickness, size_y, size_z),
            color=color.dark_gray,
            collider='box',
            shader=lit_with_shadows_shader
        )
        
        # Create obstacles
        self.create_obstacles(map_data["obstacles"])
        
        # Create team spawns
        self.red_spawn = Vec3(-size_x/2 + 10, 2, 0)
        self.blue_spawn = Vec3(size_x/2 - 10, 2, 0)
        
        # Create team bases
        # Red base
        Entity(
            model='cube',
            position=self.red_spawn + Vec3(0, 0, 0),
            scale=(10, 0.5, 10),
            color=color.red.tint(-.4),
            shader=lit_with_shadows_shader
        )
        
        # Blue base
        Entity(
            model='cube',
            position=self.blue_spawn + Vec3(0, 0, 0),
            scale=(10, 0.5, 10),
            color=color.blue.tint(-.4),
            shader=lit_with_shadows_shader
        )
        
    def create_obstacles(self, num_obstacles):
        """Create procedurally generated obstacles"""
        map_data = MAPS[self.game_state.map_name]
        size_x, size_y, size_z = map_data["size"]
        
        # Get obstacle positions from game state or generate new ones
        if not self.game_state.obstacles:
            # Generate new obstacles
            self.game_state.obstacles = []
            
            for i in range(num_obstacles):
                # Random position within map bounds
                pos_x = random.uniform(-size_x/2 + 10, size_x/2 - 10)
                pos_z = random.uniform(-size_z/2 + 10, size_z/2 - 10)
                
                # Avoid placing obstacles at spawn points
                distance_to_red = Vec3(pos_x, 0, pos_z).distance_to(self.red_spawn)
                distance_to_blue = Vec3(pos_x, 0, pos_z).distance_to(self.blue_spawn)
                
                if distance_to_red < 15 or distance_to_blue < 15:
                    continue
                
                # Random scale
                scale_x = random.uniform(2, 8)
                scale_y = random.uniform(2, 10)
                scale_z = random.uniform(2, 8)
                
                # Random color shade
                obstacle_color = color.gray.tint(random.uniform(-0.3, 0.3))
                
                self.game_state.obstacles.append({
                    "position": (pos_x, scale_y/2, pos_z),
                    "scale": (scale_x, scale_y, scale_z),
                    "color": obstacle_color
                })
        
        # Create obstacle entities
        for obstacle_data in self.game_state.obstacles:
            pos = obstacle_data["position"]
            scale = obstacle_data["scale"]
            col = obstacle_data["color"]
            
            Entity(
                model='cube',
                position=pos,
                scale=scale,
                color=col,
                collider='box',
                shader=lit_with_shadows_shader
            )
            
    def create_player(self):
        """Create the player entity"""
        if self.team == TEAM_RED:
            spawn_pos = self.red_spawn
        else:
            spawn_pos = self.blue_spawn
            
        role_data = ROLES[self.role]
        
        # Create player controller
        self.player_entity = FirstPersonController(
            position=spawn_pos,
            speed=role_data["speed"],
            jump_height=2,
            mouse_sensitivity=Vec2(40, 40),
            gravity=1
        )
        
        # Create weapon model
        self.weapon_model = self.create_weapon_model(self.role)
        self.weapon_model.parent = camera
        
        # Set player data
        if self.player_id in self.game_state.players:
            self.game_state.players[self.player_id]["health"] = role_data["health"]
            self.game_state.players[self.player_id]["position"] = self.player_entity.position
            self.game_state.players[self.player_id]["rotation"] = self.player_entity.rotation
            
    def create_weapon_model(self, role):
        """Create a weapon model for the given role"""
        if role == "ASSAULT":
            # Assault rifle
            weapon = Entity(parent=camera)
            
            # Body
            Entity(
                parent=weapon,
                model='cube',
                position=(0.4, -0.2, 0.8),
                scale=(0.05, 0.05, 0.3),
                color=color.dark_gray
            )
            
            # Grip
            Entity(
                parent=weapon,
                model='cube',
                position=(0.4, -0.25, 0.7),
                scale=(0.04, 0.1, 0.04),
                color=color.black
            )
            
            # Magazine
            Entity(
                parent=weapon,
                model='cube',
                position=(0.4, -0.23, 0.7),
                scale=(0.03, 0.08, 0.05),
                color=color.gray
            )
            
            # Scope
            Entity(
                parent=weapon,
                model='cube',
                position=(0.4, -0.18, 0.75),
                scale=(0.02, 0.02, 0.1),
                color=color.black
            )
            
        elif role == "SNIPER":
            # Sniper rifle
            weapon = Entity(parent=camera)
            
            # Body
            Entity(
                parent=weapon,
                model='cube',
                position=(0.4, -0.2, 0.8),
                scale=(0.04, 0.04, 0.4),
                color=color.black
            )
            
            # Grip
            Entity(
                parent=weapon,
                model='cube',
                position=(0.4, -0.25, 0.65),
                scale=(0.03, 0.1, 0.03),
                color=color.dark_gray
            )
            
            # Scope
            Entity(
                parent=weapon,
                model='cylinder',
                position=(0.4, -0.17, 0.8),
                rotation=(90, 0, 0),
                scale=(0.02, 0.1, 0.02),
                color=color.black
            )
            
        elif role == "SHOTGUN":
            # Shotgun
            weapon = Entity(parent=camera)
            
            # Body
            Entity(
                parent=weapon,
                model='cube',
                position=(0.4, -0.2, 0.8),
                scale=(0.06, 0.06, 0.3),
                color=color.brown
            )
            
            # Pump
            Entity(
                parent=weapon,
                model='cube',
                position=(0.4, -0.2, 0.7),
                scale=(0.05, 0.05, 0.1),
                color=color.dark_gray
            )
            
            # Grip
            Entity(
                parent=weapon,
                model='cube',
                position=(0.4, -0.25, 0.65),
                scale=(0.04, 0.1, 0.04),
                color=color.dark_brown
            )
            
        else:  # FLANKER
            # SMG
            weapon = Entity(parent=camera)
            
            # Body
            Entity(
                parent=weapon,
                model='cube',
                position=(0.4, -0.2, 0.8),
                scale=(0.04, 0.04, 0.2),
                color=color.light_gray
            )
            
            # Grip
            Entity(
                parent=weapon,
                model='cube',
                position=(0.4, -0.25, 0.75),
                scale=(0.03, 0.1, 0.03),
                color=color.black
            )
            
            # Extended magazine
            Entity(
                parent=weapon,
                model='cube',
                position=(0.4, -0.23, 0.75),
                scale=(0.025, 0.15, 0.03),
                color=color.gray
            )
            
        return weapon
    
    def create_enemy_model(self, position, team, role):
        """Create an enemy player model"""
        # Base entity
        enemy = Entity(
            position=position,
            model='cube',
            scale=(0.8, 1.8, 0.8),
            color=TEAM_COLORS[team],
            shader=lit_with_shadows_shader
        )
        
        # Head
        Entity(
            parent=enemy,
            model='sphere',
            position=(0, 1.1, 0),
            scale=0.5,
            color=TEAM_COLORS[team].tint(0.2),
            shader=lit_with_shadows_shader
        )
        
        # Gun (varies by role)
        gun_scale = ROLES[role]["model_scale"]
        
        Entity(
            parent=enemy,
            model='cube',
            position=(0.4, 0, 0.3),
            scale=(0.1 * gun_scale, 0.1 * gun_scale, 0.4 * gun_scale),
            color=color.dark_gray,
            shader=lit_with_shadows_shader
        )
        
        # Name tag
        player_name = ""
        for player_id, player_data in self.game_state.players.items():
            if (player_data.get("team") == team and 
                player_data.get("role") == role and
                Vec3(*player_data.get("position")).distance_to(position) < 0.1):
                player_name = player_data.get("name", "")
                break
                
        if player_name:
            Text(
                text=player_name,
                parent=enemy,
                position=(0, 1.5, 0),
                scale=10,
                billboard=True,
                origin=(0, 0),
                color=TEAM_COLORS[team]
            )
            
        return enemy
        
    def create_hud(self):
        """Create the game HUD"""
        self.game_hud = Entity(parent=camera.ui)
        
        # Health bar
        self.health_bar = HealthBar(
            max_value=ROLES[self.role]["health"],
            parent=self.game_hud,
            position=(-0.7, -0.4),
            scale=(0.2, 0.03)
        )
        
        # Health text
        self.health_text = Text(
            text=f"Health: {ROLES[self.role]['health']}/{ROLES[self.role]['health']}",
            parent=self.game_hud,
            position=(-0.7, -0.43),
            scale=0.7,
            origin=(-0.5, 0)
        )
        
        # Ammo (infinite for now)
        self.ammo_text = Text(
            text="Ammo: ∞",
            parent=self.game_hud,
            position=(-0.7, -0.46),
            scale=0.7,
            origin=(-0.5, 0)
        )
        
        # Role and team info
        self.role_text = Text(
            text=f"Role: {self.role}",
            parent=self.game_hud,
            position=(0.7, 0.45),
            scale=0.7,
            origin=(0.5, 0),
            color=TEAM_COLORS[self.team]
        )
        
        self.team_text = Text(
            text=f"Team: {TEAM_NAMES[self.team]}",
            parent=self.game_hud,
            position=(0.7, 0.42),
            scale=0.7,
            origin=(0.5, 0),
            color=TEAM_COLORS[self.team]
        )
        
        # Timer
        self.timer_text = Text(
            text=f"Time: {self.format_time(self.game_state.match_time)}",
            parent=self.game_hud,
            position=(0, 0.45),
            scale=1,
            origin=(0, 0)
        )
        
        # Score
        self.score_text = Text(
            text=f"RED {self.game_state.scores[TEAM_RED]} - {self.game_state.scores[TEAM_BLUE]} BLUE",
            parent=self.game_hud,
            position=(0, 0.4),
            scale=0.8,
            origin=(0, 0)
        )
        
        # Kill feed
        self.kill_feed = Entity(
            parent=self.game_hud,
            position=(-0.7, 0.4),
            scale=1
        )
        
        # Chat box
        self.create_chat_box()
        
    def create_chat_box(self):
        """Create the in-game chat box"""
        self.chat_box = Entity(
            parent=self.game_hud,
            position=(-0.7, -0.3),
            scale=1
        )
        
        # Chat messages
        self.chat_messages = []
        
        # Chat input (initially hidden)
        self.chat_input = InputField(
            parent=self.chat_box,
            position=(0.35, 0),
            scale=(0.6, 0.04),
            visible=False,
            active=False
        )
        
        # Chat send button
        self.chat_send_button = Button(
            text="Send",
            parent=self.chat_box,
            position=(0.7, 0),
            scale=(0.1, 0.04),
            visible=False,
            on_click=self.send_chat_message
        )
        
    def create_scoreboard(self):
        """Create the scoreboard (initially hidden)"""
        self.scoreboard = Entity(
            parent=camera.ui,
            model='quad',
            scale=(0.8, 0.6),
            color=color.black66,
            visible=False
        )
        
        # Title
        Text(
            text="SCOREBOARD",
            parent=self.scoreboard,
            position=(0, 0.25),
            scale=1.5,
            origin=(0, 0),
            color=color.yellow
        )
        
        # Headers
        Text(
            text="PLAYER",
            parent=self.scoreboard,
            position=(-0.3, 0.15),
            scale=0.8,
            origin=(0, 0)
        )
        
        Text(
            text="KILLS",
            parent=self.scoreboard,
            position=(0, 0.15),
            scale=0.8,
            origin=(0, 0)
        )
        
        Text(
            text="DEATHS",
            parent=self.scoreboard,
            position=(0.15, 0.15),
            scale=0.8,
            origin=(0, 0)
        )
        
        Text(
            text="ROLE",
            parent=self.scoreboard,
            position=(0.3, 0.15),
            scale=0.8,
            origin=(0, 0)
        )
        
        # Team headers
        Text(
            text="RED TEAM",
            parent=self.scoreboard,
            position=(-0.35, 0.1),
            scale=0.8,
            origin=(-0.5, 0),
            color=color.red
        )
        
        Text(
            text="BLUE TEAM",
            parent=self.scoreboard,
            position=(-0.35, -0.1),
            scale=0.8,
            origin=(-0.5, 0),
            color=color.blue
        )
        
        # Player entries will be populated in update_scoreboard()
        self.red_team_entries = Entity(parent=self.scoreboard)
        self.blue_team_entries = Entity(parent=self.scoreboard)
        
    def update_scoreboard(self):
        """Update the scoreboard with current player stats"""
        # Clear existing entries
        for child in self.red_team_entries.children:
            destroy(child)
        for child in self.blue_team_entries.children:
            destroy(child)
            
        # Populate team entries
        red_y = 0
        blue_y = 0
        
        for player_id, player_data in self.game_state.players.items():
            name = player_data.get("name", "Unknown")
            team = player_data.get("team")
            role = player_data.get("role", "")
            kills = player_data.get("kills", 0)
            deaths = player_data.get("deaths", 0)
            
            if team == TEAM_RED:
                Text(
                    text=name,
                    parent=self.red_team_entries,
                    position=(-0.3, 0.05 - (red_y * 0.04)),
                    scale=0.7,
                    origin=(0, 0),
                    color=color.light_gray
                )
                
                Text(
                    text=str(kills),
                    parent=self.red_team_entries,
                    position=(0, 0.05 - (red_y * 0.04)),
                    scale=0.7,
                    origin=(0, 0),
                    color=color.light_gray
                )
                
                Text(
                    text=str(deaths),
                    parent=self.red_team_entries,
                    position=(0.15, 0.05 - (red_y * 0.04)),
                    scale=0.7,
                    origin=(0, 0),
                    color=color.light_gray
                )
                
                Text(
                    text=role,
                    parent=self.red_team_entries,
                    position=(0.3, 0.05 - (red_y * 0.04)),
                    scale=0.7,
                    origin=(0, 0),
                    color=color.light_gray
                )
                
                red_y += 1
                
            elif team == TEAM_BLUE:
                Text(
                    text=name,
                    parent=self.blue_team_entries,
                    position=(-0.3, -0.15 - (blue_y * 0.04)),
                    scale=0.7,
                    origin=(0, 0),
                    color=color.light_gray
                )
                
                Text(
                    text=str(kills),
                    parent=self.blue_team_entries,
                    position=(0, -0.15 - (blue_y * 0.04)),
                    scale=0.7,
                    origin=(0, 0),
                    color=color.light_gray
                )
                
                Text(
                    text=str(deaths),
                    parent=self.blue_team_entries,
                    position=(0.15, -0.15 - (blue_y * 0.04)),
                    scale=0.7,
                    origin=(0, 0),
                    color=color.light_gray
                )
                
                Text(
                    text=role,
                    parent=self.blue_team_entries,
                    position=(0.3, -0.15 - (blue_y * 0.04)),
                    scale=0.7,
                    origin=(0, 0),
                    color=color.light_gray
                )
                
                blue_y += 1
                
        # Update score
        Text(
            text=f"RED: {self.game_state.scores[TEAM_RED]} - BLUE: {self.game_state.scores[TEAM_BLUE]}",
            parent=self.scoreboard,
            position=(0, -0.25),
            scale=1,
            origin=(0, 0),
            color=color.yellow
        )
        
    def format_time(self, seconds):
        """Format seconds to MM:SS"""
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def add_chat_message(self, sender_name, message, team=None):
        """Add a message to the chat box"""
        if len(self.chat_messages) >= 5:
            # Remove oldest message
            destroy(self.chat_messages[0])
            self.chat_messages.pop(0)
            
            # Move remaining messages up
            for i, msg in enumerate(self.chat_messages):
                msg.y += 0.03
                
        # Create new message
        text_color = color.white
        if team is not None:
            text_color = TEAM_COLORS[team]
            
        msg = Text(
            text=f"{sender_name}: {message}",
            parent=self.chat_box,
            position=(0, -0.15 - len(self.chat_messages) * 0.03),
            scale=0.6,
            origin=(-0.5, 0),
            color=text_color
        )
        
        self.chat_messages.append(msg)
        
        # Auto-hide after 5 seconds
        invoke(lambda: destroy(msg), delay=5)
        invoke(lambda: self.chat_messages.remove(msg) if msg in self.chat_messages else None, delay=5)
        
    def send_chat_message(self):
        """Send a chat message to all players"""
        if self.chat_input.text.strip():
            message = self.chat_input.text.strip()
            
            self.send_to_server({
                "type": MSG_CHAT,
                "message": message
            })
            
            # Clear input
            self.chat_input.text = ""
            self.chat_input.active = False
            self.chat_input.visible = False
            self.chat_send_button.visible = False
            
            # Lock mouse again
            mouse.locked = True
            self.crosshair.visible = True
        
    def update(self):
        """Main game update loop"""
        if not self.game_state.match_active:
            return
        # Process inputs
        self.process_inputs()
        # Update player position
        if self.player_entity and self.player_id in self.game_state.players:
            # Send position update to server
            self.send_to_server({
                "type": MSG_MOVE,
                "position": (
                    self.player_entity.position.x,
                    self.player_entity.position.y,
                    self.player_entity.position.z
                ),
                "rotation": (
                    self.player_entity.rotation.x,
                    self.player_entity.rotation.y,
                    self.player_entity.rotation.z
                )
            })
        # Update enemy positions
        self.update_enemies()
        # Update projectiles
        self.update_projectiles()
        # Update HUD
        self.update_hud()
    
    def process_inputs(self):
        """Process player inputs"""
        # Skip if player not created yet
        if not self.player_entity:
            return
            
        # Shooting
        if mouse.left and self.bullet_cooldown <= 0:
            role_data = ROLES[self.role]
            self.bullet_cooldown = role_data["fire_rate"]
            
            # Create projectile on server
            self.send_to_server({
                "type": MSG_SHOOT,
                "position": (
                    self.player_entity.position.x,
                    self.player_entity.position.y + 1.5,  # Head height
                    self.player_entity.position.z
                ),
                "direction": (
                    self.player_entity.forward.x,
                    self.player_entity.forward.y,
                    self.player_entity.forward.z
                ),
                "damage": role_data["damage"],
                "range": role_data["weapon_range"]
            })
            
            # Play shoot animation
            self.play_shoot_animation()
            
        # Update cooldown
        if self.bullet_cooldown > 0:
            self.bullet_cooldown -= time.dt
            
        # Toggle scoreboard
        if held_keys['tab']:
            if not self.scoreboard.visible:
                self.update_scoreboard()
                self.scoreboard.visible = True
        else:
            self.scoreboard.visible = False
            
        # Chat
        if held_keys['t'] and not self.chat_input.active:
            # Show chat input
            self.chat_input.active = True
            self.chat_input.visible = True
            self.chat_send_button.visible = True
            
            # Unlock mouse for typing
            mouse.locked = False
            self.crosshair.visible = False
            
        # Handle Enter key for chat
        if held_keys['enter'] and self.chat_input.active:
            self.send_chat_message()
            
        # Handle Escape key to cancel chat
        if held_keys['escape'] and self.chat_input.active:
            self.chat_input.text = ""
            self.chat_input.active = False
            self.chat_input.visible = False
            self.chat_send_button.visible = False
            
            # Lock mouse again
            mouse.locked = True
            self.crosshair.visible = True
    
    def play_shoot_animation(self):
        """Play shooting animation"""
        # Weapon recoil
        self.weapon_model.animate_position(
            self.weapon_model.position + Vec3(0, 0, 0.1),
            duration=0.05,
            curve=curve.linear
        )
        self.weapon_model.animate_position(
            self.weapon_model.position,
            duration=0.1,
            delay=0.05,
            curve=curve.linear
        )
        
        # Muzzle flash
        muzzle_flash = Entity(
            parent=self.weapon_model,
            model='quad',
            texture='circle',
            position=(0, 0, 0.5),
            scale=0.2,
            color=color.yellow,
            billboard=True
        )
        
        destroy(muzzle_flash, delay=0.05)
        
    def update_enemies(self):
        """Update enemy player positions"""
        # Remove enemies that no longer exist
        for player_id in list(self.players_entities.keys()):
            if player_id not in self.game_state.players or player_id == self.player_id:
                destroy(self.players_entities[player_id])
                del self.players_entities[player_id]
        # Update or create enemies
        for player_id, player_data in self.game_state.players.items():
            if player_id == self.player_id:
                continue
            position = Vec3(*player_data.get("position", (0,2,0)))
            team = player_data.get("team")
            role = player_data.get("role")
            if player_id in self.players_entities:
                # Update position
                self.players_entities[player_id].animate_position(
                    position,
                    duration=0.1,
                    curve=curve.linear
                )
            else:
                # Create new enemy
                self.players_entities[player_id] = self.create_enemy_model(position, team, role)
    
    def update_projectiles(self):
        """Update projectile positions"""
        # Clear old projectiles
        for projectile in self.projectile_entities:
            destroy(projectile)
        self.projectile_entities = []
        
        # Create new projectiles
        for proj in self.game_state.projectiles:
            position = Vec3(*proj["position"])
            color_value = color.red if proj["owner_team"] == TEAM_RED else color.blue
            
            projectile = Entity(
                model='sphere',
                position=position,
                scale=0.2,
                color=color_value,
                shader=lit_with_shadows_shader
            )
            
            self.projectile_entities.append(projectile)
            
        # Update hit markers
        for i, marker in enumerate(self.hit_markers[:]):
            marker["time"] -= time.dt
            if marker["time"] <= 0:
                destroy(marker["entity"])
                self.hit_markers.remove(marker)
    
    def add_hit_marker(self, position, is_kill=False):
        """Add a hit marker at the given position"""
        marker = Entity(
            model='quad',
            texture='circle',
            position=position,
            scale=0.2,
            color=color.red if is_kill else color.yellow,
            billboard=True
        )
        
        self.hit_markers.append({
            "entity": marker,
            "time": 0.5  # Display for 0.5 seconds
        })
        
    def update_hud(self):
        """Update HUD elements"""
        # Update health
        if self.player_id in self.game_state.players:
            health = self.game_state.players[self.player_id]["health"]
            max_health = ROLES[self.role]["health"]
            
            self.health_bar.value = health
            self.health_text.text = f"Health: {health}/{max_health}"
            
        # Update timer
        remaining_time = max(0, self.game_state.match_time - (time.time() - self.game_state.match_start_time))
        self.timer_text.text = f"Time: {self.format_time(int(remaining_time))}"
        
        # Update score
        self.score_text.text = f"RED {self.game_state.scores[TEAM_RED]} - {self.game_state.scores[TEAM_BLUE]} BLUE"
        
    def send_to_server(self, data):
        """Send data to the server"""
        if not self.client_socket:
            return
            
        try:
            # Add player ID
            if self.player_id:
                data["player_id"] = self.player_id
                
            # Serialize and send
            serialized_data = pickle.dumps(data)
            header = bytes(f"{len(serialized_data):<{HEADER_SIZE}}", 'utf-8')
            self.client_socket.send(header + serialized_data)
        except Exception as e:
            print(f"Error sending to server: {e}")
    
    def client_receive(self):
        """Client receive thread"""
        try:
            while True:
                # Receive header
                header = self.client_socket.recv(HEADER_SIZE)
                if not header:
                    break
                    
                msg_len = int(header.decode('utf-8').strip())
                
                # Receive data
                data = b""
                remaining = msg_len
                while remaining > 0:
                    chunk = self.client_socket.recv(min(4096, remaining))
                    if not chunk:
                        break
                    data += chunk
                    remaining -= len(chunk)
                    
                if not data:
                    break
                    
                # Deserialize
                message = pickle.loads(data)
                
                # Process message
                self.process_message(message)
                
        except Exception as e:
            print(f"Client receive error: {e}")
        finally:
            print("Disconnected from server")
            # TODO: Show disconnect message and return to main menu
            
    def process_message(self, message):
        """Process a message from the server"""
        msg_type = message.get("type")
        
        if msg_type == MSG_ACCEPT:
            # Server accepted connection
            self.player_id = message.get("player_id")
            print(f"Connected to server. Player ID: {self.player_id}")
        
        elif msg_type == MSG_REJECT:
            # Server rejected connection
            reason = message.get("reason", "Unknown reason")
            print(f"Connection rejected: {reason}")
            # TODO: Show rejection message and return to main menu
        
        elif msg_type == "LOBBY_UPDATE":
            # Update lobby player list
            self.game_state.players = message.get("players", {})
            self.update_player_list()
        
        elif msg_type == MSG_UPDATE:
            # Game state update (positions, etc.)
            self.game_state.players = message.get("players", {})
            self.game_state.projectiles = message.get("projectiles", [])
            self.game_state.scores = message.get("scores", {TEAM_RED: 0, TEAM_BLUE: 0})
            self.game_state.match_active = message.get("match_active", False)
            # Update UI elements
            self.update_enemies()  # Real-time enemy update
            self.update_hud()
        
        elif msg_type == MSG_CHAT:
            # Chat message
            sender = message.get("sender", "Unknown")
            msg = message.get("message", "")
            team = message.get("team")
            self.add_chat_message(sender, msg, team)
        
        elif msg_type == "START_GAME":
            self.game_state.match_active = True
            self.game_state.match_start_time = time.time()
            # Set team and role from server state
            if self.player_id in self.game_state.players:
                self.team = self.game_state.players[self.player_id].get("team")
                self.role = self.game_state.players[self.player_id].get("role")
            self.setup_game()
        
        elif msg_type == MSG_START_GAME:
            self.game_state.match_active = True
            self.game_state.match_start_time = time.time()
            # Set team and role from server state
            if self.player_id in self.game_state.players:
                self.team = self.game_state.players[self.player_id].get("team")
                self.role = self.game_state.players[self.player_id].get("role")
            self.setup_game()
        
        elif msg_type == MSG_END_GAME:
            self.game_state.match_active = False
            winner = message.get("winner")
            # Show end game screen
            self.show_end_game_screen(winner)
        
        elif msg_type == MSG_HIT:
            # Player was hit
            damage = message.get("damage", 0)
            is_kill = message.get("is_kill", False)
            # Update health
            if self.player_id in self.game_state.players:
                self.game_state.players[self.player_id]["health"] -= damage
            # Show hit marker
            if is_kill:
                self.add_hit_marker(camera.position + camera.forward * 10, True)
            else:
                self.add_hit_marker(camera.position + camera.forward * 10, False)
        
    def show_end_game_screen(self, winner):
        """Show the end game screen"""
        # Create end game screen
        self.end_screen = Entity(parent=camera.ui)
        
        # Background
        Entity(
            parent=self.end_screen,
            model='quad',
            scale=(1, 1),
            color=color.black66
        )
        
        # Winner text
        Text(
            text=f"{TEAM_NAMES[winner]} TEAM WINS!",
            parent=self.end_screen,
            position=(0, 0.2),
            scale=2,
            origin=(0, 0),
            color=TEAM_COLORS[winner]
        )
        
        # Final score
        Text(
            text=f"Final Score: RED {self.game_state.scores[TEAM_RED]} - {self.game_state.scores[TEAM_BLUE]} BLUE",
            parent=self.end_screen,
            position=(0, 0),
            scale=1.5,
            origin=(0, 0),
            color=color.white
        )
        
        # Player stats
        if self.player_id in self.game_state.players:
            player_data = self.game_state.players[self.player_id]
            Text(
                text=f"Your Stats: {player_data.get('kills', 0)} Kills, {player_data.get('deaths', 0)} Deaths",
                parent=self.end_screen,
                position=(0, -0.2),
                scale=1,
                origin=(0, 0),
                color=color.white
            )
        
        # Return to menu button
        self.return_button = Button(
            text="Return to Menu",
            parent=self.end_screen,
            position=(0, -0.4),
            scale=(0.3, 0.1),
            color=color.gray,
            highlight_color=color.white,
            on_click=self.return_to_menu
        )
        
    def return_to_menu(self):
        """Return to the main menu"""
        # Clean up game state
        self.game_state = GameState()
        self.player_id = None
        self.team = None
        self.role = None
        
        # Clean up entities
        if hasattr(self, 'player_entity'):
            destroy(self.player_entity)
        for entity in self.players_entities.values():
            destroy(entity)
        for projectile in self.projectile_entities:
            destroy(projectile)
        if hasattr(self, 'end_screen'):
            destroy(self.end_screen)
            
        # Reset mouse
        mouse.locked = False
        mouse.visible = True
        self.crosshair.visible = False
        
        # Show main menu
        self.create_main_menu()
        
    def quit_game(self):
        """Quit the game"""
        if self.client_socket:
            self.send_to_server({
                "type": MSG_DISCONNECT
            })
            self.client_socket.close()
            
        if self.server_socket:
            self.server_socket.close()
            
        application.quit()

    def run_server(self):
        """Robust server loop: handles player join, team/role selection, start game, and broadcasts game state."""
        print("Server thread started. Waiting for clients...")
        self.server_clients = {}  # {client_socket: player_id}
        self.server_players = {}  # {player_id: {name, team, role, ...}}
        self.server_next_id = 1
        import select
        import pickle
        import time
        def handle_client(client_socket, addr):
            player_id = self.server_next_id
            self.server_next_id += 1
            self.server_clients[client_socket] = player_id
            self.server_players[player_id] = {"name": None, "team": None, "role": None, "ready": False, "position": (0,2,0), "rotation": (0,0,0)}
            print(f"[SERVER] Player {player_id} connected from {addr}")
            try:
                while True:
                    header = client_socket.recv(10)
                    if not header:
                        break
                    msg_len = int(header.decode('utf-8').strip())
                    data = b""
                    while len(data) < msg_len:
                        chunk = client_socket.recv(msg_len - len(data))
                        if not chunk:
                            break
                        data += chunk
                    if not data:
                        break
                    message = pickle.loads(data)
                    msg_type = message.get("type")
                    if msg_type == "JOIN":
                        name = message.get("name", f"Player{player_id}")
                        self.server_players[player_id]["name"] = name
                        # Accept and send player_id
                        reply = {"type": "ACCEPT", "player_id": player_id}
                        self.send_to_client(client_socket, reply)
                        self.broadcast_lobby()
                    elif msg_type == "TEAM":
                        team = message.get("team")
                        self.server_players[player_id]["team"] = team
                        self.broadcast_lobby()
                    elif msg_type == "ROLE":
                        role = message.get("role")
                        self.server_players[player_id]["role"] = role
                        self.server_players[player_id]["ready"] = True
                        self.broadcast_lobby()
                    elif msg_type == "START":
                        # Only host can start
                        self.broadcast_all({"type": "START_GAME"})
                        self.broadcast_game_state()
                    elif msg_type == "MOVE":
                        pos = message.get("position", (0,2,0))
                        rot = message.get("rotation", (0,0,0))
                        self.server_players[player_id]["position"] = pos
                        self.server_players[player_id]["rotation"] = rot
                        self.broadcast_game_state()
                    elif msg_type == "DISCONNECT":
                        break
                print(f"[SERVER] Player {player_id} disconnected")
            except Exception as e:
                print(f"[SERVER] Error with player {player_id}: {e}")
            finally:
                client_socket.close()
                if client_socket in self.server_clients:
                    del self.server_clients[client_socket]
                if player_id in self.server_players:
                    del self.server_players[player_id]
                self.broadcast_lobby()
        # Accept clients
        import threading
        while True:
            client_socket, addr = self.server_socket.accept()
            threading.Thread(target=handle_client, args=(client_socket, addr), daemon=True).start()
    def send_to_client(self, client_socket, data):
        import pickle
        msg = pickle.dumps(data)
        header = bytes(f"{len(msg):<10}", 'utf-8')
        try:
            client_socket.send(header + msg)
        except:
            pass
    def broadcast_all(self, data):
        for client_socket in list(self.server_clients.keys()):
            self.send_to_client(client_socket, data)
    def broadcast_lobby(self):
        # Send lobby state to all clients
        lobby = {pid: {"name": p["name"], "team": p["team"], "role": p["role"], "ready": p["ready"]} for pid, p in self.server_players.items()}
        self.broadcast_all({"type": "LOBBY_UPDATE", "players": lobby})
    def broadcast_game_state(self):
        # Placeholder for sending game state to all clients
        self.broadcast_all({"type": "UPDATE", "players": self.server_players})

# Start the game
if __name__ == "__main__":
    app = Ursina()
    game = Chimera()
    app.run()