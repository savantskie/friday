import subprocess
import time
import logging
import sys
import os
from pystray import Icon, MenuItem as item, Menu
from PIL import Image
import threading
import socket
import ctypes

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("UnifiedLauncher")

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRIDAY_CORE = os.path.join(BASE_DIR, "friday.pyw")
FRIDAY_DISPLAY = os.path.join(BASE_DIR, "friday_display.pyw")
UPDATE_CHECK_SCRIPT = os.path.join(BASE_DIR, "check_update.py")

# Global process references
core_process = None
display_process = None

# --- Process Management ---
def start_processes():
    global core_process, display_process
    try:
        logger.info("Starting Friday display.")
        display_process = subprocess.Popen(["pythonw", FRIDAY_DISPLAY], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.error(f"Error starting display process: {e}")


def restart_friday(icon=None, item=None):
    logger.info("Restarting Friday display...")

    if display_process:
        display_process.terminate()
        time.sleep(2)

    try:
        logger.info("Starting Friday display again...")
        subprocess.Popen(["pythonw", FRIDAY_DISPLAY], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.error(f"Failed to restart Friday display: {e}")


def restart_with_update(icon=None, item=None):
    logger.info("Checking for updates before restart...")
    try:
        subprocess.run(["python", UPDATE_CHECK_SCRIPT], check=True)
        logger.info("Update script executed successfully.")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Update script failed: {e}")
    restart_friday()


def quit_friday(icon, item):
    stop_processes()
    icon.stop()


def quit_all(icon, item):
    logger.info("Terminating Friday display and tray...")
    stop_processes()
    icon.stop()


def watch_display(icon):
    global display_process
    if display_process is None:
        return
    display_process.wait()
    logger.info("Friday display has exited. (Tray remains active.)")


def setup_tray():
    image_path = os.path.join(BASE_DIR, "friday_icon.ico")
    image = Image.open(image_path)
    menu = Menu(
        item('Restart Display', restart_friday),
        item('Restart Display + Apply Update', restart_with_update),
        item('Shut Down Friday + Tray', quit_all),
        item('Quit Tray Only', quit_friday)
    )
    tray_icon = Icon("Friday", image, "Friday Launcher", menu)

    # Start display and watcher thread
    start_processes()
    threading.Thread(target=watch_display, args=(tray_icon,), daemon=True).start()

    tray_icon.run()

# --- Main Entry Point ---
if __name__ == "__main__":
    try:
        setup_tray()
    except Exception as e:
        print(f"[Launcher Error] {e}")
        import traceback
        traceback.print_exc()