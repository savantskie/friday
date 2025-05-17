import pygame
import numpy as np
import pyaudio
import math

# Constants
GLOW_RED = (255, 60, 60)

# Audio setup
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
NUM_BARS = 80
bar_width = 3
bar_spacing = 2

p = pyaudio.PyAudio()
stream = p.open(format=FORMAT, channels=CHANNELS,
                rate=RATE, input=True,
                frames_per_buffer=CHUNK)

def get_audio_level(audio_data):
    rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
    return min(rms / 32768, 1.0)

def draw_glow_overlay(surface, x, y, width, height, intensity):
    glow_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    min_alpha = 40
    dynamic_alpha = int(intensity * 160)
    alpha = min(180, max(min_alpha, dynamic_alpha))
    glow_color = (255, 0, 0, alpha)
    glow_surface.fill(glow_color)
    surface.blit(glow_surface, (x, y))

def draw_center_bar(surface, x, y, width, height, core_height=6, fade_thickness=8):
    total_height = core_height + 2 * fade_thickness
    blend_surface = pygame.Surface((width, total_height), pygame.SRCALPHA)

    for i in range(total_height):
        dist_from_center = abs(i - total_height // 2)
        if dist_from_center <= core_height // 2:
            color = (255, 60, 60, 255)
        else:
            fade = (dist_from_center - core_height // 2) / fade_thickness
            alpha = int(255 * (1 - fade))
            color = (255, 60, 60, max(0, min(255, alpha)))
        pygame.draw.line(blend_surface, color, (0, i), (width, i))

    surface.blit(blend_surface, (x, y + (height // 2 - total_height // 2)))

def draw_visualizer(surface, x, y, width, height):
    visualizer_width = width * 0.5  # Use 50% of the visualizer area's width
    left_edge = x + (width - visualizer_width) / 2 - 6  # Nudge slightly left
    center_y = y + height // 2

    data = stream.read(CHUNK, exception_on_overflow=False)
    audio_data = np.frombuffer(data, dtype=np.int16)
    level = get_audio_level(audio_data)

    step = max(1, len(audio_data) // NUM_BARS)
    audio_samples = audio_data[::step][:NUM_BARS]
    taper_curve = [math.cos((i - NUM_BARS/2) / (NUM_BARS/2) * (math.pi / 2)) for i in range(NUM_BARS)]

    total_spacing = visualizer_width / NUM_BARS
    for i, sample in enumerate(audio_samples):
        normalized = (sample / 32768)
        taper = taper_curve[i]
        bar_height = int(normalized * taper * (height * 0.45))

        bar_x = left_edge + i * total_spacing
        rect = pygame.Rect(int(bar_x), int(center_y - bar_height), bar_width, int(bar_height * 2))
        pygame.draw.rect(surface, GLOW_RED, rect, border_radius=3)

    draw_glow_overlay(surface, x, y, width, height, level)
    draw_center_bar(surface, x, y, width, height)

# Standalone test
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((800, 300))
    pygame.display.set_caption("Standalone Visualizer Test")
    clock = pygame.time.Clock()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill((0, 0, 0))
        draw_visualizer(screen, 0, 0, 800, 300)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
