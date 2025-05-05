import subprocess
import os
import time
import logging
import threading
from infi.systray import SysTrayIcon

print("Current working directory:", os.getcwd())
print("Display path exists:", os.path.exists("friday_display.pyw"))

# Get the directory where the launcher script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Paths to core & display scripts
FRIDAY_CORE = os.path.join(script_dir, "friday.py")
FRIDAY_DISPLAY = os.path.join(script_dir, "friday_display.pyw")

# Set up centralized logging
LOGFILE = os.path.join(script_dir, "friday.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGFILE),
        logging.StreamHandler()  # Optional: Print logs to the console as well
    ],
)
logger = logging.getLogger("FridayLauncher")

core_process = None
display_process = None

def start_processes():
    global core_process, display_process
    try:
        logger.info("Starting Friday display...")
        display_process = subprocess.Popen(
            ["python", FRIDAY_DISPLAY],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        logger.info("Waiting 8.05 seconds for display animation to complete...")
        time.sleep(10.5)

        logger.info("Starting Friday core...")
        core_process = subprocess.Popen(
            ["python", FRIDAY_CORE],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )

    except Exception as e:
        logger.error(f"Error starting processes: {e}")


def stop_processes():
    global core_process, display_process

    logger.info("Stopping Friday core...")
    if core_process and core_process.poll() is None:
        try:
            logger.info("Sending 'end session' via socket...")
            import socket
            with socket.create_connection(("127.0.0.1", 5050), timeout=3) as s:
                s.sendall(b"end session")
                s.recv(4096)  # wait for response
            core_process.wait(timeout=5)
            logger.info("Friday core exited cleanly.")
        except Exception as e:
            logger.warning(f"Graceful shutdown failed: {e}")
            core_process.terminate()
            core_process.wait()
            logger.info("Friday core forcibly terminated.")
    elif core_process:
        logger.info("Friday core was already stopped.")

    logger.info("Stopping Friday display...")
    if display_process and display_process.poll() is None:
        display_process.terminate()
        display_process.wait()
        logger.info("Friday display terminated.")
    elif display_process:
        logger.info("Friday display was already stopped.")


def on_quit(systray):
    logger.info("Tray quit selected. Shutting down Friday.")
    stop_processes()

    # Workaround to avoid thread join error
    def delayed_shutdown():
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=delayed_shutdown, daemon=True).start()

def main():
    menu_options = ()
    systray = SysTrayIcon("icon.ico", "Friday AI", menu_options, on_quit=on_quit)
    logger.info("Friday launcher started with system tray icon.")
    systray.start()

    start_processes()

if __name__ == "__main__":
    main()
