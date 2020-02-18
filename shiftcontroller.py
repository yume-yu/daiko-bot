import datetime as dt
import json
import os
import socket
import sys
from enum import Enum, auto
from pprint import pprint

import requests
from connectgoogle import TIMEZONE, ConnectGoogle
from pytz import timezone
from workmanage import DrawShiftImg, Shift, Work, Worker, Worktime

FONT = "./.fonts/mplus-1m-regular.ttf"
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
NOTICE_CHANNEL = os.environ["NOTICE_CHANNEL"]
header = {
    "Content-type": "application/json",
    "Authorization": "Bearer " + SLACK_BOT_TOKEN,
}
CHAT_POSTMESSAGE = "https://slack.com/api/chat.postMessage"
BEFORE_OPEN_TIME = 8
AFTER_CLOSE_TIME = 19
CALENDARID_SHIFT = os.environ["CALENDARID_SHIFT"]
CALENDARID_DAIKO = os.environ["CALENDARID_DAIKO"]
CALENDARID_OPEN = os.environ["CALENDARID_OPEN"]


class ShiftController:
    """
    シフトを操作するためのクラス
    """

    class UseWay(Enum):
        """
        使用方法
        """

        CHAT = "チャット形式"
        BUTTONS = "ボタン等ツール"
        COMM = "コマンド形式"

    class Actions(Enum):
        """
        使用用途
        """

        SHOWSHIFT = "シフト確認"
        REQUEST = "代行依頼"
        CONTRACT = "代行請負"

    class DevPos(Enum):
        """
        シフト変更時の分割位置
        """

        FRONT = auto()
        MATCH = auto()
        BACK = auto()
        INCLUDE = auto()

    def __init__(self):
        self.gcon = ConnectGoogle()
        self.calendar = self.gcon.calendar
        self.drive = self.gcon.drive
        self.sheet = self.gcon.sheet
        self.shift = None

    def post_message(
        self,
        message: str,
        channel: str = NOTICE_CHANNEL,
        ts: str = None,
        attachments: dict = None,
    ):
        post_body = {
            "text": message,
            "channel": channel,
            "token": SLACK_BOT_TOKEN,
            "as_user": False,
        }
        if ts:
            post_body.update({"thread_ts": ts})
        if attachments:
            post_body.update({"attachments": attachments})
        res = requests.post(
            CHAT_POSTMESSAGE, json=json.loads(json.dumps(post_body)), headers=header
        )
        res = json.loads(res.text)
        print(res)
        return res["ok"]

    def slackid2name(self, slackId: str):
        return self.sheet.get_slackId2name_dict()[slackId]

    def convert_utc_format(self, target: dt.datetime):
        return_value = (
            target.astimezone(timezone("UTC")).isoformat().replace("+00:00", "") + "Z"
        )
        return return_value

    def calc_nearly_monday(self, target: dt.datetime):
        """
        指定された日付に対して、月-金ならその週の、日土なら翌週の月曜日の日付を返す
        """
        weekday = target.weekday()
        if weekday < 5:
            # 月曜から金曜のとき
            diff_to_monday = dt.timedelta(days=weekday)
        else:
            # 土日
            diff_to_monday = dt.timedelta(days=-1 * (7 - weekday))
        nearly_monday = target - diff_to_monday
        return nearly_monday

    def calc_opening_hours(self, target: dt.datetime, is_UTC=False) -> tuple:
        """
        指定されたdatetimeから同日の開館時間と閉館時間を返す
        """
        # (open, clone)
        return (
            self.convert_utc_format(
                target + dt.timedelta(hours=(BEFORE_OPEN_TIME - target.hour))
            )
            if is_UTC
            else target + dt.timedelta(hours=(BEFORE_OPEN_TIME - target.hour)),
            self.convert_utc_format(
                target + dt.timedelta(hours=(AFTER_CLOSE_TIME - target.hour))
            )
            if is_UTC
            else target + dt.timedelta(hours=(AFTER_CLOSE_TIME - target.hour)),
        )

    def convert_event_to_work(self, event):
        """
        GoogleCalendar上のEvent、もしくはEventのリストを受け取ってWorkオブジェクト、またはオブジェクトのリストを返す
        """
        if isinstance(event, dict):
            worker_name: str = event.get("summary")
            work_start = dt.datetime.fromisoformat(event["start"]["dateTime"])
            work_end = dt.datetime.fromisoformat(event["end"]["dateTime"])
            requested = (
                True
                if event.get("organizer").get("email") == CALENDARID_DAIKO
                else False
            )
            eventid = event.get("id")
            slack_id = event.get("description")

            return Work(
                staff_name=worker_name,
                start=work_start,
                end=work_end,
                eventid=eventid,
                requested=requested,
                slackid=slack_id,
            )
        elif isinstance(event, list):
            works = []
            for ev in event:
                works.append(self.convert_event_to_work(ev))
            return works
        else:
            return None

    def get_shift(
        self,
        date: dt.datetime = None,
        eventid=None,
        slackid=None,
        only_requested: bool = False,
        only_active: bool = False,
    ):
        """
        指定された条件のWorkのリストを返す

        :param dt.datetime date: シフトを探す週の基準の日付。Noneなら実行された時間
        :param str eventid : シフトのGoogleCalendar上のEventid
        :param str slackid : 絞り込むシフトの担当者
        :param bool only_requested : 代行依頼のみに絞り込む
        :param bool only_active : 実シフトのみに絞り込む
        """

        if eventid is not None:
            # eventidの指定があった場合はその他に依らず一意なのでそのまま返す
            target = self.calendar.get_event(CALENDARID_DAIKO, eventid)
            if target is not None:
                return self.convert_event_to_work(target)

            target = self.calendar.get_event(CALENDARID_SHIFT, eventid)
            if target is not None:
                return self.convert_event_to_work(target)
            return None

        if date is None:
            date = dt.datetime.now()

        opening_range = self.calc_opening_hours(date, is_UTC=True)

        events = []

        if not only_active:
            # 代行依頼のみの指定がなければ有効なシフトを取得し全体にappend
            events += self.calendar.get_events_in_day(CALENDARID_SHIFT, opening_range)

        if not only_requested:
            # 有効なシフトのみの指定がなければ代行依頼を取得し全体にappend
            events += self.calendar.get_events_in_day(CALENDARID_DAIKO, opening_range)

        works = self.convert_event_to_work(events)
        del events
        if slackid is not None:
            return [work for work in works if work.slackid == slackid]
        else:
            return works

    def get_week_shift(
        self,
        base_date: dt.datetime = None,
        slackid=None,
        only_requested: bool = False,
        only_active: bool = False,
        grouping_by_week: bool = False,
    ):
        """
        指定された日を基準として条件にあったその週全体のWorkのリストを返す
        :param dt.datetime date: シフトを探す週の基準の日付。Noneなら実行された時間
        :param str slackid : 絞り込むシフトの担当者
        :param bool only_requested : 代行依頼のみに絞り込む
        :param bool only_active : 実シフトのみに絞り込む
        :param bool grouping_by_week : シフトを週ごとに別のリストにするか
        """

        if not base_date:
            base_date = dt.datetime.now().astimezone(timezone(TIMEZONE))
        elif isinstance(date, dt.datetime):
            # now = date
            pass

        works_list = []
        # もっともらしい月曜日の日付を算出
        nearly_monday = self.calc_nearly_monday(base_date)
        del base_date

        for count in range(5):
            works = self.get_shift(
                date=nearly_monday + dt.timedelta(days=count),
                slackid=slackid,
                only_active=only_active,
                only_requested=only_requested,
            )

            if grouping_by_week:
                works_list.append(works)
            else:
                works_list += works

        return works_list

    def generate_shiftimg_url(self, shift, retry=False, filename: str = None) -> str:
        """
        現在のシフトの画像のurlを返す

        :return str : 画像のurl
        """
        if not retry:
            filename = "{}.jpg".format(dt.datetime.now().strftime("%Y%m%d%H%M%S%f"))
            DrawShiftImg(shift, FONT).make_shiftimage().save(filename, quality=95)
        try:
            image_url = self.drive.upload4share(
                filename, filename, self.drive.JPEGIMAGE
            )
        except socket.timeout as e:
            print(e)
            return {"url": None, "filename": filename}
        os.remove(filename)
        return {"url": image_url, "filename": filename}

    def generate_datefix_work(
        self,
        target: Work,
        start: dt.datetime,
        end: dt.datetime,
        staff_name: str = None,
        requested: bool = None,
        slackid=None,
    ) -> Work:
        """
        指定されたtargetと同じ日付かつ指定された労働時間のworkを作る。作成されたworkのstart,endはtimezoneの情報をもったdt.datetimeObjectです。

        :param work target: 日付を揃える対象のwork
        :param str start: 作成するworktimeの開始時間
        :param str end: 作成するworktimeの終了時間

        :return Work
        """

        return Work(
            staff_name=target.staff_name if staff_name is None else staff_name,
            start=start.astimezone(timezone(TIMEZONE)),
            end=end.astimezone(timezone(TIMEZONE)),
            requested=target.requested if requested is None else requested,
            slackid=target.slackid if slackid is None else slackid,
            eventid=target.eventid,
        )

    def check_need_divide(self, original: Work, request: Work):
        """
        指定された2つのworkの位置関係を示す

        :return DepPos : 位置関係
        """
        if (original.start == request.start) and (original.end == request.end):
            return self.DevPos.MATCH
        elif (original.start == request.start) and (original.end != request.end):
            return self.DevPos.FRONT
        elif (original.start != request.start) and (original.end == request.end):
            return self.DevPos.BACK
        elif (original.start > request.start) or (original.end < request.end):
            raise ValueError("request not include original")
        else:
            return self.DevPos.INCLUDE

    def insert_shift(self, new_work: Work):
        """
        新規シフトをGoogleCalendarに登録する
        """
        # 新規作成分をinsert
        res = self.calendar.insert_event(
            calendar=CALENDARID_DAIKO if new_work.requested else CALENDARID_SHIFT,
            summary=new_work.staff_name,
            start=new_work.start,
            end=new_work.end,
            description=new_work.slackid,
        )
        return res

    def update_shift(self, new_work: Work):
        """
        既存シフトをnew_workの通り更新する
        """
        res = self.calendar.update_event(
            calendar=CALENDARID_DAIKO if new_work.requested else CALENDARID_SHIFT,
            eventid=new_work.eventid,
            summary=new_work.staff_name,
            start=new_work.start,
            end=new_work.end,
            description=new_work.slackid,
        )
        return res

    def apply_changes_shift(self, base_work: Work, new_work: Work, pos: DevPos):
        """
        元シフトと追加シフトを参照して元シフトの情報を更新する
        """
        if pos in (self.DevPos.BACK, self.DevPos.FRONT):
            res = self.update_shift(
                self.generate_datefix_work(
                    base_work,
                    start=base_work.start if pos == self.DevPos.BACK else new_work.end,
                    end=new_work.start if pos == self.DevPos.BACK else base_work.end,
                )
            )
            return res
        elif pos == self.DevPos.MATCH:
            res = self.calendar.delete_event(
                calendar=CALENDARID_DAIKO if base_work.requested else CALENDARID_SHIFT,
                eventid=base_work.eventid,
            )
            return res
        elif pos == self.DevPos.INCLUDE:
            res = []
            res += self.update_shift(
                self.generate_datefix_work(
                    base_work, start=base_work.start, end=new_work.start
                )
            )
            res += self.insert_shift(
                self.generate_datefix_work(base_work, new_work.end, base_work.end)
            )
            return res
        else:
            ValueError("Invalid Devide Position")

    def request(self, eventid: str, start: dt.datetime, end: dt.datetime) -> Work:
        """
        シフトの代行を依頼する

        :param str eventid  : 代行依頼を出すシフトのeventid
        :param dt.datetime start    : 代行を依頼する枠の開始時間
        :param dt.datetime end      : 代行を依頼する枠の終了時間
        :return Work : 代行が依頼されたシフト
        """
        # 対象と依頼内容を比較のためパース
        target_work = self.get_shift(eventid=eventid)
        del eventid
        requested_work = self.generate_datefix_work(
            target_work, start, end, requested=True
        )

        # 2つの時間帯の位置関係を確認
        relative_position = self.check_need_divide(target_work, requested_work)

        res = self.insert_shift(requested_work)
        print(res)

        res = self.apply_changes_shift(target_work, requested_work, relative_position)
        print(res)

        del res
        del target_work

        return requested_work

    def contract(
        self, eventid: str, slackid: str, start: dt.datetime, end: dt.datetime
    ):
        """
        シフトの代行を依頼する

        :param str eventId  : 代行を請け負うシフトのeventid
        :param str start    : 代行を請け負うする枠の開始時間
        :param str end      : 代行を請け負うする枠の終了時間
        :return Work : 代行を請け負ったシフト
        """
        # 対象と依頼内容を比較のためパース
        name = self.slackid2name(slackid)
        target_work = self.get_shift(eventid=eventid)

        contract_work = self.generate_datefix_work(
            target_work, start, end, requested=False, staff_name=name, slackid=slackid
        )

        # 2つの時間帯の位置関係を確認
        relative_position = self.check_need_divide(target_work, contract_work)

        res = self.insert_shift(contract_work)
        print(res)

        res = self.apply_changes_shift(target_work, contract_work, relative_position)
        print(res)

        del res
        del target_work

        return contract_work

    def record_use(self, slackId: str, use_way: UseWay, action: Actions):
        """
        卒研のために記録を取る

        :param str slackId : 呼び出したユーザーのslackid
        :param UseWay use_way : ユーザーが利用したUI
        :param Actions action : ユーザーが利用した機能
        """
        date = dt.datetime.now().astimezone(timezone(TIMEZONE)).strftime("%Y/%m/%d  %X")
        self.sheet.append(
            [date, self.slackid2name(slackId), use_way.value, action.value],
            self.sheet.LOG_SHEET_NAME,
        )

    def check_space(self, date: dt.datetime):
        return self.calendar.check_freebusy(date)

    # - 未着手ポイント -#
    def make_notice_message(
        self, slackid: str, action: Actions, work: Worker, start, end, message
    ):
        return_message = None
        if action is self.Actions.CONTRACT:
            return_message = "<@{user}>さんが<@{origin}>さんのシフトの代行を引き受けました。\n日付 : {date}\n時間 : {start}~{end}\n> {message}".format(
                user=slackid,
                date=work.start.strftime("%m/%d"),
                origin=self.sheet.get_slackId2name_dict(toName=False)[work.name],
                start=start if type(start) is str else start.strftime("%H:%M"),
                end=end if type(end) is str else end.strftime("%H:%M"),
                message=message,
            )
        elif action is self.Actions.REQUEST:
            return_message = "<@{user}>さんがシフトの代行を依頼しました。\n日付 : {date}\n時間 : {start}~{end}\n> {message}".format(
                user=slackid,
                date=work.start.strftime("%m/%d"),
                start=start if type(start) is str else start.strftime("%H:%M"),
                end=end if type(end) is str else end.strftime("%H:%M"),
                message=message,
            )
        return return_message


if __name__ == "__main__":
    sc = ShiftController()
    pprint(sc.get_week_shift())
    target_work = sc.get_shift(eventid="482tl6pqqr98sm9rtae92p1s45")
    pprint(
        sc.contract(
            target_work.eventid,
            "UJVTGPGKU",
            # target_work.start + dt.timedelta(hours=1),
            target_work.start,
            target_work.end,
            # target_work.end + dt.timedelta(hours=-1),
        )
    )
    # pprint(list(sc.get_week_shift(base_date=date, grouping_by_week=True)))
    # pprint(sc.get_shift(date=date, slackid="password", only_active=True))
