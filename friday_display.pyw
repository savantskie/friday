import pygame
import sys
import os
import time
import threading
import pyperclip
import importlib
import ripple_test_fixed as visualizer


def send_to_friday(user_input):
    try:
        return friday.ask_friday(user_input)
    except Exception as e:
        return f"[Error: Failed to talk to Friday directly: {e}]"

def background_response(user_msg):
    global friday_connected, last_success_time
    response = send_to_friday(user_msg)

    if not response:
        chatlog.append("⚠️ Friday Error: No response received.")
        return

    if isinstance(response, str) and response.startswith("[Error:"):
        chatlog.append(f"⚠️ Friday Error: {response.strip()}")
    else:
        friday_connected = True
        last_success_time = pygame.time.get_ticks()
        friday_typing["message"] = f"Friday: {response.strip()}"
        friday_typing["start_time"] = pygame.time.get_ticks()

pygame.init()
friday_connected = False
last_success_time = 0
connection_timeout = 10000

startup_first_draw_time = None

MONITOR_WIDTH = 2560
MONITOR_HEIGHT = 1440
VERTICAL_MARGIN = 50
BORDER_THICKNESS = 10
BORDER_RADIUS = 10
WIDTH = MONITOR_WIDTH // 2
HEIGHT = MONITOR_HEIGHT - 2 * VERTICAL_MARGIN

os.environ['SDL_VIDEO_WINDOW_POS'] = f'{MONITOR_WIDTH//2},{VERTICAL_MARGIN}'
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Friday Display")

BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 160, 255)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)

font_small = pygame.font.Font(None, 24)
font_medium = pygame.font.Font(None, 36)

chat_scroll_offset = 0
scroll_speed = 20
auto_scroll = True
input_text = ""
input_chars = []
chatlog = []
input_focused = False
startup_lines_shown = False
allow_llm_output = False
input_scroll_offset = 0


friday_typing = {
    "message": "",
    "start_time": 0,
    "chars_per_second": 60  # adjust typing speed here
}    

visualizer_area = pygame.Rect(10, HEIGHT // 3 + 10, WIDTH - 20, HEIGHT // 3 - 20)

chat_area = pygame.Rect(
    WIDTH // 2 + 10,
    10,
    WIDTH // 2 - 20,
    visualizer_area.top - 20
)

IMAGE_BOX = pygame.Rect(
    10,
    10,
    WIDTH // 2 - 20,
    visualizer_area.top - 20
)

input_box = pygame.Rect(
    (WIDTH - (WIDTH - 20 - 2 * BORDER_THICKNESS)) // 2,
    HEIGHT - (HEIGHT // 3 - 20 - 2 * BORDER_THICKNESS) - 10,
    WIDTH - 20 - 2 * BORDER_THICKNESS,
    HEIGHT // 3 - 20 - 2 * BORDER_THICKNESS
)

image_surface = pygame.Surface((IMAGE_BOX.width, IMAGE_BOX.height))
image_surface.fill(BLACK)

def scroll_to_bottom():
    global chat_scroll_offset
    chat_height = draw_chatlog()
    visible_height = chat_area.height
    max_scroll = max(0, chat_height - visible_height)
    chat_scroll_offset = -max_scroll

def wrap_text(text, font, max_width):
    lines = []
    words = text.split(' ')
    current_line = ''
    for word in words:
        test_line = current_line + word + ' '
        if font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line.strip())
            while font.size(word)[0] > max_width:
                for i in range(1, len(word)):
                    if font.size(word[:i])[0] > max_width:
                        lines.append(word[:i - 1])
                        word = word[i - 1:]
                        break
                else:
                    break
            current_line = word + ' '
    if current_line:
        lines.append(current_line.strip())
    return lines

def draw_chatlog():
    global chat_scroll_offset

    pygame.draw.rect(screen, BLACK, chat_area)
    pygame.draw.rect(screen, RED, chat_area, 2, border_radius=8)

    padding = 10
    line_spacing = font_small.get_height() + 2
    rendered_lines = []

    # Wrap and store all lines from chatlog
    for msg in chatlog:
        is_user = msg.startswith("You:")
        wrapped = wrap_text(msg, font_small, chat_area.width - 2 * padding)
        for line in wrapped:
            rendered_lines.append((line, is_user))

    # Add Friday's current typing message if active
    if friday_typing["message"]:
        elapsed = pygame.time.get_ticks() - friday_typing["start_time"]
        chars_to_show = int((elapsed / 1000) * friday_typing["chars_per_second"])
        shown_text = friday_typing["message"][:chars_to_show]

        if chars_to_show >= len(friday_typing["message"]):
            chatlog.append(friday_typing["message"])
            friday_typing["message"] = ""
        else:
            wrapped = wrap_text(shown_text, font_small, chat_area.width - 2 * padding)
            for line in wrapped:
                rendered_lines.append((line, False))  # False = Friday's line (red)

    # Total height of all lines
    total_height = len(rendered_lines) * line_spacing
    max_scroll = max(0, total_height - chat_area.height)

    # Clamp scroll so we can't scroll past the bottom
    soft_margin = 100  # allow some scroll past the edges
    chat_scroll_offset = max(-max_scroll - soft_margin, min(chat_scroll_offset, soft_margin))

    # Clip drawing to chat area
    screen.set_clip(pygame.Rect(chat_area.x + 1, chat_area.y + 1, chat_area.width - 2, chat_area.height - 2))

    # Calculate starting Y from the bottom, scroll upward
    start_y = chat_area.bottom - padding - total_height + chat_scroll_offset
    y = start_y

    for line, is_user in rendered_lines:
        surf = font_small.render(line, True, BLUE if is_user else RED)
        screen.blit(surf, (chat_area.x + padding, y))
        y += line_spacing

    screen.set_clip(None)
    return total_height

def draw_input_box():
    pygame.draw.rect(screen, BLACK, input_box)
    pygame.draw.rect(screen, RED, input_box, 2, border_radius=8)

    padding = 10
    line_spacing = font_medium.get_height() + 2
    max_width = input_box.width - 2 * padding
    lines = wrap_text(input_text, font_medium, max_width)
    max_visible_lines = input_box.height // line_spacing

    # Clamp scroll offset
    global input_scroll_offset
    max_offset = max(0, len(lines) - max_visible_lines)
    input_scroll_offset = max(0, min(input_scroll_offset, max_offset))

    visible_lines = lines[input_scroll_offset:input_scroll_offset + max_visible_lines]

    y = input_box.y + padding
    for line in visible_lines:
        rendered = font_medium.render(line, True, RED)
        screen.blit(rendered, (input_box.x + padding, y))
        y += line_spacing

def draw_image_box():
    pygame.draw.rect(screen, BLACK, IMAGE_BOX)
    screen.blit(image_surface, (IMAGE_BOX.x, IMAGE_BOX.y))
    pygame.draw.rect(screen, RED, IMAGE_BOX, 2, border_radius=8)

def draw_outer_border():
    pygame.draw.rect(screen, RED, screen.get_rect(), BORDER_THICKNESS, border_radius=BORDER_RADIUS)
    
def draw_startup_lines():
    global startup_lines_shown, allow_llm_output
    if startup_lines_shown:
        return

    # Static message to show at startup
    friday_typing["message"] = "Friday: Friday is online."
    friday_typing["start_time"] = pygame.time.get_ticks()

    while friday_typing["message"]:
        pygame.event.pump()
        screen.fill(BLACK)
        draw_outer_border()
        draw_image_box()
        draw_chatlog()
        draw_input_box()
        visualizer.draw_visualizer(
            screen,
            visualizer_area.x,
            visualizer_area.y,
            visualizer_area.width,
            visualizer_area.height
        )
        pygame.display.flip()
        pygame.time.delay(16)

    # Final full frame flush
    screen.fill(BLACK)
    draw_outer_border()
    draw_image_box()
    draw_chatlog()
    draw_input_box()
    visualizer.draw_visualizer(
        screen,
        visualizer_area.x,
        visualizer_area.y,
        visualizer_area.width,
        visualizer_area.height
    )
    pygame.display.flip()
    pygame.time.delay(250)

    startup_lines_shown = True

    # Now that the display is ready, safely import Friday
    global friday
    import importlib
    friday = importlib.import_module("friday")

    if hasattr(friday, "initialize_friday"):
        friday.initialize_friday()

    startup_lines_shown = True

   
def main():
    pygame.key.set_repeat(300, 30)
    global input_text, chatlog, input_focused, friday_connected, last_success_time, startup_first_draw_time, chat_scroll_offset, input_scroll_offset, auto_scroll
    clock = pygame.time.Clock()
    running = True
    draw_startup_lines()

    try:
        while running:
            for ev in pygame.event.get():

                if ev.type == pygame.MOUSEWHEEL:
                    mouse_pos = pygame.mouse.get_pos()
                    if chat_area.collidepoint(mouse_pos):
                        chat_scroll_offset -= ev.y * scroll_speed  # Scroll up = view older messages
                    elif input_box.collidepoint(mouse_pos):
                        input_scroll_offset -= ev.y  # reverse scroll direction

                elif ev.type == pygame.QUIT:
                    running = False

                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    input_focused = input_box.collidepoint(ev.pos)

                elif ev.type == pygame.KEYDOWN and input_focused:
                    mods = pygame.key.get_mods()

                    if ev.key == pygame.K_v and mods & pygame.KMOD_CTRL:
                        try:
                            clip_text = pyperclip.paste()
                            if clip_text:
                                input_text += clip_text
                                input_chars.extend([(char, pygame.time.get_ticks()) for char in clip_text])
                        except Exception as e:
                            print(f"Clipboard paste error: {e}")
                        continue

                    if ev.key == pygame.K_c and mods & pygame.KMOD_CTRL:
                        try:
                            pyperclip.copy(input_text)
                        except Exception as e:
                            print(f"Clipboard copy error: {e}")
                        continue

                    if ev.key == pygame.K_BACKSPACE:
                        input_text = input_text[:-1]
                        if input_chars:
                            input_chars.pop()

                    elif ev.key == pygame.K_RETURN:
                        if input_text.strip():
                            user_msg = input_text
                            chatlog.append(f"You: {user_msg}")
                            input_text = ""
                            input_chars.clear()
                            threading.Thread(target=background_response, args=(user_msg,), daemon=True).start()

                    else:
                        if ev.unicode.isprintable():
                            input_text += ev.unicode
                            input_chars.append((ev.unicode, pygame.time.get_ticks()))

            # Full draw cycle
            screen.fill(BLACK)
            draw_outer_border()
            draw_image_box()

            chat_height = draw_chatlog()
            max_scroll = max(0, chat_height - chat_area.height)
            chat_scroll_offset = max(-max_scroll, min(chat_scroll_offset, 0))

            draw_input_box()

            if friday_connected:
                if pygame.time.get_ticks() - last_success_time > connection_timeout:
                    friday_connected = False

            visualizer.draw_visualizer(
                screen,
                visualizer_area.x,
                visualizer_area.y,
                visualizer_area.width,
                visualizer_area.height
            )

            pygame.display.flip()
            clock.tick(60)

    except Exception as e:
        print(f"[ERROR] An error occurred in main(): {e}")
    finally:
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    main()
