import os, re, sys, openpyxl 

import win32com.client

import pandas as pd

from pathlib import Path

# def check_paths():
#
#     if os.path.isfile('result_unsorted.xlsx') == True or os.path.isfile('result_sorted.xlsx') == True:
#         sys.exit("Output files exist. Delete and try again")
#
#     else:
#         print("Starting ...")


def getfiles():
    folder_path = input("Enter the folder path containing the emails: ").strip()
    folder = Path(folder_path)
    used_names = set()
    grouped = {}                                # sheet_name → list of paths
    path_to_sheet = {}                          # rel_path str → sheet_name (for dedup)

    for file_path in folder.rglob("*.msg"):
        rel = file_path.parent.relative_to(folder)
        rel_str = str(rel)
        if rel_str not in path_to_sheet:
            path_to_sheet[rel_str] = make_sheet_name(rel, used_names)
        sheet_name = path_to_sheet[rel_str]
        grouped.setdefault(sheet_name, []).append(file_path)

    return grouped



def make_sheet_name(rel_path, used_names):
    """
    Build an Excel sheet name (max 31 chars) from a relative folder path.
    Keeps deepest (most specific) parts; abbreviates upward with '…'.
    Appends (2), (3)... on collision.
    """
    if str(rel_path) == ".":
        base = "_root"
    else:
        parts = Path(rel_path).parts
        sep = " > "
        name = parts[-1]                        # start with leaf folder
        for part in reversed(parts[:-1]):       # walk upward
            candidate = part + sep + name
            if len(candidate) <= 31:
                name = candidate
            else:
                name = ("… " + sep + name)[:31] # can't fit more levels
                break
        base = name[:31]

    # Disambiguate collisions
    if base not in used_names:
        used_names.add(base)
        return base
    i = 2
    while True:
        suffix = f" ({i})"
        candidate = base[:31 - len(suffix)] + suffix
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        i += 1

class Email:
    def __init__(self,filepath):
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        msg = outlook.OpenSharedItem(filepath)

        self.date = msg.SentOn
        self.sender = msg.SenderName
        self.recipient = msg.To
        self.cc = msg.CC
        # self.bcc = msg.BCC
        self.subject = msg.subject
        self.body = msg.Body
        self.category = msg.Categories
        self.attachments=msg.Attachments

def get_attachments(EmailObject):
    attachments = []
    for att in EmailObject.attachments:
        # print(len(EmailObject.attachments))
        attachment_filename = att.FileName
        attachments.append(str(attachment_filename))
        # print(attachments)
        #returns list of attachments as a list of strings
    return attachments


def parse_msg(EmailObject):
    keys=['date','sender','recipient','cc','subject','body','category','attachments']
    email_dict = dict.fromkeys(keys)
    date_naive = EmailObject.date.replace(tzinfo=None)
    # date_naive = EmailObject.date.tz_localize(None)
    email_dict['date'] = str(date_naive)[:16]
    email_dict['sender'] = EmailObject.sender
    email_dict['recipient'] = EmailObject.recipient
    email_dict['cc'] = EmailObject.cc
    email_dict['subject'] = EmailObject.subject
    email_dict['category'] = EmailObject.category

    email_dict['attachments'] = get_attachments(EmailObject)

    # if EmailObject.attachments:
    #     email_dict['attachments'] = 1
    # else:
    #     email_dict['attachments'] =0
    # email_dict['body'] = ' '.join(emailtext)

    return email_dict

if __name__ == "__main__":
    print("Starting...")
    grouped_emails = getfiles()

    total = sum(len(v) for v in grouped_emails.values())
    counter = 1

    with pd.ExcelWriter("results.xlsx", engine="openpyxl") as writer:
        for sheet_name, emails in grouped_emails.items():
            df = pd.DataFrame(columns=['date','sender','recipient','cc','subject','category','attachments'])

            for email in emails:
                try:
                    current_email = Email(email)
                except AttributeError:
                    keys = ['date','sender','recipient','cc','subject','body','category','attachments']
                    values = [str(current_email.date), str(current_email.sender),
                              str(current_email.recipient), str(current_email.cc),
                              str(current_email.subject), str(current_email.category),
                              str(current_email.attachments)]
                    df.loc[len(df)] = dict(zip(keys, values))
                    print(f'ERROR Processing email {counter} of {total}')
                else:
                    x = parse_msg(current_email)
                    df.loc[len(df)] = x
                    print(f'Processing email {counter} of {total}', end="\r")
                counter += 1

            # Excel sheet names max 31 chars, no special characters
            safe_name = sheet_name.replace("\\", "_").replace("/", "_")[:31]
            df.to_excel(writer, sheet_name=safe_name, index=False)
            print(f'\nSheet written: {safe_name} ({len(emails)} emails)')

    print("Done.")






# import os
# import email
# import datetime
# from email import policy
# from pathlib import Path
# import extract_msg  # Library for handling .msg files
#
# def extract_email_metadata(file_path):
#     """Extracts the date, time, and subject from an .eml or .msg file."""
#     if file_path.suffix.lower() == ".eml":
#         with open(file_path, 'rb') as f:
#             msg = email.message_from_bytes(f.read(), policy=policy.default)
#         email_date = msg['Date']
#         subject = msg['Subject'] or "No Subject"
#
#     elif file_path.suffix.lower() == ".msg":
#         msg = extract_msg.Message(str(file_path))
#         email_date = msg.date
#         subject = msg.subject or "No Subject"
#         msg.close()
#     else:
#         raise ValueError("Unsupported file format")
#
#     if not email_date:
#         raise ValueError(f"Invalid date value or format in {file_path.name}")
#
#     dt = email.utils.parsedate_to_datetime(email_date) if isinstance(email_date, str) else email_date
#     date_str = dt.strftime('%Y.%m.%d')
#     time_str = dt.strftime('%H.%M')
#
#     subject = " ".join(subject.split())  # Normalize spaces
#     subject = "".join(c for c in subject if c.isalnum() or c in " -_()")  # Keep safe characters
#
#     return date_str, time_str, subject
#
# def rename_emails(folder_path):
#     """Renames all .eml and .msg files in the given folder."""
#     folder = Path(folder_path)
#
#     for file_path in folder.glob("*.eml"):
#         try:
#             date_str, time_str, subject = extract_email_metadata(file_path)
#             new_extension = file_path.suffix.lower()
#             new_name = f"{date_str} {time_str} - {subject}{new_extension}"
#             new_path = folder / new_name
#
#             if new_path != file_path:  # Avoid renaming to the same name
#                 os.rename(file_path, new_path)
#                 print(f"Renamed: {file_path.name} -> {new_name}")
#         except Exception as e:
#             print(f"Error processing {file_path.name}: {e}")
#
#     for file_path in folder.glob("*.msg"):
#         try:
#             date_str, time_str, subject = extract_email_metadata(file_path)
#             new_extension = file_path.suffix.lower()
#             new_name = f"{date_str} {time_str} - {subject}{new_extension}"
#             new_path = folder / new_name
#
#             if new_path != file_path:  # Avoid renaming to the same name
#                 os.rename(file_path, new_path)
#                 print(f"Renamed: {file_path.name} -> {new_name}")
#         except Exception as e:
#             print(f"Error processing {file_path.name}: {e}")
#
# if __name__ == "__main__":
#     folder_path = input("Enter the folder path containing the emails: ").strip()
#     rename_emails(folder_path)
