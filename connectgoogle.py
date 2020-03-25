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

from workmanage import DrawShiftImg, Shift, Work, Worker, Worktime

socket.setdefaulttimeout(10)
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
SPREADSHEETID = "1iung0Vi3DNKOlb_IIV2oYya_0YjUsZaP2oBkjKekvbI"
BEFORE_OPEN_TIME = 8
AFTER_CLOSE_TIME = 19


def gcon_error_out(text):
    print(
        "[{}]-ConnectGoogle {}".format(dt.datetime.now().isoformat(), text),
        file=sys.stderr,
    )


class ConnectGoogle:
    def update_token(self):
        creds = Credentials(
            None,
            refresh_token=REFRESH_TOKEN,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            scopes=SCOPES,
            token_uri=TOKEN_URI,
        )
        creds.refresh(Request())
        return creds

    def __init__(self, timezone: dt.timezone):
        self.timezone = timezone
        self.creds = self.update_token()
        # ないor無効なら中断
        if not self.creds or not self.creds.valid:
            print("Error: no or invalid token.", file=sys.stderr)
            return None

        # service = build("calendar", "v3", credentials=creds)
        self.calendar = self.GoogleCalendar(
            build("calendar", "v3", credentials=self.creds), self.timezone
        )
        self.sheet = self.GoogleSpreadSheet(
            build("sheets", "v4", credentials=self.creds)
        )
        self.drive = self.GoogleDrive(build("drive", "v3", credentials=self.creds))

    class GoogleCalendar:
        def __init__(self, service, timezone: dt.timezone):
            self.service = service
            self.timezone = timezone

        def get_calenderID(self):
            calendar_list = self.service.calendarList().list().execute()
            # print("calender name : calender id")
            calid_list = {}
            for calendar_entry in calendar_list["items"]:
                calid_list.update({calendar_entry["summary"]: calendar_entry["id"]})
                #  print("{} : {}".format(calendar_entry["summary"], calendar_entry["id"]))
                pass
            return calid_list

        def check_freebusy(self, calendar: str, search_range: tuple):
            if self.service is None:
                return None
            body = {
                "timeMin": search_range[0],
                "timeMax": search_range[1],
                "timeZone": "Asia/Tokyo",
                "items": [{"id": calendar}],
            }

            result = self.service.freebusy().query(body=body).execute()
            return result.get("calendars").get(calendar).get("busy")

        def delete_event(self, calendar: str, eventid):
            self.service.events().delete(calendarId=calendar, eventId=eventid).execute()

        def insert_event(
            self,
            calendar: str,
            summary: str,
            start: dt.datetime,
            end: dt.datetime,
            description: str,
            recurrence: str = None,
        ):
            """

            GoogleCalendarにイベントを追加する

            Args:
                calendar (str): イベントを追加するカレンダーのcalendar id
                summary (str): イベントのタイトルにする文章
                start (datetime.datetime): イベントの開始日時
                end (datetime.datetime): イベントの終了日時
                description (str): イベントの詳細/メモ欄に書き込む文章
                recurrence (str): イベントの繰り返し設定 RFC5545に準拠したフォーマットの文字列

            Returns:
                dict : APIから返答された、作製したイベントの情報

            Examples:

            Note:
                timeout検出時は再帰的に自身を呼び出しリトライする
            """
            tzname = start.astimezone(self.timezone).tzname()
            start = start.astimezone(self.timezone).isoformat()
            end = end.astimezone(self.timezone).isoformat()
            event = {
                "summary": summary,
                "end": {"dateTime": end, "timeZone": tzname},
                "start": {"dateTime": start, "timeZone": tzname},
                "description": description,
            }

            if recurrence:
                event["recurrence"] = [recurrence]

            try:
                event = (
                    self.service.events()
                    .insert(calendarId=calendar, body=event)
                    .execute()
                )
            except socket.timeout as e:
                print(e)
                return self.insert_event(calendar, summary, start, end, description)
            return event

        def update_event(
            self,
            calendar: str,
            eventid: str,
            summary: str,
            start: dt.datetime,
            end: dt.datetime,
            description: str,
        ):
            start = start.astimezone(self.timezone).isoformat()
            end = end.astimezone(self.timezone).isoformat()
            event = (
                self.service.events()
                .get(calendarId=calendar, eventId=eventid)
                .execute()
            )
            event["summary"] = summary
            event["start"]["dateTime"] = start
            event["end"]["dateTime"] = end
            event["description"] = description
            try:
                updated_event = (
                    self.service.events()
                    .update(calendarId=calendar, eventId=eventid, body=event)
                    .execute()
                )
            except socket.timeout as e:
                print(e)
                return self.update_event(
                    calendar, eventid, summary, start, end, description
                )
            return updated_event

        def get_event(self, calendar: str, eventid: str):
            print("call get_event")
            try:
                target_schedule = (
                    self.service.events()
                    .get(calendarId=calendar, eventId=eventid)
                    .execute()
                )
            except g_errors.HttpError as e:
                print(e)
                target_schedule = None
            except socket.timeout as e:
                print(e)
                return self.get_event(calendar, eventid)
            return target_schedule

        def get_events_in_day(self, calendar: str, search_range: tuple) -> list:
            """
            指定された範囲の指定されたGoogleCalendar上のEventを取得してリストで返す。
            :param tuple search_range : イベントを取得する範囲(始点,終点)
            """

            if self.service is None:
                return None
            try:
                events = (
                    self.service.events()
                    .list(
                        calendarId=calendar,
                        timeMin=search_range[0],
                        timeMax=search_range[1],
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                ).get("items", [])
            except socket.timeout as e:
                print(e)
                return self.get_events_in_day(calendar, search_range)

            if not events:
                print("No upcoming events found.")
                return []
            else:
                return events

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
            try:
                response = (
                    self.service.spreadsheets()
                    .get(spreadsheetId=SPREADSHEETID)
                    .execute()
                )
            except socket.timeout:
                return self.get_sheets_dict(toId)
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

            try:
                response = request.execute()
            except socket.timeout:
                gcon_error_out("catch timeout in GoogleSpreadSheet.get(). retry")
                return self.get(sheetName)

            return response.get("valueRanges")[0].get("valueRange").get("values")

        def append(self, data: list, sheetName: str) -> object:
            """
            append data to sheet
            :param list data : to append data.
            :param str sheetName : name of target sheet.
            """
            body = {"values": [data]}
            try:
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
            except socket.timeout:
                gcon_error_out("catch timeout in GoogleSpreadSheet.append(). retry...")
                return self.append(sheetName)

            return response

        def update(self, data: list, sheetName: str, date_range: str) -> object:
            """
            update data on sheet
            :param list data : to append data.
            :param str sheetName : name of target sheet.
            """
            body = {"values": [data]}
            try:
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
            except socket.timeout:
                gcon_error_out("catch timeout in GoogleSpreadSheet.update(). retry...")
                return self.append(sheetName)
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
            try:
                file = (
                    self.service.files()
                    .create(body=file_metadata, media_body=media_body, fields="id")
                    .execute()
                )
            except socket.timeout:
                gcon_error_out("catch timeout in GoogleDrive().upload. retry...")
                return self.upload(
                    filename=filename, filepath=filepath, filetype=filetype
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
    calendar = connect.calendar
