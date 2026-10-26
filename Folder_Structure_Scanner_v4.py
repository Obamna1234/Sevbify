import os
from pathlib import Path

def scan_structure(root_dir, indent=0):
    lines = []
    items = sorted(os.listdir(root_dir))

    for item in items:
        full_path = os.path.join(root_dir, item)
        prefix = "    " * indent

        if os.path.isdir(full_path):
            lines.append(f"{prefix}📁 {item}\n")
            lines.extend(scan_structure(full_path, indent + 1))
        elif os.path.isfile(full_path):  # Only add real files
            lines.append(f"{prefix}└── {item}\n")
        else:
            print("Skipping non-existent:", full_path)  # Debug

    return lines

if __name__ == "__main__":
    root_directory = Path(__file__).parent
    desktop_path = Path.home() / "Desktop" / "sr2_folder_structure_v4.txt"

    structure_lines = scan_structure(root_directory)

    with open(desktop_path, "w", encoding="utf-8") as f:
        f.write(f"=== SR2 Folder Structure V4 ===\n")
        f.write(f"Scanned Root: {root_directory}\n\n")
        f.writelines(structure_lines)

    print("\nDone! Folder structure saved to Desktop as:")
    print(desktop_path)
