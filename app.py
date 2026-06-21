from helper import (
    authenticate,
    download_attachments,
    convert_to_ebay,
)

def run():
    service = authenticate()
    files = download_attachments(service)

    if not files:
        print("No files to convert.")
        return

    for filepath in files:
        convert_to_ebay(filepath)

run()
