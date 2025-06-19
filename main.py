import pygame
import tkinter as tk
from tkinter import ttk
import pyautogui
import threading
import time
import math
import ctypes
from ctypes import wintypes

# Windows API for smooth mouse movement
try:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Define Windows API functions for smoother mouse control
    def smooth_move_mouse(x, y):
        user32.SetCursorPos(int(x), int(y))


    # Use Windows API if available, fallback to pyautogui
    USE_WINDOWS_API = True
except e as e:
    USE_WINDOWS_API = False
    print(f"Error has occurred, \f")


    def smooth_move_mouse(x, y):
        pyautogui.moveTo(int(x), int(y))


class ControllerMouseControl:
    def __init__(self):
        # Initialize pygame for joystick support
        pygame.init()
        pygame.joystick.init()

        # Disable pyautogui failsafe for smooth operation
        pyautogui.FAILSAFE = False

        # Controller state
        self.controller = None
        self.running = False
        self.thread = None

        # Get screen center
        screen_width, screen_height = pyautogui.size()
        self.screen_center = (screen_width // 2, screen_height // 2)

        # Improved settings for smoother movement
        self.max_distance = 400
        self.normal_sensitivity = 6.0  # Reduced for smoother control
        self.limited_sensitivity = 4.0  # Reduced for smoother control
        self.deadzone = 0.12  # Slightly increased deadzone
        self.return_speed = 12
        self.click_button = 0
        self.stop_button_id = 7
        self.limit_trigger_id = 4
        self.speed_multiplier = 1.5  # Reduced for smoother movement

        # Mouse state
        self.mouse_held = False
        self.limited_mode = False
        self.limited_mode_center = None

        # Smooth movement system
        self.current_mouse_pos = list(pyautogui.position())
        self.target_mouse_pos = list(self.current_mouse_pos)

        # Enhanced smoothing system
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.acceleration = 0.15  # Reduced for smoother buildup
        self.friction = 0.85  # Increased for better stopping
        self.max_velocity = 12.0  # Reduced max velocity

        # Auto-click and quick action settings
        self.auto_click_enabled = True  # Auto-click when moving in limited mode
        self.auto_click_active = False  # Current auto-click state
        self.quick_action_button = 1  # Button for quick top-click action (Circle button)
        self.quick_action_distance = 50  # Distance from top of restricted area to click
        self.quick_action_pending = False  # Flag for pending quick action
        self.quick_action_start_time = 0  # Timing for quick action

        # Controller action settings
        self.controller_action_button = 2  # Default button for controller action (Triangle button)
        self.controller_hold_duration = 0.5  # Default hold duration in seconds
        self.controller_action_pending = False  # Flag for pending controller action
        self.controller_action_start_time = 0  # Timing for controller action
        self.controller_action_phase = 0  # 0=move, 1=click_down, 2=hold, 3=click_up, 4=return

        # Jump button settings
        self.jump_button = 3  # Default jump button (Square button)
        self.jump_pending = False  # Flag for pending jump
        self.jump_start_time = 0  # Timing for jump
        self.jump_target_x = 0  # Target X position for jump
        self.jump_target_y = 0  # Target Y position for jump

        # Multi-stage smoothing
        self.smooth_x = 0.0
        self.smooth_y = 0.0
        self.smoothing_factor = 0.6  # Less aggressive smoothing

        # Additional smoothing buffer
        self.input_buffer = []
        self.buffer_size = 3

        # Movement interpolation
        self.interpolation_factor = 0.3  # How much to interpolate between positions

        # Frame rate control
        self.target_fps = 120
        self.frame_time = 1.0 / self.target_fps

        # Create GUI
        self.setup_gui()
        self.refresh_controllers()

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Smooth Controller Mouse Control")
        self.root.geometry("450x1000")  # Increased height for new settings

        # Controller selection
        controller_frame = ttk.Frame(self.root)
        controller_frame.pack(pady=10, padx=10, fill="x")

        ttk.Label(controller_frame, text="Controller:").pack(side="left")
        self.controller_var = tk.StringVar()
        self.controller_combo = ttk.Combobox(controller_frame, textvariable=self.controller_var, state="readonly")
        self.controller_combo.pack(side="left", padx=(10, 0), fill="x", expand=True)

        ttk.Button(controller_frame, text="Refresh", command=self.refresh_controllers).pack(side="right", padx=(10, 0))

        # Settings
        settings_frame = ttk.LabelFrame(self.root, text="Movement Settings")
        settings_frame.pack(pady=10, padx=10, fill="x")

        # Normal sensitivity
        normal_sens_frame = ttk.Frame(settings_frame)
        normal_sens_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(normal_sens_frame, text="Normal Sensitivity:").pack(side="left")
        self.normal_sens_var = tk.DoubleVar(value=self.normal_sensitivity)
        ttk.Spinbox(normal_sens_frame, from_=1.0, to=15.0, increment=0.5,
                    textvariable=self.normal_sens_var, width=10).pack(side="right")

        # Limited mode sensitivity
        limited_sens_frame = ttk.Frame(settings_frame)
        limited_sens_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(limited_sens_frame, text="Limited Mode Sensitivity:").pack(side="left")
        self.limited_sens_var = tk.DoubleVar(value=self.limited_sensitivity)
        ttk.Spinbox(limited_sens_frame, from_=0.5, to=10.0, increment=0.5,
                    textvariable=self.limited_sens_var, width=10).pack(side="right")

        # Speed multiplier
        speed_frame = ttk.Frame(settings_frame)
        speed_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(speed_frame, text="Speed Multiplier:").pack(side="left")
        self.speed_var = tk.DoubleVar(value=self.speed_multiplier)
        ttk.Spinbox(speed_frame, from_=0.1, to=3.0, increment=0.1,
                    textvariable=self.speed_var, width=10).pack(side="right")

        # Smoothing factor
        smooth_frame = ttk.Frame(settings_frame)
        smooth_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(smooth_frame, text="Smoothing (0.1-0.9):").pack(side="left")
        self.smooth_var = tk.DoubleVar(value=self.smoothing_factor)
        ttk.Spinbox(smooth_frame, from_=0.1, to=0.9, increment=0.05,
                    textvariable=self.smooth_var, width=10).pack(side="right")

        # Acceleration
        accel_frame = ttk.Frame(settings_frame)
        accel_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(accel_frame, text="Acceleration:").pack(side="left")
        self.accel_var = tk.DoubleVar(value=self.acceleration)
        ttk.Spinbox(accel_frame, from_=0.05, to=0.5, increment=0.01,
                    textvariable=self.accel_var, width=10).pack(side="right")

        # Friction
        friction_frame = ttk.Frame(settings_frame)
        friction_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(friction_frame, text="Friction:").pack(side="left")
        self.friction_var = tk.DoubleVar(value=self.friction)
        ttk.Spinbox(friction_frame, from_=0.7, to=0.95, increment=0.01,
                    textvariable=self.friction_var, width=10).pack(side="right")

        # Auto-click toggle
        auto_click_frame = ttk.Frame(settings_frame)
        auto_click_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(auto_click_frame, text="Auto-click in Limited Mode:").pack(side="left")
        self.auto_click_var = tk.BooleanVar(value=self.auto_click_enabled)
        ttk.Checkbutton(auto_click_frame, variable=self.auto_click_var).pack(side="right")

        # Max distance
        distance_frame = ttk.Frame(settings_frame)
        distance_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(distance_frame, text="Limited Mode Distance:").pack(side="left")
        self.distance_var = tk.IntVar(value=self.max_distance)
        ttk.Spinbox(distance_frame, from_=50, to=500, increment=25,
                    textvariable=self.distance_var, width=10).pack(side="right")

        # Controller Action Settings Frame
        controller_action_frame = ttk.LabelFrame(self.root, text="Jump settings")
        controller_action_frame.pack(pady=10, padx=10, fill="x")

        # Action button selection
        action_btn_frame = ttk.Frame(controller_action_frame)
        action_btn_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(action_btn_frame, text="Jump Button ID:").pack(side="left")
        self.action_btn_var = tk.IntVar(value=self.controller_action_button)
        ttk.Spinbox(action_btn_frame, from_=0, to=15, textvariable=self.action_btn_var, width=10).pack(side="right")

        # Hold duration
        action_duration_frame = ttk.Frame(controller_action_frame)
        action_duration_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(action_duration_frame, text="Hold Duration (seconds):").pack(side="left")
        self.action_duration_var = tk.DoubleVar(value=self.controller_hold_duration)
        ttk.Spinbox(action_duration_frame, from_=0.1, to=5.0, increment=0.1,
                    textvariable=self.action_duration_var, width=10).pack(side="right")

        # Action explanation
        ttk.Label(controller_action_frame, text="Jump: Move to top → Click down → Hold → Release → Return to center",
                  font=("Arial", 8), wraplength=400).pack(pady=5)



        # Button mappings frame
        button_frame = ttk.LabelFrame(self.root, text="Button Mappings")
        button_frame.pack(pady=10, padx=10, fill="x")

        # Click button
        click_frame = ttk.Frame(button_frame)
        click_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(click_frame, text="Click Button ID:").pack(side="left")
        self.click_var = tk.IntVar(value=self.click_button)
        ttk.Spinbox(click_frame, from_=0, to=15, textvariable=self.click_var, width=10).pack(side="right")

        # Limit trigger
        limit_frame = ttk.Frame(button_frame)
        limit_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(limit_frame, text="Movement Mode Trigger:").pack(side="left")
        self.limit_var = tk.IntVar(value=self.limit_trigger_id)
        ttk.Spinbox(limit_frame, from_=0, to=15, textvariable=self.limit_var, width=10).pack(side="right")

        # Stop button
        stop_btn_frame = ttk.Frame(button_frame)
        stop_btn_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(stop_btn_frame, text="Stop Button ID:").pack(side="left")
        self.stop_btn_var = tk.IntVar(value=self.stop_button_id)
        ttk.Spinbox(stop_btn_frame, from_=0, to=15, textvariable=self.stop_btn_var, width=10).pack(side="right")



        # Control buttons
        control_frame = ttk.Frame(self.root)
        control_frame.pack(pady=20)

        self.start_button = ttk.Button(control_frame, text="Start", command=self.start_control)
        self.start_button.pack(side="left", padx=5)

        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_control, state="disabled")
        self.stop_button.pack(side="left", padx=5)

        # Status and mode
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var).pack(pady=5)

        self.mode_var = tk.StringVar(value="Mode: Normal")
        ttk.Label(self.root, textvariable=self.mode_var, font=("Arial", 10, "bold")).pack(pady=2)

        # API info
        api_text = "Windows API" if USE_WINDOWS_API else "PyAutoGUI"
        ttk.Label(self.root, text=f"Mouse API: {api_text}", font=("Arial", 8)).pack(pady=2)

    def refresh_controllers(self):
        pygame.joystick.quit()
        pygame.joystick.init()

        controllers = []
        for i in range(pygame.joystick.get_count()):
            joy = pygame.joystick.Joystick(i)
            controllers.append(f"{i}: {joy.get_name()}")

        self.controller_combo['values'] = controllers
        if controllers:
            self.controller_combo.current(0)
            self.status_var.set(f"Found {len(controllers)} controller(s)")
        else:
            self.status_var.set("No controllers detected")

    def apply_smoothing(self, raw_x, raw_y):
        """Apply multiple layers of smoothing to input"""
        # Add to buffer
        self.input_buffer.append((raw_x, raw_y))
        if len(self.input_buffer) > self.buffer_size:
            self.input_buffer.pop(0)

        # Average buffer values
        if self.input_buffer:
            avg_x = sum(x for x, y in self.input_buffer) / len(self.input_buffer)
            avg_y = sum(y for x, y in self.input_buffer) / len(self.input_buffer)
        else:
            avg_x, avg_y = raw_x, raw_y

        # Apply exponential smoothing
        self.smooth_x = self.smooth_x * self.smoothing_factor + avg_x * (1 - self.smoothing_factor)
        self.smooth_y = self.smooth_y * self.smoothing_factor + avg_y * (1 - self.smoothing_factor)

        return self.smooth_x, self.smooth_y

    def start_control(self):
        if not self.controller_combo.get():
            self.status_var.set("Please select a controller")
            return

        controller_id = int(self.controller_combo.get().split(':')[0])

        try:
            self.controller = pygame.joystick.Joystick(controller_id)
            self.controller.init()

            # Update settings
            self.max_distance = self.distance_var.get()
            self.normal_sensitivity = self.normal_sens_var.get()
            self.limited_sensitivity = self.limited_sens_var.get()
            self.acceleration = self.accel_var.get()
            self.friction = self.friction_var.get()
            self.smoothing_factor = self.smooth_var.get()
            self.speed_multiplier = self.speed_var.get()
            self.click_button = self.click_var.get()
            self.stop_button_id = self.stop_btn_var.get()
            self.limit_trigger_id = self.limit_var.get()
            self.auto_click_enabled = self.auto_click_var.get()

            # Update controller action settings
            self.controller_action_button = self.action_btn_var.get()
            self.controller_hold_duration = self.action_duration_var.get()

            # Update jump settings

            # Reset state
            self.mouse_held = False
            self.limited_mode = False
            self.limited_mode_center = None
            self.current_mouse_pos = list(pyautogui.position())
            self.target_mouse_pos = list(self.current_mouse_pos)
            self.velocity_x = 0.0
            self.velocity_y = 0.0
            self.smooth_x = 0.0
            self.smooth_y = 0.0
            self.input_buffer.clear()
            self.auto_click_active = False
            self.quick_action_pending = False

            # Reset controller action state
            self.controller_action_pending = False
            self.controller_action_phase = 0

            # Reset jump state
            self.jump_pending = False

            self.running = True
            self.thread = threading.Thread(target=self.control_loop, daemon=True)
            self.thread.start()

            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.status_var.set(f"Controller active - ESC to stop, Button {self.controller_action_button} for action")

        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")

    def stop_control(self):
        self.running = False

        if self.mouse_held or self.auto_click_active:
            pyautogui.mouseUp()
            self.mouse_held = False
            self.auto_click_active = False

        if self.controller:
            self.controller.quit()
            self.controller = None

        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_var.set("Stopped")
        self.mode_var.set("Mode: Normal")

    def control_loop(self):
        last_time = time.time()
        prev_limit_trigger = False
        prev_quick_pressed = False
        prev_action_pressed = False  # Track controller action button state
        prev_jump_pressed = False  # Track jump button state

        while self.running:
            try:
                current_time = time.time()
                dt = current_time - last_time
                last_time = current_time

                # Maintain consistent timing
                dt = min(dt, self.frame_time * 2)

                pygame.event.pump()

                # Check for ESC key
                keys = pygame.key.get_pressed()
                if keys[pygame.K_ESCAPE]:
                    self.root.after(0, self.stop_control)
                    break

                # Get raw input
                raw_x = self.controller.get_axis(0) if self.controller else 0
                raw_y = self.controller.get_axis(1) if self.controller else 0

                # Apply deadzone
                if abs(raw_x) < self.deadzone:
                    raw_x = 0
                if abs(raw_y) < self.deadzone:
                    raw_y = 0

                # Apply smoothing
                smooth_x, smooth_y = self.apply_smoothing(raw_x, raw_y)

                # Button handling (only if controller exists)
                click_pressed = False
                stop_pressed = False
                limit_pressed = False
                quick_pressed = False
                action_pressed = False  # Controller action button
                jump_pressed = False  # Jump button

                if self.controller:
                    click_pressed = (self.click_button < self.controller.get_numbuttons() and
                                     self.controller.get_button(self.click_button))
                    stop_pressed = (self.stop_button_id < self.controller.get_numbuttons() and
                                    self.controller.get_button(self.stop_button_id))
                    limit_pressed = (self.limit_trigger_id < self.controller.get_numbuttons() and
                                     self.controller.get_button(self.limit_trigger_id))
                    quick_pressed = (self.quick_action_button < self.controller.get_numbuttons() and
                                     self.controller.get_button(self.quick_action_button))
                    # Check controller action button
                    action_pressed = (self.controller_action_button < self.controller.get_numbuttons() and
                                      self.controller.get_button(self.controller_action_button))
                    # Check jump button
                    jump_pressed = (self.jump_button < self.controller.get_numbuttons() and
                                    self.controller.get_button(self.jump_button))

                if stop_pressed:
                    self.root.after(0, self.stop_control)
                    break

                # Handle controller action - trigger on button press (not hold)
                if action_pressed and not prev_action_pressed:
                    if self.limited_mode and self.limited_mode_center and not self.controller_action_pending:
                        self.controller_action_pending = True
                        self.controller_action_start_time = current_time
                        self.controller_action_phase = 0

                prev_action_pressed = action_pressed

                # Handle jump - trigger on button press (not hold)
                if jump_pressed and not prev_jump_pressed:
                    if self.limited_mode and self.limited_mode_center and not self.controller_action_pending:
                        self.execute_jump(smooth_x, smooth_y)

                prev_jump_pressed = jump_pressed

                # Handle quick action - trigger on button press (not hold)
                if quick_pressed and not prev_quick_pressed:
                    if self.limited_mode and self.limited_mode_center:
                        self.quick_action_pending = False
                        self.quick_action_start_time = current_time

                prev_quick_pressed = quick_pressed

                # Execute quick action if pending
                if self.quick_action_pending:
                    self.execute_quick_action(current_time)

                # Execute controller action if pending
                if self.controller_action_pending:
                    self.execute_controller_action(current_time)

                # Handle jump movement if pending (though now it's instant)
                if self.jump_pending:
                    self.handle_jump_movement(current_time)

                # Mode switching
                if limit_pressed and not prev_limit_trigger:
                    self.limited_mode = True
                    self.limited_mode_center = list(self.screen_center)
                    self.root.after(0, lambda: self.mode_var.set("Mode: Limited"))
                elif not limit_pressed and prev_limit_trigger:
                    self.limited_mode = False
                    self.limited_mode_center = None
                    # Release auto-click when exiting limited mode
                    if self.auto_click_active:
                        pyautogui.mouseUp()
                        self.auto_click_active = False
                    self.root.after(0, lambda: self.mode_var.set("Mode: Normal"))

                prev_limit_trigger = limit_pressed

                # Mouse click handling (manual clicks) - don't interfere with actions
                if not self.quick_action_pending and not self.controller_action_pending:
                    if click_pressed and not self.mouse_held and not self.auto_click_active:
                        pyautogui.mouseDown()
                        self.mouse_held = True
                    elif not click_pressed and self.mouse_held:
                        pyautogui.mouseUp()
                        self.mouse_held = False

                    # Auto-click handling in limited mode
                    if self.limited_mode and self.auto_click_enabled:
                        stick_moving = abs(smooth_x) > 0.02 or abs(smooth_y) > 0.02

                        if stick_moving and not self.auto_click_active and not self.mouse_held:
                            pyautogui.mouseDown()
                            self.auto_click_active = True
                        elif not stick_moving and self.auto_click_active:
                            pyautogui.mouseUp()
                            self.auto_click_active = False

                # Movement calculation (skip if any action in progress)
                if not self.quick_action_pending and not self.controller_action_pending:
                    if self.limited_mode and self.limited_mode_center:
                        self.handle_limited_movement(smooth_x, smooth_y, dt)
                    else:
                        self.handle_normal_movement(smooth_x, smooth_y, dt)

                    # Interpolate toward target position for extra smoothness
                    diff_x = self.target_mouse_pos[0] - self.current_mouse_pos[0]
                    diff_y = self.target_mouse_pos[1] - self.current_mouse_pos[1]

                    self.current_mouse_pos[0] += diff_x * self.interpolation_factor
                    self.current_mouse_pos[1] += diff_y * self.interpolation_factor

                    # Keep within screen bounds
                    screen_width, screen_height = pyautogui.size()
                    self.current_mouse_pos[0] = max(0, min(screen_width - 1, self.current_mouse_pos[0]))
                    self.current_mouse_pos[1] = max(0, min(screen_height - 1, self.current_mouse_pos[1]))

                    # Move mouse using smooth API
                    smooth_move_mouse(self.current_mouse_pos[0], self.current_mouse_pos[1])

                # Sleep for consistent frame rate
                time.sleep(self.frame_time)

            except Exception as e:
                print(f"Control loop error: {e}")
                self.root.after(0, self.stop_control)
                break

    def handle_normal_movement(self, smooth_x, smooth_y, dt):
        """Handle normal movement mode with velocity-based system"""
        sensitivity = self.normal_sensitivity * self.speed_multiplier

        if abs(smooth_x) > 0.01 or abs(smooth_y) > 0.01:
            # Calculate target velocity
            target_vel_x = smooth_x * sensitivity
            target_vel_y = smooth_y * sensitivity * 0.4

            # Apply acceleration
            self.velocity_x += (target_vel_x - self.velocity_x) * self.acceleration
            self.velocity_y += (target_vel_y - self.velocity_y) * self.acceleration
        else:
            # Apply friction
            self.velocity_x *= self.friction
            self.velocity_y *= self.friction

        # Limit max velocity
        velocity_mag = math.sqrt(self.velocity_x ** 2 + self.velocity_y ** 2)
        if velocity_mag > self.max_velocity:
            scale = self.max_velocity / velocity_mag
            self.velocity_x *= scale
            self.velocity_y *= scale

        # Update target position
        self.target_mouse_pos[0] += self.velocity_x
        self.target_mouse_pos[1] += self.velocity_y

    def handle_limited_movement(self, smooth_x, smooth_y, dt):
        """Handle limited movement mode - X=horizontal, Y=vertical within restricted area"""
        sensitivity = self.limited_sensitivity * self.speed_multiplier
        center_x, center_y = self.limited_mode_center

        # Use X-axis for horizontal movement, Y-axis for vertical movement
        if abs(smooth_x) > 0.01 or abs(smooth_y) > 0.01:
            # Move within constrained area using both axes
            target_vel_x = smooth_x * sensitivity
            target_vel_y = smooth_y * sensitivity

            self.velocity_x += (target_vel_x - self.velocity_x) * self.acceleration
            self.velocity_y += (target_vel_y - self.velocity_y) * self.acceleration

            # Calculate new position
            new_x = self.target_mouse_pos[0] + self.velocity_x
            new_y = self.target_mouse_pos[1] + self.velocity_y

            # Constrain to circle
            dx = new_x - center_x
            dy = new_y - center_y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance > self.max_distance:
                scale = self.max_distance / distance
                new_x = center_x + dx * scale
                new_y = center_y + dy * scale
                # Reduce velocity when hitting boundary
                self.velocity_x *= 0.5
                self.velocity_y *= 0.5

            self.target_mouse_pos[0] = new_x
            self.target_mouse_pos[1] = new_y
        else:
            # Return to center
            dx = center_x - self.target_mouse_pos[0]
            dy = center_y - self.target_mouse_pos[1]
            distance = math.sqrt(dx * dx + dy * dy)

            if distance > 2:
                return_force = min(distance * 0.1, self.return_speed)
                self.velocity_x = (dx / distance) * return_force
                self.velocity_y = (dy / distance) * return_force

                self.target_mouse_pos[0] += self.velocity_x
                self.target_mouse_pos[1] += self.velocity_y
            else:
                self.target_mouse_pos[0] = center_x
                self.target_mouse_pos[1] = center_y
                self.velocity_x = 0
                self.velocity_y = 0

    def execute_quick_action(self, current_time):
        """Execute the quick action with proper timing"""
        elapsed = current_time - self.quick_action_start_time

        if elapsed < 0.1:  # Phase 1: Move to top (first 100ms)
            center_x, center_y = self.limited_mode_center
            top_x = center_x
            top_y = center_y - self.max_distance + self.quick_action_distance

            # Instantly move to top position
            smooth_move_mouse(top_x, top_y)
            self.current_mouse_pos[0] = top_x
            self.current_mouse_pos[1] = top_y
            self.target_mouse_pos[0] = top_x
            self.target_mouse_pos[1] = top_y

        elif elapsed < 0.15:  # Phase 2: Click (100-150ms)
            # Ensure any existing mouse state is cleared
            if self.mouse_held or self.auto_click_active:
                pyautogui.mouseUp()
                self.mouse_held = False
                self.auto_click_active = False

            # Perform the click
            pyautogui.click()

        elif elapsed < 0.25:  # Phase 3: Brief pause (150-250ms)
            pass  # Just wait a bit

        else:  # Phase 4: Return to center (after 250ms)
            center_x, center_y = self.limited_mode_center

            # Return to center of limited area
            smooth_move_mouse(center_x, center_y)
            self.current_mouse_pos[0] = center_x
            self.current_mouse_pos[1] = center_y
            self.target_mouse_pos[0] = center_x
            self.target_mouse_pos[1] = center_y

            # Reset velocity and complete the action
            self.velocity_x = 0
            self.velocity_y = 0
            self.quick_action_pending = False

    def execute_controller_action(self, current_time):
        """Execute the controller-triggered action with proper timing and phases"""
        elapsed = current_time - self.controller_action_start_time

        if self.controller_action_phase == 0:  # Phase 0: Move to top
            center_x, center_y = self.limited_mode_center
            top_x = center_x
            top_y = center_y - self.max_distance + self.quick_action_distance

            # Instantly move to top position
            smooth_move_mouse(top_x, top_y)
            self.current_mouse_pos[0] = top_x
            self.current_mouse_pos[1] = top_y
            self.target_mouse_pos[0] = top_x
            self.target_mouse_pos[1] = top_y

            # Move to next phase after 50ms
            if elapsed >= 0.05:
                self.controller_action_phase = 1
                # Clear any existing mouse state before clicking
                if self.mouse_held or self.auto_click_active:
                    pyautogui.mouseUp()
                    self.mouse_held = False
                    self.auto_click_active = False

        elif self.controller_action_phase == 1:  # Phase 1: Click down
            # Press mouse button down
            pyautogui.mouseDown()
            self.controller_action_phase = 2

        elif self.controller_action_phase == 2:  # Phase 2: Hold for specified duration
            # Hold the click for the configured duration
            if elapsed >= (0.05 + self.controller_hold_duration):
                self.controller_action_phase = 3

        elif self.controller_action_phase == 3:  # Phase 3: Release click
            # Release mouse button
            pyautogui.mouseUp()
            self.controller_action_phase = 4

        elif self.controller_action_phase == 4:  # Phase 4: Return to center
            center_x, center_y = self.limited_mode_center

            # Return to center of limited area
            smooth_move_mouse(center_x, center_y)
            self.current_mouse_pos[0] = center_x
            self.current_mouse_pos[1] = center_y
            self.target_mouse_pos[0] = center_x
            self.target_mouse_pos[1] = center_y

            # Reset velocity and complete the action
            self.velocity_x = 0
            self.velocity_y = 0
            self.controller_action_pending = False
            self.controller_action_phase = 0

    def execute_jump(self, stick_x, stick_y):
        """Execute jump movement based on stick direction - INSTANT 45° movement"""
        if not self.limited_mode or not self.limited_mode_center:
            return

        center_x, center_y = self.limited_mode_center

        # Determine jump direction based on stick input
        if abs(stick_x) < 0.1 and abs(stick_y) < 0.1:
            # Standing still - jump straight up
            self.jump_target_x = center_x
            self.jump_target_y = center_y
        else:
            # Moving - jump at EXACTLY 45-degree angle in the direction of stick movement
            # Normalize the stick input to get pure direction
            magnitude = math.sqrt(stick_x * stick_x + stick_y * stick_y)
            if magnitude > 0:
                # Get normalized direction
                norm_x = stick_x / magnitude
                norm_y = stick_y / magnitude

                # Apply jump distance in that exact direction
                self.jump_target_x = center_x + norm_x
                self.jump_target_y = center_y + norm_y
            else:
                # Fallback to straight up
                self.jump_target_x = center_x
                self.jump_target_y = center_y

        # Constrain jump target to circular boundary
        dx = self.jump_target_x - center_x
        dy = self.jump_target_y - center_y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance > self.max_distance:
            scale = self.max_distance / distance
            self.jump_target_x = center_x + dx * scale
            self.jump_target_y = center_y + dy * scale

        # INSTANT movement - no smooth animation, just teleport
        smooth_move_mouse(self.jump_target_x, self.jump_target_y)
        self.current_mouse_pos[0] = self.jump_target_x
        self.current_mouse_pos[1] = self.jump_target_y
        self.target_mouse_pos[0] = self.jump_target_x
        self.target_mouse_pos[1] = self.jump_target_y

        # Reset velocity
        self.velocity_x = 0
        self.velocity_y = 0

        # No pending state needed since it's instant
        self.jump_pending = False

    def handle_jump_movement(self, current_time):
        """Handle smooth jump movement to target position"""
        elapsed = current_time - self.jump_start_time
        jump_duration = 0.3  # 300ms jump duration

        if elapsed < jump_duration:
            # Smoothly interpolate to jump target
            progress = elapsed / jump_duration
            # Use easing function for smoother movement
            eased_progress = 1 - (1 - progress) ** 3  # Ease-out cubic

            start_x = self.limited_mode_center[0]
            start_y = self.limited_mode_center[1]

            current_x = start_x + (self.jump_target_x - start_x) * eased_progress
            current_y = start_y + (self.jump_target_y - start_y) * eased_progress

            # Update positions
            smooth_move_mouse(current_x, current_y)
            self.current_mouse_pos[0] = current_x
            self.current_mouse_pos[1] = current_y
            self.target_mouse_pos[0] = current_x
            self.target_mouse_pos[1] = current_y
        else:
            # Jump complete - ensure we're at target position
            smooth_move_mouse(self.jump_target_x, self.jump_target_y)
            self.current_mouse_pos[0] = self.jump_target_x
            self.current_mouse_pos[1] = self.jump_target_y
            self.target_mouse_pos[0] = self.jump_target_x
            self.target_mouse_pos[1] = self.jump_target_y

            # Reset velocity and complete jump
            self.velocity_x = 0
            self.velocity_y = 0
            self.jump_pending = False

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def on_closing(self):
        self.stop_control()
        pygame.quit()
        self.root.destroy()


if __name__ == "__main__":
    try:
        import pygame
        import pyautogui
    except ImportError:
        print("Missing packages. Install with: pip install pygame pyautogui")
        exit(1)

    app = ControllerMouseControl()
    app.run()
