import os
import sys

BLACK = (0, 0, 0)

# Clear the display output file on startup
try:
    open("display_output.txt", "w", encoding="utf-8").close()
except Exception as e:
    print(f"[Startup Cleanup Error] {e}")
    
chatlog = []
_last_known_lines = 0



def update_chatlog_from_file(filename="display_output.txt"):
    global _last_known_lines
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if len(lines) > _last_known_lines:
                new_entries = lines[_last_known_lines:]
                for entry in new_entries:
                    clean = entry.strip()
                    if clean:
                        chatlog.append(clean)
                _last_known_lines = len(lines)
    except Exception as e:
        print(f"[Chat Display Error] {e}")
        
# Accept X and Y from command-line args
if len(sys.argv) >= 3:
    x = sys.argv[1]
    y = sys.argv[2]
    os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x},{y}"
import pygame

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

def preprocess_lines(chatlog, font, width):
    lines = []
    for msg in chatlog:
        color = (0, 160, 255) if msg.startswith("You:") else (255, 0, 0)
        wrapped = wrap_text(msg, font, width - 2)
        lines.extend([(line, color) for line in wrapped])
    return lines
    
def draw_chatlog(screen, rect, chatlog=None, font=None, scroll_offset=0):
    update_chatlog_from_file()

    if font is None:
        return 0, scroll_offset

    padding = 10
    y = rect.y + scroll_offset
    line_spacing = font.get_height() + 6

    for entry in chatlog or []:
        color = (255, 0, 0) if entry.startswith("You:") else (0, 160, 255)
        wrapped = wrap_text(entry, font, rect.width - 2 * padding)
        for line in wrapped:
            rendered = font.render(line, True, color)
            screen.blit(rendered, (rect.x + padding, y))
            y += line_spacing

    total_height = y - rect.y
    return total_height, scroll_offset
    
    

def handle_scroll(event, scroll_offset, scroll_speed=20):
    if event.type == pygame.MOUSEWHEEL:
        return scroll_offset + event.y * scroll_speed
    return scroll_offset

def calculate_auto_scroll_offset(total_height, rect_height):
    max_scroll = max(0, total_height - rect_height)
    return -max_scroll
    
if __name__ == "__main__":
    import pygame

    pygame.init()
    screen = pygame.display.set_mode((800, 400))
    clock = pygame.time.Clock()

    font = pygame.font.Font(None, 28)
    chat_box = pygame.Rect(50, 50, 700, 300)

    # Test-only draw (now safe):
    pygame.draw.rect(screen, BLACK, chat_box) 

    chatlog = []
    for i in range(25):
        speaker = "You" if i % 2 == 0 else "Friday"
        chatlog.append(f"{speaker}: This is message {i+1} testing vertical spacing alignment.")

    chat_scroll_offset = 0
    auto_scroll = True

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEWHEEL:
                chat_scroll_offset = handle_scroll(event, chat_scroll_offset)
                auto_scroll = False

        screen.fill((30, 30, 30))
        pygame.draw.rect(screen, (50, 50, 50), chat_box, border_radius=6)
        pygame.draw.rect(screen, (0, 0, 0), chat_box.inflate(-4, -4), border_radius=6)

        total_height, chat_scroll_offset = draw_chatlog(
            screen, chat_box, chatlog, font, chat_scroll_offset
        )

        if auto_scroll:
            chat_scroll_offset = calculate_auto_scroll_offset(total_height, chat_box.height)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit() 