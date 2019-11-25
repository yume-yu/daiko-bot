from __future__ import print_function

import datetime as dt
import json
import os
import re
import socket
import sys
from pprint import pprint

import googleapiclient.errors as g_errors
from apiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pytz import timezone

from workmanage import DrawShiftImg, Shift, Worker, Worktime

socket.setdefaulttimeout(30)
CLIENT_SECRET_JSON = json.loads(os.environ["CLIENT_SECRET_JSON"])["installed"]
REFRESH_TOKEN = os.environ["REFRESH_TOKEN"]
CLIENT_ID = CLIENT_SECRET_JSON["client_id"]
CLIENT_SECRET = CLIENT_SECRET_JSON["client_secret"]
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]
TOKEN_URI = os.environ["TOKEN_URI"]
CALENDERID = "primary"
try:
    CALENDERID = os.environ["CALENDERID"]
except KeyError:
    pass
TIMEZONE = "Asia/Tokyo"
SPREADSHEETID = "1iung0Vi3DNKOlb_IIV2oYya_0YjUsZaP2oBkjKekvbI"
BEFORE_OPEN_TIME = 8
AFTER_CLOSE_TIME = 19


class ConnectGoogle:
    def update_token(self):
        if not self.creds or not self.creds.valid:
            self.creds = Credentials(
                None,
                refresh_token=REFRESH_TOKEN,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                scopes=SCOPES,
                token_uri=TOKEN_URI,
            )
        self.creds.refresh(Request())
        print("update or create token.")
        return self.creds

    def connect_google(self):
        self.creds = self.update_token()
        # ないor無効なら中断
        if not self.creds or not self.creds.valid:
            print("Error: no or invalid token.", file=sys.stderr)
            return None

        # service = build("calendar", "v3", credentials=creds)
        service = self.GoogleServices(self.creds)
        return service

    def __init__(self):
        self.creds = None
        self.service = self.connect_google()

    class GoogleServices:
        """
        認証情報を一括で持つためのクラス
        """

        def __init__(self, creds):
            """
            :param google.oauth2.credentials.Credentials creds : GoogleAPIの認証情報
            """
            self.calendar = build("calendar", "v3", credentials=creds)
            self.sheet = build("sheets", "v4", credentials=creds)
            self.drive = build("drive", "v3", credentials=creds)

    class GoogleCalendar:
        def __init__(self, service):
            self.service = service

        def get_calenderID(self):
            calendar_list = self.service.calendarList().list().execute()
            # print("calender name : calender id")
            calid_list = {}
            for calendar_entry in calendar_list["items"]:
                calid_list.update({calendar_entry["summary"]: calendar_entry["id"]})
                #  print("{} : {}".format(calendar_entry["summary"], calendar_entry["id"]))
                pass
            return calid_list

        def convert_utc_format(self, target: dt.datetime):
            return_value = (
                target.astimezone(timezone("UTC")).isoformat().replace("+00:00", "")
                + "Z"
            )
            return return_value

        def calc_opening_hours(self, target: dt.datetime, when: str):
            if when == "open":
                return target + dt.timedelta(hours=(BEFORE_OPEN_TIME - target.hour))
            elif when == "close":
                return target + dt.timedelta(hours=(AFTER_CLOSE_TIME - target.hour))
            else:
                print("Error: 'when':{} is wrong value.".format(when), file=sys.stderr)
                return None

        def calc_nearly_monday(self, target: dt.datetime):
            diff_to_monday = dt.timedelta(days=target.weekday())
            nearly_monday = target - diff_to_monday
            return nearly_monday

        def convert_event_to_worker(self, event) -> Worker:
            if not event:
                return None

            worker_name: str = ""
            requested = False
            if re.search(r"-代行", str(event["summary"])):
                worker_name = re.sub(r"-代行", "", str(event["summary"]))
                requested = True
            else:
                worker_name = str(event["summary"])
            work_start = dt.datetime.fromisoformat(event["start"]["dateTime"])
            work_end = dt.datetime.fromisoformat(event["end"]["dateTime"])
            eventid = event["id"]
            new_worker = Worker(
                worker_name,
                [Worktime(work_start, work_end, eventid=eventid, requested=requested)],
            )
            return new_worker

        def generate_shift_aday(self, events: list):
            """
            error handling
            """
            if not events:
                return None

            day = []
            for event in events:
                new_worker = self.convert_event_to_worker(event)
                worker_index = Shift.has_worker(new_worker.name, day)
                if worker_index is not None:
                    day[worker_index].append_worktime(new_worker.worktime[0])
                else:
                    day.append(new_worker)

            weekday = Shift.WORKDAYS[day[0].worktime[0].start.weekday()]
            day = {weekday: day}
            return day

        def get_day_schedule(self, date: dt.datetime = None):

            if self.service is None:
                return None

            if not date:
                date = dt.datetime.now()
            elif isinstance(date, dt.datetime):
                # now = date
                pass

            before_open = self.convert_utc_format(self.calc_opening_hours(date, "open"))
            after_close = self.convert_utc_format(
                self.calc_opening_hours(date, "close")
            )

            events_result = (
                self.service.events()
                .list(
                    calendarId=CALENDERID,
                    timeMin=before_open,
                    timeMax=after_close,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])

            if not events:
                print("No upcoming events found.")
                return None
            else:
                return events

        def delete_schedule(self, eventid):
            self.service.events().delete(
                calendarId=CALENDERID, eventId=eventid
            ).execute()

        def insert_schedule(self, name: str, start: dt.datetime, end: dt.datetime):
            start = start.astimezone(timezone(TIMEZONE)).isoformat()
            end = end.astimezone(timezone(TIMEZONE)).isoformat()
            event = {
                "summary": name,
                "end": {"dateTime": end, "timeZone": TIMEZONE},
                "start": {"dateTime": start, "timeZone": TIMEZONE},
            }
            event = (
                self.service.events()
                .insert(calendarId=CALENDERID, body=event)
                .execute()
            )
            return self.generate_shift_aday([event])

        def update_schedule(
            self, eventid: str, summary: str, start: dt.datetime, end: dt.datetime
        ):
            start = start.astimezone(timezone(TIMEZONE)).isoformat()
            end = end.astimezone(timezone(TIMEZONE)).isoformat()
            event = (
                self.service.events()
                .get(calendarId=CALENDERID, eventId=eventid)
                .execute()
            )
            event["summary"] = summary
            event["start"]["dateTime"] = start
            event["end"]["dateTime"] = end
            updated_event = (
                self.service.events()
                .update(calendarId=CALENDERID, eventId=eventid, body=event)
                .execute()
            )
            return updated_event

        def get_schedule(self, eventid: str):
            try:
                target_schedule = (
                    self.service.events()
                    .get(calendarId=CALENDERID, eventId=eventid)
                    .execute()
                )
            except g_errors.HttpError:
                target_schedule = None
            return target_schedule

        def get_day_shift(self, date: dt.datetime = None):

            if not date:
                date = dt.datetime.now()
            elif isinstance(date, dt.datetime):
                # now = date
                pass

            events = self.get_day_schedule(date)
            shit_aday = self.generate_shift_aday(events)
            return shit_aday

        def get_week_shift(self, date: dt.datetime = None):

            if not date:
                date = dt.datetime.now().astimezone(timezone(TIMEZONE))
            elif isinstance(date, dt.datetime):
                # now = date
                pass
            shift_dict = {}
            nearly_monday = self.calc_nearly_monday(date)
            for count in range(5):
                aday = self.get_day_shift(nearly_monday + dt.timedelta(days=count))
                if aday is not None:
                    shift_dict.update(aday)
                else:
                    shift_dict.update(
                        {
                            Shift.WORKDAYS[count]: [
                                Worker(
                                    name="該当なし",
                                    times=[
                                        Worktime(
                                            start="09:00", end="19:00", requested=True
                                        )
                                    ],
                                )
                            ]
                        }
                    )
            return shift_dict

    class GoogleSpreadSheet:
        LOG_SHEET_NAME = "use-logs"
        USERID_SHEET_NAME = "name-id"

        def __init__(self, service):
            self.service = service

        def get_sheets_dict(self, toId=True):
            """
            make dict of sheetName ↔ sheetId

            :param bool toId : if toId is True, key of return dict is "sheetName"
            :return dict : sheetName ↔ sheetId
            """
            response = (
                self.service.spreadsheets().get(spreadsheetId=SPREADSHEETID).execute()
            )
            sheets = {}
            for prop in response.get("sheets"):
                if toId:
                    sheets.update(
                        {
                            prop.get("properties")
                            .get("title"): prop.get("properties")
                            .get("sheetId")
                        }
                    )
                else:
                    sheets.update(
                        {
                            prop.get("properties")
                            .get("sheetId"): prop.get("properties")
                            .get("title")
                        }
                    )
            return sheets

        def get(self, sheetName: str):
            """
            get data from spreadsheet of SPREADSHEETID.

            :param str sheetName : name of target sheet.
            :return list : list of data in sheet.
            """
            sheetId = self.get_sheets_dict()[sheetName]
            request_doby = {
                "dataFilters": [
                    {
                        "gridRange": {
                            "startColumnIndex": 0,
                            "startRowIndex": 1,
                            "sheetId": sheetId,
                        }
                    }
                ],
                "majorDimension": "COLUMNS",
            }
            request = (
                self.service.spreadsheets()
                .values()
                .batchGetByDataFilter(spreadsheetId=SPREADSHEETID, body=request_doby)
            )

            response = request.execute()
            return response.get("valueRanges")[0].get("valueRange").get("values")

        def append(self, data: list, sheetName: str) -> object:
            """
            append data to sheet
            :param list data : to append data.
            :param str sheetName : name of target sheet.
            """
            body = {"values": [data]}
            response = (
                self.service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=SPREADSHEETID,
                    range=sheetName,
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body=body,
                )
                .execute()
            )
            return response

        def update(self, data: list, sheetName: str, date_range: str) -> object:
            """
            update data on sheet
            :param list data : to append data.
            :param str sheetName : name of target sheet.
            """
            body = {"values": [data]}
            response = (
                self.service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=SPREADSHEETID,
                    valueInputOption="USER_ENTERED",
                    range="{}!{}".format(sheetName, date_range),
                    body=body,
                )
                .execute()
            )
            return response

        def get_slackId2name_dict(self, toName=True) -> dict:
            """
            make dict of slack_id ↔ display name

            :param bool toName : if toId is True, key of return dict is "slackId"
            :return dict : slackId ↔ name
            """
            values_list = self.get(self.USERID_SHEET_NAME)
            id2name_dict = None
            if toName:
                id2name_dict = dict(zip(values_list[0], values_list[1]))
            else:
                id2name_dict = dict(zip(values_list[1], values_list[0]))

            return id2name_dict

    class GoogleDrive:
        JPEGIMAGE = "image/jpeg"
        # URLHEADER = "https://drive.google.com/file/d/{}"
        URLHEADER = "https://drive.google.com/uc?id={}"

        def __init__(self, service):
            self.service = service

        def upload(self, filename: str, filepath: str, filetype: str) -> str:
            """
            upload to GoogleDrive

            :param str filename
            :param str filepath
            :param str filetytpe : mimetype of target file
            :return str fileid : fileid for GoogleDrive
            """
            file_metadata = {
                "name": filename,
                "mimetype": filetype,
                "parents": ["1WM6yJVBgoqU9azui7d_EhGuFp5KDIjAN"],
            }
            media_body = MediaFileUpload(filepath, mimetype=filetype)
            file = (
                self.service.files()
                .create(body=file_metadata, media_body=media_body, fields="id")
                .execute()
            )
            return file.get("id")

        def share(self, fileid: str) -> dict:
            """
            share target file on google drive

            :param str fileid : fileid for GoogleDrive
            :return dict changed_permission : created Permission
            """
            ONLY_KNOWN_URL_PERMISSION = {"role": "reader", "type": "anyone"}
            changed_permission = (
                self.service.permissions()
                .create(fileId=fileid, body=ONLY_KNOWN_URL_PERMISSION)
                .execute()
            )
            return changed_permission

        def upload4share(self, filename: str, filepath: str, filetype: str) -> dict:
            fileid = self.upload(filename, filepath, filetype)
            new_permission = self.share(fileid)
            return self.URLHEADER.format(fileid)


if __name__ == "__main__":
    connect = ConnectGoogle()
    calendar = connect.GoogleCalendar(connect.service.calendar)
    # spreadsheet = connect.GoogleSpreadSheet(connect.service.sheet)
    # drive = connect.GoogleDrive(connect.service.drive)
    # print(drive.upload4share("sample.jpg", "./sample.jpg", drive.JPEGIMAGE))
    # pprint(spreadsheet.append(["a", "b"], spreadsheet.LOG_SHEET_NAME))
    ddd = calendar.get_week_shift(dt.datetime.strptime("2019-10-07", "%Y-%m-%d"))
    pprint(Shift.parse_dict(ddd))
