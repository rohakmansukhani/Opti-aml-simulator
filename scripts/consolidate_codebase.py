import os

def consolidate_files(output_file="codebase_dump.py"):
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    files_to_process = []
    
    # Define directories to scan
    scan_dirs = [
        os.path.join(root_dir, "backend"),
        os.path.join(root_dir, "scripts")
    ]
    
    ignore_dirs = ["venv", "__pycache__", ".git", ".idea", ".gemini"]
    
    for scan_dir in scan_dirs:
        for root, dirs, files in os.walk(scan_dir):
            # chunks of dirs to ignore
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                if file.endswith(".py") and not file.startswith("consolidate"):
                    files_to_process.append(os.path.join(root, file))
    
    files_to_process.sort()
    
    with open(os.path.join(root_dir, output_file), "w", encoding="utf-8") as outfile:
        outfile.write(f"# Consolidated Codebase generated on {os.environ.get('USER', 'User')}'s request\n")
        outfile.write("# Contains backend and scripts\n\n")
        
        for file_path in files_to_process:
            try:
                rel_path = os.path.relpath(file_path, root_dir)
                outfile.write(f"\n# {'='*80}\n")
                outfile.write(f"# FILE: {rel_path}\n")
                outfile.write(f"# {'='*80}\n\n")
                
                with open(file_path, "r", encoding="utf-8") as infile:
                    outfile.write(infile.read())
                    outfile.write("\n")
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

    print(f"Consolidated {len(files_to_process)} files into {output_file}")

if __name__ == "__main__":
    consolidate_files()
