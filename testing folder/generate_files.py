import os
import re


def create_project_from_text(text_file_path, base_dir="blog-website"):
    """
    Reads a text file containing file paths and code blocks,
    and generates the corresponding directory structure and files.
    """
    try:
        with open(text_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: The file '{text_file_path}' was not found.")
        return

    # Regex to find file paths and their corresponding code blocks
    # It looks for a path-like string followed by a code block in ```...```
    pattern = re.compile(r"####?\s*(.*?)\s*\n```(?:\w*\n)?([\s\S]*?)```")

    matches = pattern.findall(content)

    if not matches:
        print("No file paths and code blocks found in the specified format.")
        print("Please ensure the format is like: '### path/to/file.js' followed by a code block.")
        return

    print(f"Found {len(matches)} files to create. Starting process...")

    # Create the base directory if it doesn't exist
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    for file_path_str, code_content in matches:
        # Clean up the file path
        file_path_str = file_path_str.strip().replace('(', '').replace(')', '')

        # Construct the full path within the base directory
        full_path = os.path.join(base_dir, file_path_str)

        # Get the directory part of the path
        directory = os.path.dirname(full_path)

        try:
            # Create the directory if it doesn't exist
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"Created directory: {directory}")

            # Write the code to the file
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(code_content.strip())

            print(f"Successfully created file: {full_path}")

        except Exception as e:
            print(f"Error creating file {full_path}: {e}")

    print("\nProject generation complete!")


# --- Script Execution ---
if __name__ == "__main__":
    input_file = "full_code.txt"
    create_project_from_text(input_file)

