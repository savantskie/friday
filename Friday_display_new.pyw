import pygame
import chat_display
import ripple_test_fixed as visualizer
import subprocess
import friday
import time
import threading
from chat_display import draw_chatlog, chatlog

input_text = ""
input_scroll_offset = 0
input_auto_scroll = True
input_focused = False

# Initialize
pygame.init()

# Holding Backspace
pygame.key.set_repeat(300, 40)

# Screen setup (MUST come before scrap.init)
WIDTH, HEIGHT = 1280, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Friday Mockup Display")
clock = pygame.time.Clock()

# Now it's safe to initialize clipboard
pygame.scrap.init()
pygame.scrap.set_mode(pygame.SCRAP_CLIPBOARD)

# Fonts & Colors
font = pygame.font.Font(None, 28)
BLACK = (0, 0, 0)
DARK_GREY = (30, 30, 30)
SOFT_GREY = (50, 50, 50)
BLUE = (0, 160, 255)
RED = (255, 0, 0)

# Layout boxes
PADDING = 20
TOP_HEIGHT = 320
IMAGE_WIDTH = 475
VISUALIZER_HEIGHT = 80
BOTTOM_HEIGHT = HEIGHT - TOP_HEIGHT - VISUALIZER_HEIGHT - (PADDING * 3)

image_box = pygame.Rect(PADDING, PADDING, IMAGE_WIDTH, TOP_HEIGHT)
chat_box = pygame.Rect(IMAGE_WIDTH + 2 * PADDING + 35, PADDING + 30, WIDTH - IMAGE_WIDTH - 3 * PADDING - 90, TOP_HEIGHT - 60)
chat_bezel = chat_box.inflate(20, 20)  # Outer bezel shape
visualizer_box = pygame.Rect(20, image_box.bottom + 20, 1240, 100)
input_box = pygame.Rect(20, visualizer_box.bottom + 20, WIDTH - 40, 100)

# Chat border frame extended evenly
chat_border_blend = chat_box.inflate(0, 0)  # No extension needed, bezels will be drawn around it explicitly

def draw_chat_area():
    # Outer plastic bezel (wide frame)
    pygame.draw.rect(screen, SOFT_GREY, chat_bezel, border_radius=14)

    # Layered shading to simulate beveled plastic corners
    pygame.draw.rect(screen, (65, 65, 65), chat_bezel.inflate(-4, -4), border_radius=16)
    pygame.draw.rect(screen, (45, 45, 45), chat_bezel.inflate(-8, -8), border_radius=18)
    pygame.draw.rect(screen, (25, 25, 25), chat_bezel.inflate(-12, -12), border_radius=20)

    # Very subtle curved highlight (faux reflective surface)
    highlight = pygame.Surface((chat_bezel.width - 18, chat_bezel.height - 18), pygame.SRCALPHA)
    pygame.draw.rect(highlight, (255, 255, 255, 12), highlight.get_rect(), border_radius=22)
    screen.blit(highlight, (chat_bezel.x + 9, chat_bezel.y + 9))

    # Final black screen inset
    pygame.draw.rect(screen, BLACK, chat_box, border_radius=10)

def draw_input_box(text):
    pygame.draw.rect(screen, SOFT_GREY, input_box, border_radius=6)
    pygame.draw.rect(screen, BLACK, input_box.inflate(-4, -4), border_radius=6)

    padding = 10
    line_spacing = font.get_height() + 2
    max_width = input_box.width - 2 * padding
    cursor_on = input_focused and int(time.time() * 2) % 2 == 0
    full_text = text + ("|" if cursor_on else "")
    lines = chat_display.wrap_text(full_text, font, max_width)

    max_visible_lines = input_box.height // line_spacing
    global input_scroll_offset
    max_offset = max(0, len(lines) - max_visible_lines)

    if input_auto_scroll:
        input_scroll_offset = max(0, len(lines) - max_visible_lines)
    else:
        input_scroll_offset = max(0, min(input_scroll_offset, max_offset))

    visible_lines = lines[input_scroll_offset:input_scroll_offset + max_visible_lines]

    y = input_box.y + padding
    for i, line in enumerate(visible_lines):
        clean_line = line.replace('\x00', '')  # Protect against null chars

    rendered = font.render(clean_line, True, (255, 0, 0))
    screen.blit(rendered, (input_box.x + padding, y))
    y += line_spacing

# Scroll state
chat_scroll_offset = 0
scroll_speed = 20

def wrap_text(text, font, max_width):
    words = text.split(' ')
    lines = []
    current_line = ''

    for word in words:
        # Handle words that are too long for one line
        if font.size(word)[0] > max_width:
            for char in word:
                test_line = current_line + char
                if font.size(test_line)[0] <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = char
            current_line += ' '
        else:
            test_line = current_line + word + ' '
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line.strip())
                current_line = word + ' '

    if current_line:
        lines.append(current_line.strip())

    return lines

auto_scroll = True

# Main loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.MOUSEWHEEL:
            mouse_pos = pygame.mouse.get_pos()
            if chat_box.collidepoint(mouse_pos):
                chat_scroll_offset = chat_display.handle_scroll(event, chat_scroll_offset)
                auto_scroll = False
            elif input_box.collidepoint(mouse_pos):
                if event.y > 0:
                    input_scroll_offset = max(0, input_scroll_offset - 1)
                elif event.y < 0:
                    input_scroll_offset += 1
                input_auto_scroll = False

        elif event.type == pygame.MOUSEBUTTONDOWN:
            input_focused = input_box.collidepoint(event.pos)

        elif event.type == pygame.KEYDOWN and input_focused:
            input_auto_scroll = True
            mods = pygame.key.get_mods()

            # Clipboard paste (Ctrl+V)
            if event.key == pygame.K_v and (mods & pygame.KMOD_CTRL):
                try:
                    pasted = pygame.scrap.get(pygame.SCRAP_TEXT)
                    if pasted and isinstance(pasted, bytes):
                        text = pasted.decode("utf-8", errors="ignore").replace('\r', '')
                        input_text += text
                    else:
                        print("[Clipboard] No valid text data found.")
                except Exception as e:
                    print(f"[Clipboard Paste Error] {e}")

            # Clipboard copy (Ctrl+C)
            elif event.key == pygame.K_c and (mods & pygame.KMOD_CTRL):
                pygame.scrap.put(pygame.SCRAP_TEXT, input_text.encode())

            # Backspace
            elif event.key == pygame.K_BACKSPACE:
                input_text = input_text[:-1]

            # Enter/Return
            elif event.key == pygame.K_RETURN:
                if input_text.strip():
                    safe_text = input_text.replace('\x00', '')  # Remove nulls
                    import threading  # make sure this is at the top of your file

                    threading.Thread(target=friday.ask_friday, args=(safe_text.strip(),), daemon=True).start()  # ✅ Pass to Friday
                    input_text = ""

            # All other printable keys
            elif event.unicode.isprintable():
                input_text += event.unicode

    

    
    
    # === BACKGROUND with chat cutout ===
    screen_rect = screen.get_rect()
    chat_hole_rect = chat_box.inflate(6, 12)  # Reduced width for left/right alignment

    # Top of panel
    pygame.draw.rect(screen, DARK_GREY, pygame.Rect(0, 0, WIDTH, chat_hole_rect.top))

    # Left of panel
    pygame.draw.rect(screen, DARK_GREY, pygame.Rect(0, chat_hole_rect.top, chat_hole_rect.left, chat_hole_rect.height))

    # Right of panel
    pygame.draw.rect(screen, DARK_GREY, pygame.Rect(chat_hole_rect.right, chat_hole_rect.top, WIDTH - chat_hole_rect.right, chat_hole_rect.height))

    # Bottom of panel
    pygame.draw.rect(screen, DARK_GREY, pygame.Rect(0, chat_hole_rect.bottom, WIDTH, HEIGHT - chat_hole_rect.bottom))

    # === IMAGE BOX (top-left)
    pygame.draw.rect(screen, SOFT_GREY, image_box, border_radius=6)
    pygame.draw.rect(screen, BLACK, image_box.inflate(-4, -4), border_radius=6)

    # === CHAT MODULE (renders under the hole)
    draw_chat_area()
    pygame.draw.rect(screen, BLACK, chat_box)
    total_height, chat_scroll_offset = chat_display.draw_chatlog(
        screen, chat_box, chatlog, font, chat_scroll_offset
    )
    if auto_scroll:
        chat_scroll_offset = chat_display.calculate_auto_scroll_offset(total_height, chat_box.height)

    # === VISUALIZER
    pygame.draw.rect(screen, DARK_GREY, visualizer_box, border_radius=6)
    visualizer.draw_visualizer(
        screen,
        visualizer_box.x,
        visualizer_box.y,
        visualizer_box.width,
        visualizer_box.height
    )

    # === INPUT BOX
    draw_input_box(input_text)

    # === FINAL DISPLAY UPDATE
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
