import datetime as dt
import os
import sys
from enum import Enum, auto
from pprint import pprint

from pytz import timezone

from connectgoogle import TIMEZONE, ConnectGoogle
from workmanage import DrawShiftImg, Shift, Worker, Worktime

FONT = "./.fonts/mplus-1m-regular.ttf"


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
        self.calendar = ConnectGoogle.GoogleCalendar(self.gcon.service.calendar)
        self.drive = ConnectGoogle.GoogleDrive(self.gcon.service.drive)
        self.sheet = ConnectGoogle.GoogleSpreadSheet(self.gcon.service.sheet)
        self.shift = None
        self.id2name_dict = self.sheet.get_slackId2name_dict()

    def slackid2name(self, slackId: str):
        return self.id2name_dict.get(slackId)

    def init_shift(self, date: str = None):
        """
        自身の変数"shift"を指定された週で初期化する関数

        :param str data : 指定する週に含まれる日付
        """
        # dateがNoneなら今日を基準にする
        if date:
            date = dt.datetime.strptime(date, "%Y-%m-%d").astimezone(timezone(TIMEZONE))
        try:
            self.shift = Shift.parse_dict(self.calendar.get_week_shift(date))
        except TypeError:
            print("Opps, GCalendar is empty", file=sys.stderr)

    def get_parsonal_shift(self, slackId: str, date: str = None) -> list:
        """
        指定された日付の週のシフトの中から、特定のslackidの人のWorkerをリストにして返す

        :param str slackId : slackid
        :param str date = None : シフトを探す週の基準の日付。Noneなら実行された時間
        :return list<Worker>
        """
        self.init_shift(date)
        return self.shift.get_shift_of_member(self.slackid2name(slackId))

    def get_requested_shift(self, date: str = None) -> list:
        """
        指定された日付の週のシフトの中から、代行依頼が出ているWorkerをリストにして返す

        :param str date = None : シフトを探す週の基準の日付。Noneなら実行された時間
        :return list<Worker>
        """
        self.init_shift(date)
        return self.shift.get_requested_shift()

    def get_shift_by_date(self, date: dt.datetime, slackId: str) -> Worker:
        """
        指定された日付の指定されたユーザーのシフトをWorkerにして返す

        :param datetime.datetime date : 探すシフトがある日付
        :param str slackId : 検索対象のユーザーのslackId
        :return Worker
        """

        name = self.slackid2name(slackId)
        shifts_in_day = self.calendar.get_day_schedule(date)

        if shifts_in_day is None:
            raise ValueError("there is no works at the date")

        for work in shifts_in_day:
            worker_obj = self.calendar.convert_event_to_worker(work)
            if worker_obj.name == name:
                return worker_obj

        raise ValueError("there is no your work at the date")

    def get_shift_by_id(self, eventid) -> Worker:
        """
        指定されたeventidの予定をWorkerにcastして返す

        :param str eventid
        :return Worker
        """
        target = self.calendar.get_schedule(eventid)

        if target is None:
            raise ValueError("invalid eventid")
        return self.calendar.convert_event_to_worker(target)

    def generate_shiftimg_url(self) -> str:
        """
        現在のシフトの画像のurlを返す

        :return str : 画像のurl
        """
        filename = "{}.jpg".format(dt.datetime.now().strftime("%Y%m%d%H%M%S%f"))
        DrawShiftImg(self.shift, FONT).makeImage().save(filename, quality=95)
        image_url = self.drive.upload4share(filename, filename, self.drive.JPEGIMAGE)
        os.remove(filename)
        return {"url": image_url, "filename": filename}

    def generate_datefix_worktime(
        self, target: Worktime, start: str, end: str
    ) -> Worktime:
        """
        指定されたtargetと同じ日付かつ指定された労働時間のworktimeを作ります。作成されたworktimeのstart,endはtimezoneの情報をもったdatetimeObjectです。

        :param worktime target: 日付を揃える対象のworktime
        :param str start: 作成するworktimeの開始時間
        :param str end: 作成するworktimeの終了時間

        :return Worktime
        """

        made_obj = Worktime(
            start=dt.datetime.strptime(
                " ".join([target.start.strftime("%Y-%m-%d"), start]), "%Y-%m-%d %H:%M"
            ).astimezone(timezone(TIMEZONE)),
            end=dt.datetime.strptime(
                " ".join([target.end.strftime("%Y-%m-%d"), end]), "%Y-%m-%d %H:%M"
            ).astimezone(timezone(TIMEZONE)),
        )
        return made_obj

    def check_need_divide(self, original: Worktime, request: Worktime):
        """
        指定された2つのworktimeの位置関係を示す

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

    def request(self, eventId: str, start: str, end: str):
        """
        シフトの代行を依頼する

        :param str eventId  : 代行依頼を出すシフトのeventid
        :param str start    : 代行を依頼する枠の開始時間
        :param str end      : 代行を依頼する枠の終了時間
        """
        # 対象と依頼内容を比較のためパース
        target_schedule = self.get_shift_by_id(eventId)
        requested_worktime = Worktime(
            target_schedule.worktime[0].start.replace(
                hour=int(start.split(":")[0]), minute=int(start.split(":")[1])
            ),
            target_schedule.worktime[0].end.replace(
                hour=int(end.split(":")[0]), minute=int(end.split(":")[1])
            ),
        )
        pprint(requested_worktime)

        # 2つの時間帯の位置関係を確認
        relative_position = self.check_need_divide(
            target_schedule.worktime[0], requested_worktime
        )

        # 位置関係に応じて予定を変更
        if relative_position is self.DevPos.FRONT:
            res = self.calendar.update_schedule(
                eventid=target_schedule.worktime[0].eventid,
                summary=target_schedule.name + "-代行",
                start=requested_worktime.start,
                end=requested_worktime.end,
            )
            print("update :{} ".format(res))
            res = self.calendar.insert_schedule(
                name=target_schedule.name,
                start=requested_worktime.end,
                end=target_schedule.worktime[0].end,
            )
            print("insert :{} ".format(res))
        elif relative_position is self.DevPos.BACK:
            res = self.calendar.update_schedule(
                eventid=target_schedule.worktime[0].eventid,
                summary=target_schedule.name,
                start=target_schedule.worktime[0].start,
                end=requested_worktime.start,
            )
            print("update :{} ".format(res))
            res = self.calendar.insert_schedule(
                name=target_schedule.name + "-代行",
                start=requested_worktime.start,
                end=requested_worktime.end,
            )
            print("insert :{} ".format(res))
        else:
            res = self.calendar.update_schedule(
                eventid=target_schedule.worktime[0].eventid,
                summary=target_schedule.name + "-代行",
                start=target_schedule.worktime[0].start,
                end=target_schedule.worktime[0].end,
            )

    def contract(self, eventId: str, slackId: str, start: str, end: str):
        """
        シフトの代行を依頼する

        :param str eventId  : 代行を請け負うシフトのeventid
        :param str start    : 代行を請け負うする枠の開始時間
        :param str end      : 代行を請け負うする枠の終了時間
        """
        # 対象と依頼内容を比較のためパース
        name = self.slackid2name(slackId)
        target_schedule = self.calendar.convert_event_to_worker(
            self.calendar.get_schedule(eventId)
        )
        contract_worktime = Worktime(
            target_schedule.worktime[0].start.replace(
                hour=int(start.split(":")[0]), minute=int(start.split(":")[1])
            ),
            target_schedule.worktime[0].end.replace(
                hour=int(end.split(":")[0]), minute=int(end.split(":")[1])
            ),
        )

        # 位置関係に応じて予定を変更
        relative_position = self.check_need_divide(
            target_schedule.worktime[0], contract_worktime
        )

        # 位置関係に応じて予定を変更
        if relative_position is self.DevPos.FRONT:
            res = self.calendar.update_schedule(
                eventid=target_schedule.worktime[0].eventid,
                summary=name,
                start=contract_worktime.start,
                end=contract_worktime.end,
            )
            print("update :{} ".format(res))
            res = self.calendar.insert_schedule(
                name=target_schedule.name + "-代行",
                start=contract_worktime.end,
                end=target_schedule.worktime[0].end,
            )
            print("insert :{} ".format(res))
        elif relative_position is self.DevPos.BACK:
            res = self.calendar.update_schedule(
                eventid=target_schedule.worktime[0].eventid,
                summary=target_schedule.name + "-代行",
                start=target_schedule.worktime[0].start,
                end=contract_worktime.start,
            )
            print("update :{} ".format(res))
            res = self.calendar.insert_schedule(
                name=name, start=contract_worktime.start, end=contract_worktime.end
            )
            print("insert :{} ".format(res))
        elif relative_position is self.DevPos.INCLUDE:
            res = self.calendar.update_schedule(
                eventid=target_schedule.worktime[0].eventid,
                summary=target_schedule.name + "-代行",
                start=target_schedule.worktime[0].start,
                end=contract_worktime.start,
            )
            print("update :{} ".format(res))
            res = self.calendar.insert_schedule(
                name=name, start=contract_worktime.start, end=contract_worktime.end
            )
            print("insert :{} ".format(res))
            res = self.calendar.insert_schedule(
                name=target_schedule.name + "-代行",
                start=contract_worktime.end,
                end=target_schedule.worktime[0].end,
            )
            print("insert :{} ".format(res))
        else:
            res = self.calendar.update_schedule(
                eventid=target_schedule.worktime[0].eventid,
                summary=name,
                start=target_schedule.worktime[0].start,
                end=target_schedule.worktime[0].end,
            )

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


if __name__ == "__main__":
    empty = ShiftController()
    empty.init_shift()
    empty.get_parsonal_shift("U862Z509F")
    # print(empty.shift)
    # event = empty.calendar.get_schedule("6is9mrnpb16c1klohd0o9ugefn_20190712T000000Z")
    # empty.request("imkiuofjatoigtvge0ekkosst8", "11:00", "12:00")
    # empty.init_shift("2019-07-09")
    # print(empty.generate_shiftimg_url())
    # empty.contract("imkiuofjatoigtvge0ekkosst8", "U1D6LQ997", "11:00", "12:00")
    # empty.init_shift("2019-07-09")
    # print(empty.generate_shiftimg_url())
