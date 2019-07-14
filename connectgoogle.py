grom __future__ import print_function

import datetime as dt
import os.path
import pickle
import sys

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from pytz import timezone

from workmanage import DrawShiftImg, Shift, Worker, Worktime

# If modifying these scopes, delete the file token.pickle.
SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_FILENAME = "token.pickle"
CALENDERID = "primary"
TIMEZONE = "Asia/Tokyo"


class ConnectGoogle:
    @staticmethod
    def update_token(token_name):
        creds = None
        if os.path.exists(token_name):
            with open(token_name, "rb") as token:
                creds = pickle.load(token)
                if creds.valid:
                    print("ok, token is valid.")
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "./client_secret.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(token_name, "wb") as token:
                pickle.dump(creds, token)
                print("update or create token.")

    def connect_google(self):

        creds = None

        ConnectGoogle.update_token(TOKEN_FILENAME)

        # 認証トークンがあったらそれを使う
        if os.path.exists(TOKEN_FILENAME):
            with open(TOKEN_FILENAME, "rb") as token:
                creds = pickle.load(token)

        # ないor無効なら中断
        if not creds or not creds.valid:
            print("Error: no or invalid token.", file=sys.stderr)
            print('Please execute "maketoken.py"', file=sys.stderr)
            return None

        service = build("calendar", "v3", credentials=creds)
        return service

    def get_calenderID(self):
        calendar_list = self.service.calendarList().list().execute()
        print("calender name : calender id")
        for calendar_entry in calendar_list["items"]:
            print("{} : {}".format(calendar_entry["summary"], calendar_entry["id"]))

    def __init__(self):
        self.service = self.connect_google()

    def convert_utc_format(self, target: dt.datetime):
        return_value = (
            target.astimezone(timezone("UTC")).isoformat().replace("+00:00", "") + "Z"
        )
        return return_value

    def calc_opening_hours(self, target: dt.datetime, when: str):
        if when == "open":
            return target + dt.timedelta(hours=(8 - target.hour))
        elif when == "close":
            return target + dt.timedelta(hours=(19 - target.hour))
        else:
            print("Error: 'when':{} is wrong value.".format(when), file=sys.stderr)
            return None

    def calc_nearly_monday(self, target: dt.datetime):
        diff_to_monday = dt.timedelta(days=target.weekday())
        nearly_monday = target - diff_to_monday
        return nearly_monday

    def generate_shift_aday(self, events: list):

        day = []
        for worker in events:
            worker_name = str(worker["summary"])
            work_start = dt.datetime.fromisoformat(worker["start"]["dateTime"])
            work_end = dt.datetime.fromisoformat(worker["end"]["dateTime"])
            eventid = worker["id"]
            worker_index = Shift.has_worker(worker_name, day)
            if worker_index is not None:
                day[worker_index].append_worktime(
                    Worktime(work_start, work_end, eventid=eventid)
                )
            else:
                new_worker_obj = Worker(
                    worker_name, [Worktime(work_start, work_end, eventid=eventid)]
                )
                day.append(new_worker_obj)

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
        after_close = self.convert_utc_format(self.calc_opening_hours(date, "close"))

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
        self.service.events().delete(calendarId=CALENDERID, eventId=eventid).execute()

    def insert_schedule(self, name: str, start: dt.datetime, end: dt.datetime):
        start = start.astimezone(timezone(TIMEZONE)).isoformat()
        end = end.astimezone(timezone(TIMEZONE)).isoformat()
        event = {
            "summary": name,
            "end": {"dateTime": end, "timeZone": TIMEZONE},
            "start": {"dateTime": start, "timeZone": TIMEZONE},
        }
        event = (
            self.service.events().insert(calendarId=CALENDERID, body=event).execute()
        )
        return self.generate_shift_aday([event])

    def update_schedule(
        self, eventid: str, summary: str, start: dt.datetime, end: dt.datetime
    ):
        start = start.astimezone(timezone(TIMEZONE)).isoformat()
        end = end.astimezone(timezone(TIMEZONE)).isoformat()
        event = (
            self.service.events().get(calendarId=CALENDERID, eventId=eventid).execute()
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
            shift_dict.update(aday)
        return shift_dict


if __name__ == "__main__":
    date = dt.datetime.now()
    date = date - dt.timedelta(days=0)
    connect = ConnectGoogle()
    start = date + dt.timedelta(days=-1)
    end = date + dt.timedelta(days=-1, hours=1)
    shift_id = (
        connect.get_day_shift(date - dt.timedelta(days=1))["tue"][0].worktime[0].eventid
    )
    print(connect.update_schedule(shift_id, start, end))
    shift = connect.get_week_shift(dt.datetime.now())
    shift = Shift.parse_dict(shift)

    make = DrawShiftImg(
        shift,
        "/Users/yume_yu/Library/Fonts/Cica-Regular.ttf",
        "/Users/yume_yu/Library/Fonts/Cica-Bold.ttf",
        "/Library/Fonts/Arial.ttf",
    )
    image = make.makeImage()
    image.show()
