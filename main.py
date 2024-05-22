import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime
import base64
from bs4 import BeautifulSoup
import re
from email.mime.text import MIMEText
import configparser

#Reading information from config file
config = configparser.ConfigParser()
config.read('config.ini')

#Forming mail search date range from billing generation date
    # If current date is less than bill generation date
    # else current date greater than bill generation date
today = datetime.today()

#Getting billing generation date as user input or from config. eg. 2,3..13..etc
input_date = int(config['BILL']['bill_generation_date'])
msg_billmy = datetime(today.year, input_date, 1).strftime('%b%Y')
billing_date = datetime(today.year,today.month,input_date)

if(today < billing_date):
    if(today.month == 1):
        start_date = datetime(today.year-1, 12, input_date).strftime('%Y/%m/%d')
    else:
        start_date = datetime(today.year, today.month-1, input_date).strftime('%Y/%m/%d')
else:
    start_date = datetime(today.year, today.month, input_date).strftime('%Y/%m/%d')

end_date = datetime(today.year, today.month, today.day).strftime('%Y/%m/%d')

#Search criteria
subject_search = config['MAILSEARCH']['subject']
from_search = config['MAILSEARCH']['from']
date_search = f"after:{start_date} before:{end_date}" 
detail_search = from_search + " " + subject_search + " " + date_search

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"]


def main():
    '''

    Create a config as below and save in same code path as "config.ini" and proceed

    [BILL]
    bill_generation_date=2

    [MAILSEARCH]
    subject=subject:Alert : Update on your ABC Bank Credit Card
    from=from:alerts@abcbank.net

    [MAILSEND]
    from=username1@gmail.com
    to=username2@gmail.com

    '''
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("token.json", "w") as token:
                token.write(creds.to_json())
    
    try:
    # Call the Gmail API
        service = build("gmail", "v1", credentials=creds)
        results = service.users().messages().list(userId="me", maxResults=200, q=detail_search, labelIds=['INBOX']).execute()
        messages = results.get('messages')

        #Total spending, spent date, spending at
        total_spending = []
        #spent_date = []
        #spent_at = []

        #message html
        html_message = ""
        html_open = "<html><body>"
        html_close = "</body></html>"
        body_0 = '<table align=\"center\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"600\"><tbody><tr><td align="left" class="td esd-text" style="font-family:Arial; font-size:16px; line-height:22px; color:#000; font-weight: normal; text-align: left" valign="middle">Dear User, <br/><br/><ol>'
        body_1 = ""

        #messages is a list of dictionary
        for msg in messages:
            #Get each message id from msg
            txt = service.users().messages().get(userId="me", id=msg['id']).execute()

            try:
                payload = txt['payload']
                #headers = payload['headers']
                
                #Getting body of the mail
                # Get the data and decode it with base 64 decoder.
                parts = payload.get('parts')[0]
                data = parts['body']['data']
                data = data.replace("-","+").replace("_","/") 
                decoded_data = base64.b64decode(data)

                soup = BeautifulSoup(decoded_data, 'lxml')
                body = soup.body()[0]
                sptext = body.select("table tbody tr td.td.esd-text")

                msg_txt = ""
                for txt in sptext:
                    if txt.text.strip() != "": 
                        msg_txt += txt.text.strip()

                mt = re.match(r'^.*?(?P<card>\d{4}) for Rs (?P<amt>\d+\.\d{2}) at (?P<loc>.*?)on (?P<dt>.+?)\.', msg_txt, flags=re.M)
                
                body_1 += '<li>Spent Rs. {} at {} on {}</li>'.format(mt.group('amt'), mt.group('loc'), mt.group('dt'))
                #print('<ol><li>Spent Rs. {} at {} on {}</li></ol>'.format(mt.group('amt'), mt.group('loc'), mt.group('dt')))

                total_spending.append(mt.group('amt'))
                #spent_at.append(mt.group('loc'))
                #spent_date.append(mt.group('dt'))

            except Exception as error:
                print(error)       

        if len(total_spending) > 0:
            overall_spent = 0.00
            for s in total_spending:
                overall_spent += float(s)
        
        #print(f'You have spent around Rs. {overall_spent} using card. Carefull!')
        body_2 = f'</ol></br>You have spent around Rs. {overall_spent} using card.!</td></tr></tbody></table>'

        #Concat html messages
        html_message = html_open + body_0 + body_1 + body_2 + html_close

        #Calling mail funtion
        send_mail_spend(html_message, msg_billmy, creds)
        
    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f"An error occurred: {error}")


def send_mail_spend(msg, billDate, creds):
    try:
        service = build("gmail", "v1", credentials=creds)
        message = MIMEText(msg, "html")
        message["To"] = config['MAILSEND']['to']
        message["From"] = config['MAILSEND']['from']
        message["Subject"] = "My Spendings for month {}".format(billDate)

        # encoded message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        create_message = {"raw": encoded_message}
        # pylint: disable=E1101
        send_message = (
            service.users()
            .messages()
            .send(userId="me", body=create_message)
            .execute()
        )
    except HttpError as error:
        print(f"An error occurred: {error}")
        send_message = None
    return send_message


if __name__ == "__main__":
  main()