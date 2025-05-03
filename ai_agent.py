import os
import numpy as np
from stable_baselines3 import PPO

class CombatAgent:
    def __init__(self, model_path="ppo_chimera_combat", env=None, learning_rate=3e-4):
        self.model_path = f"{model_path}.zip"
        self.env = env  # Needs a VecEnv usually
        self.learning_rate = learning_rate
        self.model = None
        self._load_or_initialize_model()

    def _load_or_initialize_model(self):
        if os.path.exists(self.model_path):
            print(f"Loading pre-trained model from {self.model_path}")
            try:
                # Pass custom_objects if needed for activation functions etc.
                self.model = PPO.load(self.model_path, env=self.env)
                print("Model loaded successfully.")
            except Exception as e:
                print(f"Error loading model: {e}. Initializing a new one.")
                self._initialize_new_model()
        else:
            print("No pre-trained model found. Initializing a new one.")
            self._initialize_new_model()

    def _initialize_new_model(self):
        if self.env is None:
            print("Error: Cannot initialize model without an environment.")
            # Fallback: Create a dummy model structure if absolutely necessary
            class DummyModel:
                def predict(self, obs, deterministic=True): 
                    return np.random.randint(0, 5), None  # Random action
                def learn(self, *args, **kwargs): 
                    print("Dummy learn called")
                def save(self, *args, **kwargs): 
                    print("Dummy save called")
            self.model = DummyModel()
            return

        # Use PPO algorithm. MlpPolicy is standard for vector observations.
        self.model = PPO("MlpPolicy", self.env, verbose=1, learning_rate=self.learning_rate,
                         tensorboard_log="./chimera_tensorboard/")
        print("New PPO model initialized.")

    def predict(self, observation, deterministic=True):
        """Get action from the RL model."""
        if self.model:
            action, _states = self.model.predict(observation, deterministic=deterministic)
            return action
        else:
            print("Warning: Model not available for prediction.")
            # Return a default action (e.g., idle) if model isn't loaded
            return 0  # Assuming 0 is Idle

    def learn(self, total_timesteps=1000, callback=None, reset_num_timesteps=False):
        """Perform a training step."""
        if self.model and hasattr(self.model, 'learn') and self.env:
            print(f"Starting simplified training for {total_timesteps} timesteps...")
            try:
                # The 'env' passed during initialization should be used internally by learn
                self.model.learn(total_timesteps=total_timesteps,
                                callback=callback,
                                reset_num_timesteps=reset_num_timesteps,  # Continue learning count unless specified
                                tb_log_name="PPO_Chimera")
                print("Training step completed.")
                self.save_model()  # Save after learning
            except Exception as e:
                print(f"Error during training: {e}")
        else:
            print("Warning: Cannot train. Model or environment not properly configured.")

    def save_model(self):
        """Save the current model state."""
        if self.model and hasattr(self.model, 'save'):
            try:
                self.model.save(self.model_path.replace(".zip", ""))  # SB3 adds .zip automatically
                print(f"Model saved to {self.model_path}")
            except Exception as e:
                print(f"Error saving model: {e}")
        else:
            print("Warning: Model not available for saving.")