import datetime as dt
import sys
from pprint import pprint

from dateutil import rrule as rr
from pytz import timezone

from settings import sc
from workmanage import Work


def calc_recurrence_pattern(start_date: dt.datetime, end_date: dt.datetime):
    """

    予定の繰り返しパターン文字列を生成する

    Args:
        start_date (datetime.datetime): パターンの開始日
        end_date (datetime.datetime): パターンの終了日

    Returns;
        str : RFC5545に準拠した繰り返しパターンの文字列

    Examples:
        calc_recurrence_pattern(date, "mon")
    """
    pattern = str(
        rr.rrule(
            freq=rr.WEEKLY, wkst=rr.SU, byweekday=rr.weekday(wkday=start_date.weekday())
        )
    ).split("\n")[1]
    pattern = "".join(
        [
            pattern,
            ";UNTIL=",
            end_date.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        ]
    )
    return pattern


def calc_first_weekday(initial_day: dt.datetime):
    """

    特定の日付から、その日を起点として、曜日をキーとした1週間の日付をdictで返す


    Args:
        initial_day (datetime.datetime): 起点となる日づけ

    Returns:
        dict : {"mon": datetime.datetime, "tue":datetime.datetime ...}
    """
    each_initial_day = {}
    for diff in range(7):
        target_day = initial_day + dt.timedelta(days=diff)
        each_initial_day[target_day.strftime("%a").lower()] = target_day
    return each_initial_day


def generate_work(work_detail: dict, date: dt.datetime):
    """

    シフト情報の辞書型からWorkクラスを作る

    Args:
        work_detail (dict): シフトの詳細情報
        date (datetime.datetime): シフトの日付

    Returns:
        Work : シフト情報を示すWorkオブジェクト

    Raises:

    Examples:

    Note:
        {"name":"","slackid":"","start":"","end":""}
    """
    start = dt.datetime.combine(
        date.date(),
        dt.time(
            hour=int(work_detail.get("start").split(":")[0]),
            minute=int(work_detail.get("start").split(":")[1]),
        ),
        tzinfo=sc.timezone,
    )
    end = dt.datetime.combine(
        date.date(),
        dt.time(
            hour=int(work_detail.get("end").split(":")[0]),
            minute=int(work_detail.get("end").split(":")[1]),
        ),
        tzinfo=sc.timezone,
    )
    slackid = (
        work_detail.get("slackid")
        if work_detail.get("slackid")
        else sc.get_name2slackId(work_detail.get("name"))
    )
    return Work(
        staff_name=work_detail.get("name"),
        start=start,
        end=end,
        slackid=slackid,
        requested=False,
        eventid=None,
    )


def parse_formdata(data: dict):
    """

    formから渡されたデータをパースする

    Args:
    Returns:
    Raises:
    Note:
    """
    # シフト期間の開始日と終了日を算出
    base_date = dt.datetime.strptime(data.get("begin"), "%Y-%m-%d").replace(
        tzinfo=sc.timezone
    )
    end_date = (
        dt.datetime.strptime(data.get("finish"), "%Y-%m-%d")
        + dt.timedelta(days=1)
        + dt.timedelta(seconds=-1)
    ).replace(tzinfo=sc.timezone)

    # 開始日から各曜日の初日を算出
    each_initial_day = calc_first_weekday(base_date)
    del each_initial_day["sun"], each_initial_day["sat"]

    # 曜日ごとの処理を開始
    for (day, date) in each_initial_day.items():
        # その曜日のパターン文を作製
        rule = calc_recurrence_pattern(start_date=date, end_date=end_date)
        print(rule, file=sys.stderr)
        for work in data.get(day):
            # 初日情報と各シフト情報からWorkオブジェクトを生成
            new_work = generate_work(work, date)
            print(new_work, file=sys.stderr)
            pprint(sc.insert_shift(new_work, rule), stream=sys.stderr)
