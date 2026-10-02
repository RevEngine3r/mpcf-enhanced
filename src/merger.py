import os
import glob
import settings


def merge_txt_files():
    if not os.path.isdir(settings.OUTPUT_DIR):
        print(f"Directory '{settings.OUTPUT_DIR}' does not exist.")
        return

    txt_files = sorted(glob.glob(os.path.join(settings.OUTPUT_DIR, "*.txt")))

    if not txt_files:
        print(f"No .txt files found in '{settings.OUTPUT_DIR}'.")
        return

    with open(settings.MERGED_FILE, "w", encoding="utf-8") as outfile:
        for filepath in txt_files:
            with open(filepath, "r", encoding="utf-8") as infile:
                outfile.write(infile.read())
                if not infile.read().endswith("\n"):
                    outfile.write("\n")  # optional: separate files by newline

    print(f"Merged {len(txt_files)} file(s) into '{settings.MERGED_FILE}'.")


if __name__ == "__main__":
    merge_txt_files()
