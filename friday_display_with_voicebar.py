import pygame
import sys
import threading
import time
import math
import pyaudio
import numpy as np
from kitt_voicebox import draw_voice_bars
from friday import ask_friday, friday_is_thinking
from display_bridge import chat_queue
import subprocess



desired_width = 1280
desired_height = 720
fullscreen = False

pygame.init()

# Launch summarizer at startup (non-blocking)
try:
    subprocess.Popen(["python", "memory_summarizer.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
except Exception as e:
    print(f"[⚠️] Failed to run memory_summarizer.py: {e}")
    
screen = pygame.display.set_mode((1280, 720))
pygame.display.set_caption("Friday Display Rebuild")
clock = pygame.time.Clock()
input_focused = False

FRIDAY_DISPLAY_VERSION = "2.0.0"
DISPLAY_NOTES = "Display matched with memory-aware Friday core. No breaking changes."

# Friday thinking animation
# friday_is_thinking = False  # placeholder until she's connected

# Tracks when to post Friday's boot messages
post_boot_messages = False
boot_message_timer = 0
boot_message_stage = 0

# Layout Rects

# Dashboard
dashboardPanel = pygame.Rect(0, 0, 1265, 680)  # x, y, width, height

# Right countdown
statusPwrLabel = pygame.Rect(1196, 22, 66, 26)  # x = right side, y = top
statusNETLabel = pygame.Rect(1196, 48, 66, 26)
statusAUXLabel = pygame.Rect(1196, 77, 66, 26)
statusCPULabel = pygame.Rect(1196, 102, 66, 26)

# Voicebox lights — Left side
lightAIRlabel = pygame.Rect(90, 13, 62, 32)  # x = left side, y = top row
lightAIRlabel.center = (90 + 25 // 2, 13 + 13 // 2)

lightOILLabel = pygame.Rect(91, 112, 60, 32)
lightOILLabel.center = (91 + 24 // 2, 112 + 13 // 2)

lightP1Label = pygame.Rect(95, 247, 50, 32)
lightP1Label.center = (95 + 20 // 2, 247 + 13 // 2)

lightP2Label = pygame.Rect(95, 369, 50, 32)
lightP2Label.center = (95 + 20 // 2, 369 + 13 // 2)

# Voicebox lights — Right side
lightS1Label = pygame.Rect(391, 13, 50, 32)  # x = right side, y = top row
lightS1Label.center = (391 + 20 // 2, 13 + 13 // 2)

lightS2Label = pygame.Rect(391, 112, 50, 32)
lightS2Label.center = (391 + 20 // 2, 112 + 13 // 2)

lightP3Label = pygame.Rect(391, 247, 50, 32)
lightP3Label.center = (391 + 20 // 2, 247 + 13 // 2)

lightP4Label = pygame.Rect(391, 369, 50, 32)
lightP4Label.center = (391 + 20 // 2, 369 + 13 // 2)


# Unused placeholder
# Label1 = pygame.Rect(223, 369, 45, 13)  # x, y, width, height — currently not used

# Cruise Lights
cruiseAutoLabel = pygame.Rect(200, 320, 100, 28)        # x = cruise panel, y = top
CruiseNormalLabel = pygame.Rect(200, 355, 100, 28)
cruisePursuitLabel = pygame.Rect(200, 390, 100, 28)

# Input text and scroll state
input_text = ""
input_lines = []
input_scroll_offset = 0
input_line_height = 20
input_cursor_visible = True

# Input box
inputBox = pygame.Rect(61, 481, 1151, 170)  # bottom section

# Chat
chatPanel = pygame.Rect(496, 22, 655, 350)  # top-right chat area

# Chat Font Colors
FRIDAY_COLOR = (255, 60, 60)  # Bright red
USER_COLOR = (60, 160, 255)   # Blue

# Actual voicebox center panel
voiceBarPanel = pygame.Rect(161, 22, 182, 264)

# Dim of Cruise Lights
ORANGE_DIM = (100, 60, 0)
YELLOW_DIM = (100, 100, 40)
BLUE_DIM = (0, 40, 100)

# Active of Cruise Lights
ORANGE_ACTIVE = (255, 120, 0)
YELLOW_ACTIVE = (255, 255, 60)
BLUE_ACTIVE = (0, 90, 255)

# Wraps long input text into multiple lines to fit input box width
def wrap_input_text(text, font, max_width):
    words = text.split(" ")
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + word + " "
        if font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line.strip())
            current_line = word + " "
    lines.append(current_line.strip())
    return lines


# Sunken effect for chat and input panels
def draw_sunken_rect(rect, highlight=(80, 80, 80), shadow=(10, 10, 10)):
    # Outer top-left highlight
    pygame.draw.line(screen, highlight, rect.topleft, rect.topright)
    pygame.draw.line(screen, highlight, rect.topleft, rect.bottomleft)

    # Inner bottom-right shadow
    pygame.draw.line(screen, shadow, rect.bottomleft, rect.bottomright)
    pygame.draw.line(screen, shadow, rect.topright, rect.bottomright)

# Apply the effect
draw_sunken_rect(chatPanel)
draw_sunken_rect(inputBox)

# Startup animation: lights up status lights and voicebox lights in order
def update_startup_sequence(frame_count):
    delay = 15  # frames between each step

    if frame_count < len(status_lights) * delay:
        index = frame_count // delay
        status_active[index] = True

    elif frame_count < (len(status_lights) + len(voicebox_pairs)) * delay:
        index = (frame_count - len(status_lights) * delay) // delay
        voicebox_active[index] = True
    else:
        global startup_complete, post_boot_messages, boot_message_timer, boot_message_stage
        if not startup_complete:
            startup_complete = True
            post_boot_messages = True
            boot_message_timer = 0
            boot_message_stage = 0


# Shutdown animation: turns off lights in reverse order
def update_shutdown_sequence(frame_count):
    delay = 15  # frames between each step

    total = len(status_lights) + len(voicebox_pairs)
    step = frame_count // delay

    if step < len(voicebox_pairs):
        index = len(voicebox_pairs) - 1 - step
        voicebox_active[index] = False
    elif step < total:
        index = len(status_lights) - 1 - (step - len(voicebox_pairs))
        status_active[index] = False
    else:
        global shutdown_triggered, startup_complete
        shutdown_triggered = False
        startup_complete = False

        # Fully clear lights and dashboard visuals
        for i in range(len(status_active)):
            status_active[i] = False
        for i in range(len(voicebox_active)):
            voicebox_active[i] = False
        
# Light states
status_lights = [statusPwrLabel, statusNETLabel, statusAUXLabel, statusCPULabel]
voicebox_pairs = [
    (lightAIRlabel, lightS1Label),
    (lightOILLabel, lightS2Label),
    (lightP1Label, lightP3Label),
    (lightP2Label, lightP4Label),
]

status_active = [False] * len(status_lights)
voicebox_active = [False] * len(voicebox_pairs)

startup_complete = False
shutdown_triggered = False

# Color definitions
BLACK = (0, 0, 0)
DARK_GREY = (30, 30, 30)
SOFT_GREY = (60, 60, 60)
RED = (255, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)

# Chat content and scroll state
chatlog = []
chat_scroll_offset = 0
chat_line_height = 20

# Voicebar Threaded Surface
voice_surface = pygame.Surface((voiceBarPanel.width, voiceBarPanel.height))

font = pygame.font.SysFont("Segoe UI Emoji", 18)

status_labels_text = ["PWR", "NET", "AUX", "CPU"]


# Loops in a separate thread to continuously animate the voicebar
def voicebar_loop():
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100

    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)

    try:
        while True:
            try:
                data = np.frombuffer(stream.read(CHUNK, exception_on_overflow=False), dtype=np.int16)
                volume = np.linalg.norm(data) / CHUNK
                threshold = 7.7
                scale = 55

                if volume < threshold:
                    level = 0.0
                else:
                    level = max(0.0, min((volume - threshold) / scale, 1.0))

                center_level = level
                side_level = (level ** 1.25) * 1
                draw_voice_bars(voice_surface, center_level, side_level)

                time.sleep(1 / 60)  # <-- moved back under 'while True'

            except Exception as stream_error:
                print("Stream read error:", stream_error)
                draw_voice_bars(voice_surface, 0.0, 0.0)
                time.sleep(1 / 60)

    except Exception as e:
        print("Voicebar loop error:", e)
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        
        threading.Thread(target=voicebar_loop, daemon=True).start()
        
        # Center bar gets raw level
        center_level = level

        # Side bars: softened curve, slightly reduced max
        side_level = (level ** 1.25) * 0.85

voice_thread = threading.Thread(target=voicebar_loop, daemon=True)
voice_thread.start()

# Draws the full dashboard layout and UI based on current state
def draw_layout():
    screen.fill(DARK_GREY)

    # If system is cold (after shutdown), skip drawing
    if not startup_complete and not any(status_active) and not any(voicebox_active):
        pygame.draw.rect(screen, BLACK, dashboardPanel)
        return

    # Dashboard background: dark during startup/shutdown, grey when active
    if startup_complete and not shutdown_triggered:
        pygame.draw.rect(screen, SOFT_GREY, dashboardPanel, border_radius=10)
    else:
        pygame.draw.rect(screen, BLACK, dashboardPanel)

    # Chat and input box backgrounds
    pygame.draw.rect(screen, BLACK, chatPanel, border_radius=6)
    pygame.draw.rect(screen, BLACK, inputBox, border_radius=6)

    # Draw chat messages with scroll
    clip_rect = chatPanel
    screen.set_clip(clip_rect)  # Limit drawing to chat area

    visible_lines = chatlog
    start_y = chatPanel.y + chat_scroll_offset
    
    # Chat colors
    for i, line in enumerate(visible_lines):
        # Determine the role of the current or previous line
        if i == 0:
            last_role = None
        else:
            prev_line = visible_lines[i - 1]
            if prev_line.startswith("Friday:"):
                last_role = "friday"
            elif prev_line.startswith("You:"):
                last_role = "user"
            elif prev_line.startswith("System:") or prev_line.startswith("[System]"):
                last_role = "system"

        if line.startswith("Friday:"):
            color = FRIDAY_COLOR
            last_role = "friday"
        elif line.startswith("You:"):
            color = USER_COLOR
            last_role = "user"
        elif line.startswith("System:") or line.startswith("[System]"):
            color = WHITE
            last_role = "system"
        elif last_role == "friday":
            color = FRIDAY_COLOR
        elif last_role == "user":
            color = USER_COLOR
        elif last_role == "system":
            color = WHITE
        else:
            color = WHITE



        text_surface = font.render(line, True, color)
        screen.blit(text_surface, (chatPanel.x + 10, start_y + i * chat_line_height))


    screen.set_clip(None)  # Restore full drawing area

    # Draw wrapped input text with scroll
    input_lines = wrap_input_text(input_text, font, inputBox.width - 20)

    screen.set_clip(inputBox)
    start_y = inputBox.y + 10 + input_scroll_offset

    for i, line in enumerate(input_lines):
        text_surface = font.render(line, True, WHITE)
        screen.blit(text_surface, (inputBox.x + 10, start_y + i * input_line_height))

    screen.set_clip(None)

    # Apply sunken effect to chat and input boxes
    draw_sunken_rect(chatPanel)
    draw_sunken_rect(inputBox)

    # Skip cruise lights if system is fully shut down
    if not startup_complete and not any(status_active) and not any(voicebox_active):
        return

    # Cruise lights (NORMAL CRUISE activates after startup)
    auto_color = ORANGE_DIM
    normal_color = YELLOW_ACTIVE if startup_complete and not shutdown_triggered else YELLOW_DIM
    pursuit_color = BLUE_DIM

    # AUTO CRUISE light
    pygame.draw.rect(screen, auto_color, cruiseAutoLabel, border_radius=6)
    text_auto = font.render("AUTO CRUISE", True, BLACK)
    screen.blit(text_auto, text_auto.get_rect(center=cruiseAutoLabel.center))

    # NORMAL CRUISE light
    pygame.draw.rect(screen, normal_color, CruiseNormalLabel, border_radius=6)
    text_normal = font.render("NORMAL", True, BLACK)
    screen.blit(text_normal, text_normal.get_rect(center=CruiseNormalLabel.center))

    # PURSUIT light
    pygame.draw.rect(screen, pursuit_color, cruisePursuitLabel, border_radius=6)
    text_pursuit = font.render("PURSUIT", True, BLACK)
    screen.blit(text_pursuit, text_pursuit.get_rect(center=cruisePursuitLabel.center))

    # Far-right status lights (PWR, NET, AUX, CPU) with labels
    for i, label in enumerate(status_lights):
        if status_active[i]:
            if i == 3:  # CPU
                if friday_is_thinking:
                    # Breathing red effect
                    pulse = (math.sin(thinking_pulse_timer / 10) + 1) / 2  # range: 0 to 1
                    intensity = int(60 + pulse * 195)  # range: 60–255
                    color = (intensity, 0, 0)
                else:
                    color = (255, 60, 60)
            else:
                color = (255, 220, 100)
            pygame.draw.rect(screen, color, label, border_radius=3)


        # Draw text inside each status label
        text = font.render(status_labels_text[i], True, BLACK if status_active[i] else (180, 180, 180))
        text_rect = text.get_rect(center=label.center)
        screen.blit(text, text_rect)

    # Voicebox side lights with labels and dimmed fallback colors
    voicebox_labels_left = ["AIR", "OIL", "P1", "P2"]
    voicebox_labels_right = ["S1", "S2", "P3", "P4"]
    voicebox_colors = [(255, 200, 0), (255, 0, 0)]      # Active: Yellow, Red
    voicebox_dimmed = [(80, 60, 10), (80, 0, 0)]        # Dimmed versions

    for i, (left, right) in enumerate(voicebox_pairs):
        color_index = 0 if i < 2 else 1
        fill_color = voicebox_colors[color_index] if voicebox_active[i] else voicebox_dimmed[color_index]

        # Draw left voicebox light
        pygame.draw.rect(screen, fill_color, left, border_radius=6)
        left_text = font.render(voicebox_labels_left[i], True, BLACK)
        screen.blit(left_text, left_text.get_rect(center=left.center))

        # Draw right voicebox light
        pygame.draw.rect(screen, fill_color, right, border_radius=6)
        right_text = font.render(voicebox_labels_right[i], True, BLACK)
        screen.blit(right_text, right_text.get_rect(center=right.center))

    # Draw animated voicebar
    screen.blit(voice_surface, (voiceBarPanel.x, voiceBarPanel.y))

import os  # at the top of the file if not already imported

def handle_friday_response(message):
    global friday_is_thinking
    friday_is_thinking = True

    try:
        # Step 1: Intercept Confirm End Session before it reaches Friday
        if message.strip().lower() == "confirm end session":
            # Let Friday handle the shutdown logic
            response = ask_friday(message)

            # Then immediately shut down the display
            pygame.quit()
            os._exit(0)

        # Step 2: Let Friday process other messages
        response = ask_friday(message)

        # Step 3: If there's no response, do nothing
        if response is None or response.strip() == "":
            return

        # Step 4: Preserve paragraph spacing
        paragraphs = response.split("\n")
        for i, paragraph in enumerate(paragraphs):
            if paragraph.strip() == "":
                chatlog.append("")  # blank line
                continue

            prefix = "Friday: " if i == 0 else ""
            wrapped_lines = wrap_input_text(prefix + paragraph, font, chatPanel.width - 20)
            for line in wrapped_lines:
                chatlog.append(line)

    finally:
        # Step 5: Always reset the thinking flag, no matter what
        friday_is_thinking = False

    # Step 6: Scroll to bottom
    global chat_scroll_offset
    chat_scroll_offset = -max(0, len(chatlog) * chat_line_height - chatPanel.height)






# Runtime flags and counters
running = True
start_time = pygame.time.get_ticks()
frame_count = 0
chatlog.append("Friday: Brain connected.")

# Main Loop
try:
    while running:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if chat_queue:
                for msg in chat_queue:
                    chatlog.append(msg)
                chat_queue.clear()

            if event.type == pygame.MOUSEBUTTONDOWN:
                input_focused = inputBox.collidepoint(event.pos)

            if event.type == pygame.MOUSEWHEEL:
                mouse_pos = pygame.mouse.get_pos()

                if chatPanel.collidepoint(mouse_pos):
                    chat_scroll_offset += event.y * chat_line_height

                elif inputBox.collidepoint(mouse_pos):
                    input_scroll_offset += event.y * input_line_height

            # ✅ Alt+Enter toggles fullscreen
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN and pygame.key.get_mods() & pygame.KMOD_ALT:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.RESIZABLE)
                    else:
                        screen = pygame.display.set_mode((desired_width, desired_height), pygame.RESIZABLE)

            # ✅ Optional: Listen for manual window resizing
            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                # You can dynamically recalculate element positions/sizes here if needed:
                # new_width, new_height = event.size
                # (not yet implemented)

            # ✅ Permanent backspace handler (independent of modifier logic)
            if event.type == pygame.KEYDOWN and input_focused and event.key == pygame.K_BACKSPACE:
                if len(input_text) > 0:
                    input_text = input_text[:-1]

            if event.type == pygame.KEYDOWN and input_focused:
                if event.key == pygame.K_v and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    try:
                        import pyperclip
                        pasted_text = pyperclip.paste()
                        input_text += pasted_text
                    except Exception as e:
                        print(f"[Paste Error] {e}")
                if event.key == pygame.K_RETURN:
                    if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                        input_text += "\n"
                    else:
                        user_message = input_text.strip()
                        if user_message:
                            wrapped_user_lines = wrap_input_text("You: " + user_message, font, chatPanel.width - 20)
                            for line in wrapped_user_lines:
                                chatlog.append(line)
                            input_text = ""
                            input_scroll_offset = 0

                            # Correctly start background thread for Friday's response
                            threading.Thread(target=handle_friday_response, args=(user_message,), daemon=True).start()

                else:
                    if event.unicode.isprintable():
                        input_text += event.unicode

        # Handle startup light sequence
        if not startup_complete:
            update_startup_sequence(frame_count)

        # Handle shutdown light sequence
        elif shutdown_triggered:
            update_shutdown_sequence(frame_count)

        # Draw all UI elements based on current system state
        draw_layout()

        # Clamp input scroll offset
        visible_lines = inputBox.height // input_line_height
        max_input_scroll = 0
        min_input_scroll = -max(0, len(input_lines) * input_line_height - inputBox.height + 20)
        input_scroll_offset = max(min(input_scroll_offset, max_input_scroll), min_input_scroll)

        # Handle Friday's boot messages after startup completes
        if post_boot_messages:
            boot_message_timer += 1

            if boot_message_stage == 0 and boot_message_timer >= 60:  # Wait 1 sec before first message
                chatlog.append("Friday: System boot complete.")
                boot_message_stage = 1

            elif boot_message_stage == 1 and boot_message_timer >= 180:  # Wait 2 more seconds (total 3s)
                chatlog.append("Friday: All systems online.")
                post_boot_messages = False

        # Clamp scroll offset
        max_scroll = 0
        min_scroll = -max(0, len(chatlog) * chat_line_height - chatPanel.height)
        chat_scroll_offset = max(min(chat_scroll_offset, max_scroll), min_scroll)

        # Update display and frame count
        pygame.display.flip()
        clock.tick(60)
        frame_count += 1
        if friday_is_thinking:
            thinking_pulse_timer += 1
        else:
            thinking_pulse_timer = 0

except Exception as e:
    import traceback
    error_details = traceback.format_exc()

    # Print to terminal
    print("[Display Crash Detected]")
    print(error_details)

    # Send to display
    try:
        from display_bridge import forward_system_message
        forward_system_message("[Display Crash Detected]")
        for line in error_details.strip().splitlines():
            forward_system_message(line)
    except Exception as inner:
        print(f"[Crash Handling Failed] {inner}")



