from __future__ import print_function

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
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_FILENAME = "token.pickle"


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


def connect_google():

    creds = None

    update_token(TOKEN_FILENAME)

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


def convert_utc_format(target: dt.datetime):
    return_value = (
        target.astimezone(timezone("UTC")).isoformat().replace("+00:00", "") + "Z"
    )
    return return_value


def calc_opening_hours(target: dt.datetime, when: str):
    if when == "open":
        return target + dt.timedelta(hours=(8 - target.hour))
    elif when == "close":
        return target + dt.timedelta(hours=(19 - target.hour))
    else:
        print("Error: 'when':{} is wrong value.".format(when), file=sys.stderr)
        return None


def calc_nearly_monday(target: dt.datetime):
    diff_to_monday = dt.timedelta(days=target.weekday())
    nearly_monday = target - diff_to_monday
    return nearly_monday


def generate_shift_aday(events: list):
    first_item = events[0]["start"]["dateTime"]
    first_item_date = dt.datetime.fromisoformat(first_item)
    weekday = Shift.WORKDAYS[first_item_date.weekday()]

    day = {weekday: []}
    for worker in events:
        worker_name = worker["summary"]
        work_start = dt.datetime.fromisoformat(worker["start"]["dateTime"])
        work_end = dt.datetime.fromisoformat(worker["end"]["dateTime"])
        new_worker_obj = Worker(worker_name, [Worktime(work_start, work_end)])
        day[weekday].append(new_worker_obj)
    return day


def get_day_schedule(date: dt.datetime = None):

    service = connect_google()

    if service is None:
        return None

    if not date:
        date = dt.datetime.now()
    elif isinstance(date, dt.datetime):
        # now = date
        pass

    before_open = convert_utc_format(calc_opening_hours(date, "open"))
    after_close = convert_utc_format(calc_opening_hours(date, "close"))

    events_result = (
        service.events()
        .list(
            calendarId="primary",
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


def get_day_shift(date: dt.datetime = None):

    if not date:
        date = dt.datetime.now()
    elif isinstance(date, dt.datetime):
        # now = date
        pass

    events = get_day_schedule(date)
    shit_aday = generate_shift_aday(events)
    return shit_aday


def get_week_shift(date: dt.datetime = None):

    if not date:
        date = dt.datetime.now()
    elif isinstance(date, dt.datetime):
        # now = date
        pass
    shift_dict = {}
    nearly_monday = calc_nearly_monday(date)
    for count in range(5):
        aday = get_day_shift(nearly_monday + dt.timedelta(days=count))
        shift_dict.update(aday)
    return shift_dict


if __name__ == "__main__":
    date = dt.datetime.now()
    date = date - dt.timedelta(days=0)
    # shift = get_day_schedule(date)
    shift = get_week_shift(dt.datetime.now())
    shift = Shift(shift["mon"], shift["mon"], shift["mon"], shift["mon"], shift["mon"])

    make = DrawShiftImg(
        shift,
        "/Users/yume_yu/Library/Fonts/Cica-Regular.ttf",
        "/Users/yume_yu/Library/Fonts/Cica-Bold.ttf",
        "/Library/Fonts/Arial.ttf",
    )
    image = make.makeImage()
    image.show()
