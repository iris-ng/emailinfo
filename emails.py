import argparse
from pathlib import Path
from renamer import rename_emails
from extractdata import run as run_extract
from analyze_relationships import run as run_analyze
from visualise import run as run_visual

OUTPUT_DIR = Path('output')

parser = argparse.ArgumentParser(description="Email processing tool")
parser.add_argument('--rename', '-r', action='store_true', help='Rename email files by date and subject')
parser.add_argument('--data',   '-d', action='store_true', help='Extract email data to Excel')
parser.add_argument('--visual', '-v', action='store_true', help='Generate visual report (requires results.xlsx)')
args = parser.parse_args()

if not args.rename and not args.data and not args.visual:
    parser.print_help()
else:
    OUTPUT_DIR.mkdir(exist_ok=True)
    if args.rename or args.data:
        folder_path = input("Enter the folder path: ").strip()
        if args.rename:
            rename_emails(folder_path)
        if args.data:
            run_extract(folder_path, OUTPUT_DIR)
    if args.visual:
        run_analyze(output_dir=OUTPUT_DIR)
        run_visual(output_dir=OUTPUT_DIR)
