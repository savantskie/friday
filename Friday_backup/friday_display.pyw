import pygame
import sys
import os
import time
import random
import numpy as np
import ripple_test_fixed as visualizer
import threading
import pyperclip
import importlib
friday = importlib.import_module("friday")

def send_to_friday(user_input):
    try:
        return friday.ask_friday(user_input)
    except Exception as e:
        return f"[Error: Failed to talk to Friday directly: {e}]"

def background_response(user_msg):
    global friday_connected, last_success_time
    response = send_to_friday(user_msg)
    if response.startswith("[Error:"):
        chatlog.append(f"⚠️ Friday Error: {response.strip()}")
    else:
        friday_connected = True
        last_success_time = pygame.time.get_ticks()
        chatlog.append(f"Friday: {response.strip()}")
        
def background_response(user_msg):
    global friday_connected, last_success_time
    response = send_to_friday(user_msg)
    if response.startswith("[Error:"):
        chatlog.append(f"⚠️ Friday Error: {response.strip()}")
    else:
        friday_connected = True
        last_success_time = pygame.time.get_ticks()
        chatlog.append(f"Friday: {response.strip()}")


        

        
pygame.init()
friday_connected = False
last_success_time = 0
connection_timeout = 10_000  # 10 seconds in milliseconds

MONITOR_WIDTH = 2560
MONITOR_HEIGHT = 1440
VERTICAL_MARGIN = 50
BORDER_THICKNESS = 10
BORDER_RADIUS = 10

WIDTH = MONITOR_WIDTH // 2
HEIGHT = MONITOR_HEIGHT - 2 * VERTICAL_MARGIN

os.environ['SDL_VIDEO_WINDOW_POS'] = f'{MONITOR_WIDTH//2},{VERTICAL_MARGIN}'
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Friday Display Final")

input_text = ""
input_chars = []
chatlog = []
input_focused = False
cursor_position = 0

BLACK = (0, 0, 0)
RED = (255, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
BLUE = (0, 160, 255)

font_indicator = pygame.font.Font(None, 18)
font_small = pygame.font.Font(None, 24)
font_medium = pygame.font.Font(None, 36)

txt = "FRIDAY"
text_surface = font_indicator.render(txt, True, WHITE)
tw, th = text_surface.get_size()
ind_rx = tw // 2 + 2
ind_ry = th // 2 + 2


visualizer_area = pygame.Rect(10, HEIGHT // 3 + 10, WIDTH - 20, HEIGHT // 3 - 20)

chat_box_margin = 10
chat_box_width = WIDTH // 2 - 2 * chat_box_margin
chat_box_height = visualizer_area.top - chat_box_margin * 2

chat_box_x = WIDTH - chat_box_margin - chat_box_width
chat_box_y = chat_box_margin

chat_area = pygame.Rect(
    chat_box_x,
    chat_box_y,
    chat_box_width,
    chat_box_height
)

image_box_margin = 10
image_box_width = WIDTH // 2 - 2 * image_box_margin
image_box_height = visualizer_area.top - image_box_margin * 2

image_box_x = image_box_margin
image_box_y = image_box_margin

IMAGE_BOX = pygame.Rect(
    image_box_x,
    image_box_y,
    image_box_width,
    image_box_height
)

image_surface = pygame.Surface((IMAGE_BOX.width, IMAGE_BOX.height))
image_surface.fill(BLACK)

ind_cx = IMAGE_BOX.left + 10 + ind_rx
ind_cy = IMAGE_BOX.top + 10 + ind_ry

input_box_width = WIDTH - 20 - 2 * BORDER_THICKNESS
input_box_height = HEIGHT // 3 - 20 - 2 * BORDER_THICKNESS
input_box_x = (WIDTH - input_box_width) // 2
input_box_y = HEIGHT - input_box_height - 10

input_box = pygame.Rect(
    input_box_x,
    input_box_y,
    input_box_width,
    input_box_height
)

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
            # Handle words that are too long to fit
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


def draw_image_display():
    pygame.draw.rect(screen, BLACK, IMAGE_BOX)
    screen.blit(image_surface, (IMAGE_BOX.x, IMAGE_BOX.y))
    pygame.draw.rect(screen, RED, IMAGE_BOX, 2, border_radius=8)


def draw_chatlog():
    pygame.draw.rect(screen, BLACK, chat_area)
    padding = 10
    y = chat_area.y + padding
    line_spacing = font_small.get_height() + 2
    max_lines = (chat_area.height - 2 * padding) // line_spacing
    lines_drawn = 0

    # Loop through most recent messages, starting from the end
    for msg in reversed(chatlog):
        user = msg.startswith("You:")
        wrapped_lines = wrap_text(msg, font_small, chat_area.width - 2 * padding)
        for line in reversed(wrapped_lines):
            if lines_drawn >= max_lines:
                return  # stop drawing if we've filled the area
            surf = font_small.render(line, True, BLUE if user else RED)
            screen.blit(surf, (chat_area.x + padding, y + (max_lines - lines_drawn - 1) * line_spacing))
            lines_drawn += 1


def draw_input_box():
    global border_animation_done
    

    # Start fade-in timer once
    if not hasattr(draw_input_box, "start_time"):
        draw_input_box.start_time = pygame.time.get_ticks()

    elapsed = pygame.time.get_ticks() - draw_input_box.start_time
    fade_val = min(255, int((elapsed / 2000) * 255))
    fade_color = (fade_val, 0, 0)

    # Always draw the box background and border
    pygame.draw.rect(screen, BLACK, input_box)
    pygame.draw.rect(screen, RED, input_box, 2, border_radius=8)

    # Only show typed text once the entire boot animation is done
    if border_animation_done:
        padding = 10
        line_spacing = font_medium.get_height() + 2
        max_width = input_box.width - 2 * padding
        max_lines = input_box.height // line_spacing

        lines = wrap_text(input_text, font_medium, max_width)
        visible_lines = lines[-(max_lines - 1):]
        y = input_box.y + padding
        for line in visible_lines:
            rendered = font_medium.render(line, True, fade_color)
            screen.blit(rendered, (input_box.x + padding, y))
            y += line_spacing


def draw_path_segment(surface, points, draw_len, color, thickness):
    length_covered = 0
    for i in range(len(points) - 1):
        start = points[i]
        end = points[i + 1]
        segment_length = ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
        if draw_len > length_covered + segment_length:
            pygame.draw.line(surface, color, start, end, thickness)
            length_covered += segment_length
        else:
            ratio = (draw_len - length_covered) / segment_length
            intermediate = (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio
            )
            pygame.draw.line(surface, color, start, intermediate, thickness)
            break

def draw_animated_borders(progress):
    outer_total = 2 * WIDTH + 2 * HEIGHT
    image_total = 2 * IMAGE_BOX.width + 2 * IMAGE_BOX.height
    chat_total = 2 * chat_area.width + 2 * chat_area.height
    input_total = 2 * input_box.width + 2 * input_box.height

    if progress < outer_total:
        points = [(3, 3), (WIDTH - 3, 3), (WIDTH - 3, HEIGHT - 3), (3, HEIGHT - 3), (3, 3)]
        draw_path_segment(screen, points, progress, RED, BORDER_THICKNESS)
    else:
        pygame.draw.rect(screen, RED, (3, 3, WIDTH - 6, HEIGHT - 6), BORDER_THICKNESS)

    if progress >= outer_total and progress < outer_total + image_total:
        p = progress - outer_total
        ccw_image = [
            IMAGE_BOX.topleft,
            IMAGE_BOX.bottomleft,
            IMAGE_BOX.bottomright,
            IMAGE_BOX.topright,
            IMAGE_BOX.topleft
        ]
        draw_path_segment(screen, ccw_image, p, RED, 2)
    elif progress >= outer_total + image_total:
        pygame.draw.rect(screen, RED, IMAGE_BOX, 2, border_radius=8)

    if progress >= outer_total + image_total and progress < outer_total + image_total + chat_total:
        p = progress - outer_total - image_total
        ccw_chat = [
            chat_area.topleft,
            chat_area.bottomleft,
            chat_area.bottomright,
            chat_area.topright,
            chat_area.topleft
        ]
        draw_path_segment(screen, ccw_chat, p, RED, 2)
    elif progress >= outer_total + image_total + chat_total:
        pygame.draw.rect(screen, RED, chat_area, 2, border_radius=8)

    if progress >= outer_total + image_total + chat_total and progress < outer_total + image_total + chat_total + input_total:
        p = progress - outer_total - image_total - chat_total
        ccw_input = [
            input_box.topleft,
            input_box.bottomleft,
            input_box.bottomright,
            input_box.topright,
            input_box.topleft
        ]
        draw_path_segment(screen, ccw_input, p, RED, 2)
    elif progress >= outer_total + image_total + chat_total + input_total:
        pygame.draw.rect(screen, RED, input_box, 2, border_radius=8)

def draw_connection_status():
    if friday_connected:
        status_text = "Connected to Friday"
        text_surf = font_small.render(status_text, True, GREEN)
        text_rect = text_surf.get_rect()
        text_rect.bottomleft = (input_box.left, input_box.top - 8)  # just above input box
        screen.blit(text_surf, text_rect)

def main():
    pygame.key.set_repeat(300, 30)

    global input_text, chatlog, input_focused
    global border_animation_done, friday_connected, last_success_time

    border_progress = 0
    outer_total = 2 * WIDTH + 2 * HEIGHT
    image_total = 2 * IMAGE_BOX.width + 2 * IMAGE_BOX.height
    chat_total = 2 * chat_area.width + 2 * chat_area.height
    input_total = 2 * input_box.width + 2 * input_box.height
    visualizer_fold_progress = 0
    fold_done = False
    border_animation_done = False
    fold_duration = 40
    clock = pygame.time.Clock()
    running = True

    try:
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    input_focused = input_box.collidepoint(ev.pos)
                elif ev.type == pygame.KEYDOWN and input_focused:
                    mods = pygame.key.get_mods()

                    # PASTE (Ctrl+V)
                    if ev.key == pygame.K_v and mods & pygame.KMOD_CTRL:
                        try:
                            clip_text = pyperclip.paste()
                            if clip_text:
                                input_text += clip_text
                                input_chars.extend([(char, pygame.time.get_ticks()) for char in clip_text])
                        except Exception as e:
                            print(f"Clipboard paste error: {e}")
                        continue

                    # COPY (Ctrl+C)
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

            screen.fill(BLACK)

            if border_progress >= outer_total + image_total:
                draw_image_display()
            if border_progress >= outer_total + image_total + chat_total:
                draw_chatlog()
            if border_progress >= outer_total + image_total + chat_total + input_total:
                draw_input_box()

            # Auto-clear connection flag if no response from Friday in timeout window
            if friday_connected:
                current_time = pygame.time.get_ticks()
                if current_time - last_success_time > connection_timeout:
                    friday_connected = False

            if border_animation_done:
                draw_connection_status()

            total_border_length = (
                2 * WIDTH + 2 * HEIGHT +
                2 * IMAGE_BOX.width + 2 * IMAGE_BOX.height +
                2 * chat_area.width + 2 * chat_area.height +
                2 * input_box.width + 2 * input_box.height
            )

            if not border_animation_done:
                draw_animated_borders(border_progress)
                border_progress += 40
                if border_progress >= total_border_length:
                    border_animation_done = True
            else:
                pygame.draw.rect(screen, RED, (3, 3, WIDTH - 6, HEIGHT - 6), BORDER_THICKNESS)
                pygame.draw.rect(screen, RED, chat_area, 2, border_radius=8)
                pygame.draw.rect(screen, RED, input_box, 2, border_radius=8)

            if fold_done:
                visualizer.draw_visualizer(
                    screen,
                    visualizer_area.x,
                    visualizer_area.y,
                    visualizer_area.width,
                    visualizer_area.height
                )
            else:
                mid = visualizer_area.centerx
                half_width = int((visualizer_fold_progress / fold_duration) * (visualizer_area.width / 2))
                expanding_rect = pygame.Rect(mid - half_width, visualizer_area.y, half_width * 2, visualizer_area.height)
                pygame.draw.rect(screen, (50, 0, 0), expanding_rect, border_radius=6)
                if visualizer_fold_progress < fold_duration:
                    visualizer_fold_progress += 1
                else:
                    fold_done = True

            pygame.display.flip()
            clock.tick(60)

    except Exception as e:
        print(f"[ERROR] An error occurred in main(): {e}")
    finally:
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    main()