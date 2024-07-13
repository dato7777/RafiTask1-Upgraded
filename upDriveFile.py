from __future__ import print_function
import os
import io
import pickle
import argparse
import inquirer
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Combined SCOPES for both uploading and downloading
SCOPES = ['https://www.googleapis.com/auth/drive']

def authenticate():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret_1064085980762-du2qefanrj9u323s3850pc9scsdgdsm3.apps.googleusercontent.com.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)
    return service

def upload_file(service, file_path, file_name, folder_id=None):
    file_metadata = {'name': file_name}
    if folder_id:
        file_metadata['parents'] = [folder_id]
    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print('Uploaded File ID: %s' % file.get('id'))
    return file.get('id')

def download_file(service, file_id, file_path):
    if os.path.isdir(file_path):
        file_path = os.path.join(file_path, 'downloaded_file')

    try:
        request = service.files().get_media(fileId=file_id)
        with open(file_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    print("Download %d%%." % int(status.progress() * 100))
        
        print(f"Downloaded file saved to: {file_path}")
        
    except Exception as e:
        print(f"Error downloading file: {e}")

def list_files(service, folder_id=None, level=0):
    query = f"'{folder_id}' in parents" if folder_id else None
    results = service.files().list(q=query, pageSize=1000, fields="nextPageToken, files(id, name, mimeType)").execute()
    items = results.get('files', [])

    file_list = []
    if not items:
        print('No files found.')
    else:
        for item in items:
            file_list.append({'name': item['name'], 'id': item['id'], 'mimeType': item['mimeType']})
            print('  ' * level + f"{item['name']} ({item['id']}) - {item['mimeType']}")
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                file_list.extend(list_files(service, folder_id=item['id'], level=level+1))
    return file_list

def list_local_files(directory):
    file_list = []
    for root, dirs, files in os.walk(directory):
        for name in files:
            file_list.append(os.path.join(root, name))
        for name in dirs:
            file_list.append(os.path.join(root, name))
    return file_list

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Google Drive File Operations')
    parser.add_argument('operation', choices=['upload', 'download', 'list'], help='Operation to perform')
    parser.add_argument('--local-path', help='Local file path for upload or download')
    parser.add_argument('--drive-path', help='Google Drive file/folder ID for upload or download')
    parser.add_argument('--file-name', help='File name for upload')
    args = parser.parse_args()

    service = authenticate()
    
    if args.operation == 'upload':
        if not args.local_path:
            print('Local path is required for upload.')
        else:
            print("Listing local files...")
            local_files = list_local_files(args.local_path)
            print("Local files listed. Please select one to upload.")
            choices = [os.path.basename(file) for file in local_files]
            questions = [
                inquirer.List('file',
                              message="Select the file to upload",
                              choices=choices,
                              ),
            ]
            answers = inquirer.prompt(questions)
            selected_file = next((file for file in local_files if os.path.basename(file) == answers['file']), None)
            if selected_file:
                print("Listing Google Drive folders...")
                drive_files = list_files(service, folder_id=args.drive_path)
                drive_folders = [f"{file['name']} ({file['id']})" for file in drive_files if file['mimeType'] == 'application/vnd.google-apps.folder']
                drive_questions = [
                    inquirer.List('folder',
                                  message="Select the Google Drive folder to upload to",
                                  choices=drive_folders,
                                  ),
                ]
                drive_answers = inquirer.prompt(drive_questions)
                selected_folder = next((file for file in drive_files if f"{file['name']} ({file['id']})" == drive_answers['folder']), None)
                if selected_folder:
                    upload_file(service, selected_file, os.path.basename(selected_file), folder_id=selected_folder['id'])
                else:
                    print("No folder selected.")
            else:
                print("No file selected.")
    
    elif args.operation == 'download':
        if not args.local_path:
            print('Local path is required for download.')
        else:
            print("Listing files...")
            file_list = list_files(service, folder_id=args.drive_path)
            print("Files listed. Please select one to download.")
            choices = [f"{file['name']} ({file['id']})" for file in file_list]
            questions = [
                inquirer.List('file',
                              message="Select the file to download",
                              choices=choices,
                              ),
            ]
            answers = inquirer.prompt(questions)
            selected_file = next((file for file in file_list if f"{file['name']} ({file['id']})" == answers['file']), None)
            if selected_file:
                if os.path.isdir(args.local_path):
                    file_path_to_save = os.path.join(args.local_path, selected_file['name'])
                else:
                    file_path_to_save = args.local_path
                print(f"Downloading {selected_file['name']} to {file_path_to_save}")
                download_file(service, selected_file['id'], file_path_to_save)
            else:
                print("No file selected.")
    
    elif args.operation == 'list':
        list_files(service, folder_id=args.drive_path)
