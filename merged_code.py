import os

# שם הקובץ שייווצר
output_filename = "full_project_code.txt"

# איזה סוגי קבצים לאסוף
target_extensions = ('.py')

with open(output_filename, 'w', encoding='utf-8') as outfile:
    # os.walk עובר על כל תיקיות המשנה באופן אוטומטי
    for root, dirs, files in os.walk('.'):
        for file in files:
            # מתעלם מהסקריפט עצמו כדי לא ליצור לולאה אינסופית
            if file.endswith(target_extensions) and file != "merge_code.py":
                file_path = os.path.join(root, file)

                outfile.write(f"\n\n{'=' * 60}\n")
                outfile.write(f"--- נתיב הקובץ: {file_path} ---\n")
                outfile.write(f"{'=' * 60}\n\n")

                try:
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f"שגיאה בקריאת הקובץ: {e}")

print(f"הסתיים! כל הקוד נאסף לקובץ: {output_filename}")