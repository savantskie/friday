import difflib
import os
from datetime import datetime

# === CONFIGURATION ===
CURRENT_CODE_PATH = "friday.py"
BACKUP_CODE_PATH = "Friday_Backup/friday_backup.py"
INTENDED_CHANGES_LOG = "Friday_Updates/intended_changes.txt"
UPDATE_LOG = "Friday_Updates/update_log.txt"
INTEGRITY_OUTPUT_LOG = "integrity/integrity_log.txt"

def read_file(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as file:
            return file.readlines()
    return []

def compare_files(current_lines, backup_lines):
    diff = list(difflib.unified_diff(backup_lines, current_lines, fromfile='backup', tofile='current'))
    return diff

def log_difference(differences):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(UPDATE_LOG, 'a', encoding='utf-8') as log_file:
        log_file.write(f"\n[{timestamp}] Code Comparison Run:\n")
        if differences:
            for line in differences:
                log_file.write(line)
        else:
            log_file.write("No differences found.\n")
            
def write_integrity_log(differences):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(os.path.dirname(INTEGRITY_OUTPUT_LOG), exist_ok=True)
    with open(INTEGRITY_OUTPUT_LOG, 'a', encoding='utf-8') as log_file:
        log_file.write(f"\n[{timestamp}] Integrity Check:\n")
        if differences:
            for line in differences:
                log_file.write(line)
        else:
            log_file.write("No differences found.\n")


def check_intended_changes():
    if not os.path.exists(INTENDED_CHANGES_LOG):
        return []
    with open(INTENDED_CHANGES_LOG, 'r', encoding='utf-8') as f:
        return f.read().splitlines()

def run_code_check():
    current = read_file(CURRENT_CODE_PATH)
    backup = read_file(BACKUP_CODE_PATH)
    differences = compare_files(current, backup)
    intended = check_intended_changes()

    if not differences:
        print("No changes found.")
        write_integrity_log(differences)
    else:
        print("Differences detected. Logging to update log.")
        log_difference(differences)
        write_integrity_log(differences)

if __name__ == "__main__":
    run_code_check()
