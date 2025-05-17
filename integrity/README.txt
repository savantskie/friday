== INTEGRITY FOLDER OVERVIEW ==

This folder is responsible for Friday’s self-integrity checking and code validation.

--- Files ---

1. code_check.py
   - Compares the current version of friday.py with a backup copy (Friday_Backup/friday_backup.py).
   - Checks for unintended changes by comparing against a developer-authored list (Friday_Updates/intended_changes.txt).
   - Logs all differences to update_log.txt for later review.

--- How it Works ---

- On Friday's startup, she runs a quick code comparison and logs the result.
- Every 3 hours, she performs an automatic recheck using a background thread.
- If unintended changes are found, they are printed and logged.

--- Folder Integration ---

• This script is imported into friday.py and does not need to be run directly.
• Changes to the checker should only be made here, not copied into friday.py.
• Backup and update tracking files are stored in dedicated folders for cleanliness.

--- Related Files ---

- Friday_Backup/friday_backup.py → Baseline reference for comparison.
- Friday_Updates/intended_changes.txt → Known and allowed modifications.
- Friday_Updates/update_log.txt → Auto-generated log of detected differences.

== DO NOT DELETE THIS FILE ==
