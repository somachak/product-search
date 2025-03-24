#!/usr/bin/env python3
import os
import subprocess
import datetime

def auto_commit():
    # Get current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Change to the project directory
    os.chdir(current_dir)
    
    # Check git status
    status = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
    
    if not status.stdout.strip():
        print("No changes to commit.")
        return
    
    # Add all changes
    subprocess.run(['git', 'add', '.'])
    
    # Create automatic commit message with timestamp
    commit_message = f"Auto commit: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Commit changes
    result = subprocess.run(['git', 'commit', '-m', commit_message], capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"Successfully committed changes with message: '{commit_message}'")
        
        # Push changes
        push_result = subprocess.run(['git', 'push'], capture_output=True, text=True)
        if push_result.returncode == 0:
            print("Successfully pushed changes to remote repository.")
        else:
            print(f"Failed to push changes: {push_result.stderr}")
    else:
        print(f"Failed to commit changes: {result.stderr}")
        
        # Check if there's an issue with Git configuration
        if "Please tell me who you are" in result.stderr:
            print("\nGit configuration issue detected. Setting up default identity...")
            subprocess.run(['git', 'config', '--global', 'user.email', "auto@example.com"])
            subprocess.run(['git', 'config', '--global', 'user.name', "Auto Committer"])
            print("Default identity configured. Trying to commit again...")
            
            # Try committing again
            retry_result = subprocess.run(['git', 'commit', '-m', commit_message], capture_output=True, text=True)
            if retry_result.returncode == 0:
                print(f"Successfully committed changes with message: '{commit_message}'")
            else:
                print(f"Still failed to commit: {retry_result.stderr}")

if __name__ == "__main__":
    auto_commit()