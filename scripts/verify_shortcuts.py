import tkinter as tk
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ui.theme import install_basic_shortcuts

def verify_shortcuts():
    root = tk.Tk()
    root.withdraw()  # Hide window

    print("Installing shortcuts...")
    install_basic_shortcuts(root)

    is_macos = sys.platform == 'darwin'
    mod = 'Command' if is_macos else 'Control'
    
    classes_to_check = ['Entry', 'Text', 'TEntry', 'TCombobox']
    shortcuts = [f'<{mod}-c>', f'<{mod}-v>', f'<{mod}-x>', f'<{mod}-a>']

    all_passed = True
    
    for cls in classes_to_check:
        print(f"\nChecking bindings for class: {cls}")
        for shortcut in shortcuts:
            binding = root.bind_class(cls, shortcut)
            if binding:
                print(f"  [PASS] {shortcut} is bound.")
            else:
                print(f"  [FAIL] {shortcut} is NOT bound!")
                all_passed = False

    if all_passed:
        print("\nSUCCESS: All expected shortcuts are bound to the target classes.")
    else:
        print("\nFAILURE: Some shortcuts are missing.")

    root.destroy()

if __name__ == "__main__":
    verify_shortcuts()
