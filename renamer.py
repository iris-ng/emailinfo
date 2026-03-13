import os
import email
import datetime
from email import policy
from pathlib import Path
import extract_msg  # Library for handling .msg files

def extract_email_metadata(file_path):
    """Extracts the date, time, and subject from an .eml or .msg file."""
    if file_path.suffix.lower() == ".eml":
        with open(file_path, 'rb') as f:
            msg = email.message_from_bytes(f.read(), policy=policy.default)
        email_date = msg['Date']
        subject = msg['Subject'] or "No Subject"

    elif file_path.suffix.lower() == ".msg":
        msg = extract_msg.Message(str(file_path))
        email_date = msg.date
        subject = msg.subject or "No Subject"
        msg.close()
    else:
        raise ValueError("Unsupported file format")

    if not email_date:
        raise ValueError(f"Invalid date value or format in {file_path.name}")

    dt = email.utils.parsedate_to_datetime(email_date) if isinstance(email_date, str) else email_date
    date_str = dt.strftime('%Y.%m.%d')
    time_str = dt.strftime('%H.%M')

    subject = " ".join(subject.split())  # Normalize spaces
    subject = "".join(c for c in subject if c.isalnum() or c in " -_()")  # Keep safe characters

    return date_str, time_str, subject[:100]

def rename_emails(folder_path):
    """Renames all .eml and .msg files in the given folder and all subfolders."""
    folder = Path(folder_path)

    all_files = list(folder.rglob("*.eml")) + list(folder.rglob("*.msg"))

    counter = 1
    total = len(all_files)

    for file_path in all_files:
        try:
            date_str, time_str, subject = extract_email_metadata(file_path)
            new_extension = file_path.suffix.lower()
            new_name = f"{date_str} {time_str} - {subject}{new_extension}"
            new_path = file_path.parent / new_name

            if new_path == file_path:
                counter+=1
                continue  # Already correctly named

            if new_path.exists():
                dup_folder = file_path.parent / "potential duplicate"
                dup_folder.mkdir(exist_ok=True)
                new_path = dup_folder / new_name
                os.rename(file_path, new_path)
                print(f"Duplicate: {file_path.name} -> {file_path.parent / 'potential duplicate' / new_name}")
                counter +=1
            else:
                os.rename(file_path, new_path)
                # print(f"Renamed: {file_path.name} -> {new_name}", end="\r")
                counter+=1
                print(f'Processing email {counter} of {total}', end="\r")

        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")
            counter+=1
