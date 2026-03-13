import os, re, sys
import email as email_lib
import email.utils
from email import policy as email_policy
from datetime import datetime
from pathlib import Path

import extract_msg

import pandas as pd


def getfiles(folder_path):
    folder = Path(folder_path)

    msg_files = list(folder.rglob("*.msg"))
    eml_files = list(folder.rglob("*.eml"))
    file_list = msg_files + eml_files

    print(f"Found {len(file_list)} email files ({len(msg_files)} .msg, {len(eml_files)} .eml) in {folder_path} and its subdirectories")
    return file_list


class Email:
    def __init__(self, filepath):
        filepath = Path(filepath)

        if filepath.suffix.lower() == '.eml':
            with open(filepath, 'rb') as f:
                msg = email_lib.message_from_bytes(f.read(), policy=email_policy.default)

            date_str = msg['Date']
            if date_str:
                self.date = email.utils.parsedate_to_datetime(date_str)
            else:
                self.date = None

            self.sender    = msg['From']
            self.recipient = msg['To']
            self.cc        = msg['Cc']
            self.subject   = msg['Subject']
            self.category  = []

            # Extract plain-text body (skip attachments)
            body_parts = []
            for part in msg.walk():
                if part.get_content_type() == 'text/plain' and part.get_content_disposition() != 'attachment':
                    body_parts.append(part.get_content())
            self.body = ''.join(body_parts)

            # Extract attachment filenames directly as strings
            self.attachments = []
            for part in msg.walk():
                if part.get_content_disposition() == 'attachment':
                    filename = part.get_filename()
                    if filename:
                        self.attachments.append(filename)

            self._msg  = None   # no close() needed for .eml
            self._is_eml = True

        elif filepath.suffix.lower() == '.msg':
            msg = extract_msg.Message(str(filepath))

            self.date      = msg.date
            self.sender    = msg.sender
            self.recipient = msg.to
            self.cc        = msg.cc
            self.subject   = msg.subject
            self.body      = msg.body
            self.category  = msg.categories if hasattr(msg, 'categories') else []
            self.attachments = msg.attachments

            self._msg    = msg
            self._is_eml = False

        else:
            raise ValueError(f"Unsupported file format: {filepath.suffix}")


def get_attachments(EmailObject):
    if EmailObject._is_eml:
        # Already extracted as strings in __init__
        return EmailObject.attachments
    else:
        attachments = []
        for att in EmailObject.attachments:
            attachment_filename = att.longFilename if hasattr(att, 'longFilename') else att.name
            attachments.append(str(attachment_filename))
        return attachments


def parse_msg(EmailObject):
    keys = ['date', 'sender', 'recipient', 'cc', 'subject', 'body', 'category', 'attachments']
    email_dict = dict.fromkeys(keys)

    if EmailObject.date:
        if isinstance(EmailObject.date, datetime):
            email_dict['date'] = EmailObject.date.strftime('%Y-%m-%d, %H:%M')
        else:
            email_dict['date'] = str(EmailObject.date)[:16]
    else:
        email_dict['date'] = 'No Date'

    email_dict['sender']    = EmailObject.sender
    email_dict['recipient'] = EmailObject.recipient
    email_dict['cc']        = EmailObject.cc
    email_dict['subject']   = EmailObject.subject
    email_dict['category']  = EmailObject.category

    body_text = EmailObject.body if EmailObject.body else ''
    email_dict['body'] = body_text[:32000] if len(body_text) > 32000 else body_text

    email_dict['attachments'] = get_attachments(EmailObject)

    return email_dict


def run(folder_path, output_dir='output'):
    print("Starting...")
    emails = getfiles(folder_path)

    df = pd.DataFrame(columns=['date', 'sender', 'recipient', 'cc', 'subject', 'body', 'category', 'attachments'])

    counter = 1
    total = len(emails)

    for email in emails:
        try:
            current_email = Email(email)
            x = parse_msg(current_email)
            df.loc[len(df)] = x
            if current_email._msg:
                current_email._msg.close()
            print(f'Processing email {counter} of {total}', end="\r")
        except Exception as e:
            keys   = ['date', 'sender', 'recipient', 'cc', 'subject', 'body', 'category', 'attachments']
            values = ['ERROR', 'ERROR', 'ERROR', 'ERROR', f'ERROR: {str(e)}', 'ERROR', 'ERROR', []]
            df.loc[len(df)] = dict(zip(keys, values))
            print(f'ERROR Processing email {counter} of {total}: {str(e)}')
        finally:
            counter += 1

    print("Generating Excel sheet ...")

    df.to_excel(Path(output_dir) / 'results.xlsx')

    print("Done.")


if __name__ == "__main__":
    run(input("Enter the folder path containing the emails: ").strip())
