
import os

def consolidate_directory(root_dir, target_dir, output_file):
    """
    Consolidates all code from a specific directory into a single text file.
    """
    # Directories and files to exclude
    exclude_dirs = {
        "node_modules", ".next", "dist", "build", "venv", "__pycache__", 
        ".git", ".idea", ".vscode", "coverage", "tmp", "migrations"
    }
    exclude_files = {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml", 
        ".DS_Store", "codebase_dump.txt", "consolidate_codebase.py",
        "backend_codebase_dump.txt", "frontend_codebase_dump.txt"
    }
    
    # Allowed extensions (to avoid binary files)
    allowed_extensions = {
        ".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".html", ".json", ".md", ".sql", ".env"
    }

    print(f"Processing directory: {target_dir}")
    print(f"Output target: {output_file}")

    full_path = os.path.join(root_dir, target_dir)
    if not os.path.exists(full_path):
        print(f"Error: Directory not found: {full_path}")
        return

    try:
        with open(output_file, "w", encoding="utf-8") as outfile:
            outfile.write(f"# Codebase Dump: {target_dir}\n")
            outfile.write(f"# Generated from: {full_path}\n\n")

            for root, dirs, files in os.walk(full_path):
                # Filter directories in-place
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                
                for file in files:
                    if file in exclude_files:
                        continue
                        
                    _, ext = os.path.splitext(file)
                    if ext.lower() not in allowed_extensions:
                        continue

                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, root_dir)
                    
                    try:
                        with open(file_path, "r", encoding="utf-8") as infile:
                            content = infile.read()
                            
                        outfile.write(f"\n{'='*80}\n")
                        outfile.write(f"FILE: {rel_path}\n")
                        outfile.write(f"{'='*80}\n\n")
                        outfile.write(content)
                        outfile.write("\n")
                        
                        # print(f"Added: {rel_path}")
                        
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
                        outfile.write(f"\n[ERROR READING FILE: {rel_path}]\n")
        
        print(f"Success! Saved to {output_file}")
        
    except Exception as e:
        print(f"Failed to write output file: {e}")

if __name__ == "__main__":
    # Root directory is two levels up from scripts/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(script_dir, ".."))
    
    # 1. Generate Backend Dump
    backend_out = os.path.join(script_dir, "backend_codebase_dump.txt")
    consolidate_directory(root_dir, "backend", backend_out)
    
    # 2. Generate Frontend Dump
    frontend_out = os.path.join(script_dir, "frontend_codebase_dump.txt")
    consolidate_directory(root_dir, "frontend", frontend_out)
