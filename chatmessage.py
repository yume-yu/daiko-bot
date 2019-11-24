import datetime as dt
import json
import os
import sys
from enum import Enum, auto
from pprint import pprint

import requests
from pytz import timezone

from connectgoogle import TIMEZONE
from settings import (IM_OPEN, SLACK_BOT_TOKEN, TEMP_CONVERSATION_SHEET,
                      analyzer, header, sc)


class ActionNotFoundError(Exception):
    pass


class EventNotFoundError(Exception):
    pass


class InvalidFormatError(Exception):
    pass


class TargetIsPastError(Exception):
    pass


def get_temp_conversation(slackid: str) -> dict:
    all_data = sc.sheet.get(TEMP_CONVERSATION_SHEET)
    target_index = all_data[0].index(slackid)
    temp_comversation = {
        "append_date": all_data[1][target_index],
        "action": all_data[2][target_index],
        "dates": all_data[3][target_index],
        "times": all_data[4][target_index],
        "works": all_data[5][target_index],
    }
    return temp_comversation


def update_temp_conversation(
    slackid: str,
    action: sc.Actions = None,
    dates: list = None,
    times: list = None,
    works: list = None,
    text: str = None,
):
    values = [
        dt.datetime.now().astimezone(timezone(TIMEZONE)).isoformat(),
        str(action),
        ",".join([date.strftime("%m/%d") for date in dates])
        if len(dates) > 0
        else str(None),
        ",".join(
            [
                '{{"start":{},"end":{}}}'.format(time["start"], time["end"])
                for time in times
            ]
        )
        if len(times) > 0
        else str(None),
        ",".join([worktime.eventid for work in works for worktime in work.worktime])
        if len(works) > 0
        else str(None),
        text,
    ]

    all_data = sc.sheet.get(TEMP_CONVERSATION_SHEET)
    target_index = all_data[0].index(slackid)

    sc.sheet.update(
        values,
        TEMP_CONVERSATION_SHEET,
        "B{index}:G{index}".format(index=target_index + 2),
    )


def analyze_message(message: str):
    token_list = {}
    ordered_word_list = []
    for token in analyzer.analyze(message):
        try:
            ordered_word_list.append(token.surface)
            token_list[token.part_of_speech.split(",")[0]].append(
                {"word": token.surface, "value": token.phonetic}
            )
        except (AttributeError, KeyError):
            token_list.update(
                {
                    token.part_of_speech.split(",")[0]: [
                        {"word": token.surface, "value": token.phonetic}
                    ]
                }
            )

    token_list.update({"all": ordered_word_list})
    return token_list


def convert_str2action(action: str) -> sc.Actions:
    if action == "Actions.REQUEST":
        return sc.Actions.REQUEST
    if action == "Actions.CONTRACT":
        return sc.Actions.CONTRACT
    if action == "Actions.SHOWSHIFT":
        return sc.Actions.SHOWSHIFT

    return None


def decide_action(words_count: dict):
    """
    与えられた対象単語の出現数から行動を決定して返す

    :param dict words_count : 対象の単語の出現頻度の辞書
    :return ShiftController.Actions : 推定される行動。確定できないときはNone
    """
    decided_action = None

    if words_count.get("キーワード") and words_count.get("トリガー-依頼"):
        decided_action = sc.Actions.REQUEST
        if words_count.get("トリガー-確認"):
            return decided_action
        elif words_count.get("トリガー-請負"):
            decided_action = None
        return decided_action

    if words_count.get("キーワード") and words_count.get("トリガー-請負"):
        decided_action = sc.Actions.CONTRACT
        if words_count.get("トリガー-確認"):
            return decided_action
        return decided_action

    if words_count.get("キーワード") and words_count.get("トリガー-確認"):
        decided_action = sc.Actions.SHOWSHIFT
        return decided_action

    if decided_action is None:
        raise ActionNotFoundError()

    return decided_action


def convert2valid_date(
    date: str, day=None, weekday=None, weekday_attach=None, unclear=None
):
    """
    与えら得た文字列を条件に沿ってもっともらしいdatetime.datetimeにする

    :param str  date : 変換対象の文字列
    :param bool day : 変換対象が"%d"のフォーマットであるか
    :param bool weekday : 変換対象が"[日月火水木金土]"である
    :param str  weekday_attach : 変換対象がweekdayのときに用いる補助要素
    :param bool unclear : 変換対象は日付を表す曖昧表現である

    :return datetime.datetime : 変換後の日付
    """
    print(date)
    # 呼び出された日付と00:00時間、東京のタイムゾーンを持つ"today"をつくる
    today = dt.datetime.now().astimezone(timezone(TIMEZONE))
    today = dt.datetime.strptime(
        "{}/{}/{}".format(today.year, today.month, today.day), "%Y/%m/%d"
    ).astimezone(timezone(TIMEZONE))

    target_date = None

    # 日付かを見る
    if day is None and weekday is None and unclear is None:
        # -> date is MM/DD
        try:
            target_date = dt.datetime.strptime(
                "/".join([str(today.year), date]), "%Y/%m/%d"
            ).astimezone(timezone(TIMEZONE))
        except ValueError:
            raise InvalidFormatError()
        # 過去の日付だった場合、1年後のものと解釈する
        if target_date < today:
            target_date = dt.datetime.strptime(
                "{}/{}/{}".format(
                    target_date.year + 1, target_date.month, target_date.day
                ),
                "%Y/%m/%d",
            ).astimezone(timezone(TIMEZONE))

        return target_date

    if day:
        # -> date is DD
        try:
            target_date = dt.datetime.strptime(
                "/".join([str(today.year), str(today.month), date]), "%Y/%m/%d"
            ).astimezone(timezone(TIMEZONE))
        except ValueError:
            raise InvalidFormatError()
        # 過去の日付だった場合、1ヶ月後のものと解釈する
        if target_date < today:
            target_date = dt.datetime.strptime(
                "{}/{}/{}".format(
                    target_date.year, target_date.month + 1, target_date.day
                ),
                "%Y/%m/%d",
            ).astimezone(timezone(TIMEZONE))

        return target_date

    if weekday:
        # -> date is [月|火|水|木|金|土|日]
        weedkay_list = ("日", "月", "火", "水", "木", "金", "土")
        day_of_week = int(today.strftime("%w"))
        print("day_of_week" + str(day_of_week))
        tar_day_of_week = weedkay_list.index(date)
        print("tar_day_of_week" + str(tar_day_of_week))
        if weekday_attach:
            target_date = today + dt.timedelta(days=7 + (tar_day_of_week - day_of_week))
            target_date = target_date.astimezone(timezone(TIMEZONE))
            return target_date
        diff_of_today = tar_day_of_week - day_of_week
        print(diff_of_today)
        if diff_of_today >= 0:
            target_date = today + dt.timedelta(days=diff_of_today)
        else:
            target_date = today + dt.timedelta(days=7 - diff_of_today)
        target_date = target_date.astimezone(timezone(TIMEZONE))
        return target_date

    if unclear:
        if date in ("今日", "本日"):
            target_date = today
        if date in ("明日"):
            target_date = today + dt.timedelta(days=1)

        target_date = target_date.astimezone(timezone(TIMEZONE))
        return target_date


def find_target_day(words: dict):
    """
    与えら得た文字列群から日付を探してリストにする。

    :param dict words : analyze_messageによって抽出された文字群
    :return list<dt.datetime> : 見つかった日付のリスト
    """

    suspected_target = []

    # まず%m/%dを確認
    if words.get("日付"):
        # 確実な日付があるのでいくつあるのか調べる
        for day in words.get("日付"):
            suspected_target.append(convert2valid_date(day.get("value")))
        return suspected_target

    # なければ%dを探す
    elif words.get("日付-日"):
        for day in words.get("日付-日"):
            suspected_target.append(convert2valid_date(day.get("value"), day=True))
        return suspected_target
    else:
        # それでもなければ曜日を探す
        if words.get("日付-曜日"):
            for day in words.get("日付-曜日"):
                suspected_target.append(
                    convert2valid_date(
                        day.get("value"),
                        weekday=True,
                        weekday_attach=words.get("日付-補助")[0]["value"]
                        if words.get("日付-補助")
                        else False,
                    )
                )

        # それでもなければ曖昧表現を探す
        if words.get("日付-曖昧"):
            for day in words.get("日付-曖昧"):
                suspected_target.append(
                    convert2valid_date(day.get("word"), unclear=True)
                )

        if len(suspected_target) == 0:
            suspected_target.append(convert2valid_date("今日", unclear=True))
        return suspected_target


def find_target_time(words: dict, works: list) -> (list, list):
    """
    与えられた文字列から代行の開始/終了時間を探し、対象のシフトを絞り込む
    """

    class UseWordCombination(Enum):
        ONETIME_PLUS_RANGE = auto()
        TWOTIMES = auto()

    ordered_word_list = words.get("all")
    count_doubtful_str = 0
    times = {"start": None, "end": None}
    combination = None
    times_list = []

    # 仮range作成開始

    # 時刻は何個あるか
    if words.get("時刻"):
        count_doubtful_str = len(words.get("時刻"))

    # 時刻として扱える語が2つあるときは、それでrange
    if count_doubtful_str == 2:
        combination = UseWordCombination.TWOTIMES
        times["start"] = words.get("時刻")[0]["value"]
        times["end"] = words.get("時刻")[1]["value"]
    # 時刻として扱える語が1つしかないとき
    elif count_doubtful_str == 1:
        # 時間の範囲を示す語があるか
        if words.get("時刻-補助"):
            # 範囲を示す語が1つだけふくまれているか
            if len(words.get("時刻-補助")) == 1:
                combination = UseWordCombination.ONETIME_PLUS_RANGE
                if words.get("時刻-補助")[0]["word"] == "まで":
                    times["end"] = words.get("時刻")[0]["value"]
                if words.get("時刻-補助")[0]["word"] == "から":
                    times["start"] = words.get("時刻")[0]["value"]
        # ただの数字があるか
        if words.get("名詞"):
            # あったら、時間として適切なものはいくつあるか
            for number in words.get("名詞"):
                if 0 <= number <= 19:
                    pass
                else:
                    words.remove(number)

            # 1つなら今あるものと合わせて2つでrange
            if len(words.get("名詞")) == 1:
                combination = UseWordCombination.TWOTIMES
                if ordered_word_list.index(
                    words.get("名詞")[0]["words"]
                ) < ordered_word_list.index(words.get("時刻")[0]["words"]):
                    times["start"] = "{}:00".format(words.get("名詞")[0]["words"])
                    times["end"] = words.get("時刻")[0]["value"]
                else:
                    times["start"] = words.get("時刻")[0]["value"]
                    times["end"] = "{}:00".format(words.get("名詞")[0]["words"])

    # そもそも時刻として有効なものがなかった
    elif count_doubtful_str == 0:
        # ただの数字があるか
        if words.get("名詞"):
            # あったら、時間として適切なものはいくつあるか
            for number in words.get("名詞"):
                if 0 <= number <= 19:
                    pass
                else:
                    words.remove(number)

            # 1つなら時間の範囲を示す語があるか確認
            if len(words.get("名詞")) == 1:
                # 時間の範囲を示す語があるか
                if words.get("時刻-補助"):
                    # 範囲を示す語が1つだけふくまれているか
                    if len(words.get("時刻-補助")) == 1:
                        combination = UseWordCombination.ONETIME_PLUS_RANGE
                        if words.get("時刻-補助")[0]["word"] == "まで":
                            times["end"] = "{}:00".format(words.get("名詞")[0]["words"])
                        if words.get("時刻-補助")[0]["word"] == "から":
                            times["start"] = "{}:00".format(words.get("名詞")[0]["words"])
            # 2つあるならそれをもってrange
            elif len(words.get("名詞")) == 2:
                combination = UseWordCombination.TWOTIMES
                times["start"] = "{}:00".format(words.get("名詞")[0]["words"])
                times["end"] = "{}:00".format(words.get("名詞")[1]["words"])

    # 仮range作成おわり

    # この時点で仮のrangeを作れていなかったらError
    if combination is None:
        raise ValueError("there is 3 or more/less words about times")

    # 対象のシフトが見つかっていないなら、そのまま返す
    if len(works) == 0:
        return works, [times]

    pprint(works)
    # すべての対象になりうるシフトを確認して時間帯と合うか検証する
    for work in works:
        # 対象のシフトから時間を抽出
        work_start = work.worktime[0].start.time()
        work_end = work.worktime[0].end.time()

        # 作成した時間帯をtimeにパース。このときNoneが入っていたらworktimeに合わせる
        target_start = (
            dt.time(
                int(times["start"].split(":")[0]), int(times["start"].split(":")[1])
            )
            if times["start"] is not None
            else work_start
        )
        target_end = (
            dt.time(int(times["end"].split(":")[0]), int(times["end"].split(":")[1]))
            if times["end"] is not None
            else work_end
        )

        # 時間帯とシフトが噛み合っているか確認する
        # シフト開始時間が予定開始時刻より過去、もしくはシフト終了時間が予定終了時刻より未来であるか
        if work_start > target_start or target_end > work_end:
            # そうであったなら不適切なシフトなので対処から除外
            works.remove(work)
        else:
            # そうでなかったなら適正なので、対応するworkと同じindexにそのときのtimesを保存する
            times_list.append(
                {
                    "start": target_start.strftime("%H:%M"),
                    "end": target_end.strftime("%H:%M"),
                }
            )

    return works, times_list


def check_exist_work(date: dt.datetime, slackid: str, action: sc.Actions):  # -> Worker
    if action is sc.Actions.REQUEST:
        return [sc.get_shift_by_date(date, slackid)]
    elif action is sc.Actions.CONTRACT:
        return sc.get_request_by_date(date)
    else:
        return None


def do_action(message_data, action: sc.Actions, date, time, work, text):
    # message.reply(" ".join([str(action), str(date), str(time), str(work)]))
    slackid = message_data["event"]["user"]
    if action is sc.Actions.SHOWSHIFT:
        sc.init_shift(date.strftime("%Y-%m-%d"))
        image = sc.generate_shiftimg_url()
        if image["url"] is None:
            while image["url"] is not None:
                sc.post_message(
                    "画像のアップロードに問題があったようです:cry:\n再挑戦しています。",
                    channel=message_data["event"]["channel"],
                    ts=message_data["event"]["ts"],
                )
                image = sc.generate_shiftimg_url(retry=True, filename=image["filename"])
        print(image)
        sc.post_message(
            "{}の週のシフトです".format(date.strftime("%Y/%m/%d")),
            attachments=[{"image_url": image["url"], "fields": []}],
            channel=message_data["event"]["channel"],
            ts=message_data["event"]["ts"],
        )
        sc.record_use(slackid, sc.UseWay.CHAT, action)
    elif action is sc.Actions.REQUEST:
        if not time:
            time = {"start": work.worktime[0].start, "end": work.worktime[0].end}
        sc.request(
            work.worktime[0].eventid,
            time["start"]
            if type(time["start"]) is str
            else time["start"].strftime("%H:%M"),
            time["end"] if type(time["end"]) is str else time["end"].strftime("%H:%M"),
        )
        notice_message = sc.make_notice_message(
            slackid, action, work, time["start"], time["end"], text
        )
        sc.post_message(notice_message)
        sc.record_use(slackid, sc.UseWay.CHAT, action)
    elif action is sc.Actions.CONTRACT:
        if not time:
            time = {"start": work.worktime[0].start, "end": work.worktime[0].end}
        sc.contract(
            work.worktime[0].eventid,
            slackid,
            time["start"]
            if type(time["start"]) is str
            else time["start"].strftime("%H:%M"),
            time["end"] if type(time["end"]) is str else time["end"].strftime("%H:%M"),
        )
        notice_message = sc.make_notice_message(
            slackid, action, work, time["start"], time["end"], text
        )
        sc.post_message(notice_message)
        sc.record_use(slackid, sc.UseWay.CHAT, action)


def start_chatmessage_process(message_data: dict):
    # 必要な情報を抜き出す
    bot_userid = message_data["authed_users"][0]
    user_slackid = message_data["event"].get("user")
    if user_slackid is None:
        return ""
    pprint(message_data)
    text = message_data["event"]["text"].replace("<@{}>".format(bot_userid), "")
    ts = message_data["event"]["ts"]
    received_channel = message_data["event"]["channel"]
    # DMのチャンネルを取得
    dm_channel = json.loads(
        requests.post(
            IM_OPEN,
            json=json.loads(
                json.dumps({"token": SLACK_BOT_TOKEN, "user": user_slackid})
            ),
            headers=header,
        ).text
    )["channel"]["id"]

    # 処理開始
    words = analyze_message(text)
    action = None
    dates = []
    times = []  # {"start":"HH:MM","end":"HH:MM"}
    works = []
    giveup_flag = False
    is_sequence = False

    temp_comversation = get_temp_conversation(user_slackid)
    if temp_comversation["append_date"] != "None":
        if dt.datetime.now().astimezone(timezone(TIMEZONE)) - dt.datetime.fromisoformat(
            temp_comversation["append_date"]
        ) < dt.timedelta(minutes=10):
            is_sequence = True

    try:
        action = decide_action(words)
    except ActionNotFoundError:
        if is_sequence:
            action = convert_str2action(temp_comversation["action"])
        if not action:
            sc.post_message(
                "メッセージからアクションが読み取れませんでした。ひょっとして業務外のお話ですか?",
                channel=dm_channel,
                ts=ts if message_data["event"].get("channel_type") == "im" else None,
            )
            return

    dates = find_target_day(words)
    if (
        (
            len(dates) == 0
            or (
                len(dates) == 1
                and dates[0] - dt.datetime.now().astimezone(timezone(TIMEZONE))
                < dt.timedelta(minutes=5)
            )
        )
        and temp_comversation["dates"] != "None"
        and is_sequence
    ):
        dates.remove(dates[0])
        dates.extend(
            convert2valid_date(string_date)
            for string_date in temp_comversation["dates"].split(",")
        )
    for date in dates:
        try:
            work = check_exist_work(date, user_slackid, action)
            if work:
                works.extend(work)
        except ValueError:
            pass

    # 対象になりうるシフトがあるかどうか
    if len(works) == 0 and action is not sc.Actions.SHOWSHIFT:
        sc.post_message(
            "{}には有効な対象がありません。日付を間違えていませんか?".format(
                ",".join([date.strftime("%m/%d") for date in dates])
            ),
            channel=dm_channel,
            ts=ts if message_data["event"].get("channel_type") == "im" else None,
        )
        giveup_flag = True

    # 時刻を示す文言が文中に存在する時はそれを範囲指定と判断し、範囲を取りworksとの整合性をとる
    if words.get("時刻") or words.get("名詞"):
        try:
            # 1回目でworksとの整合性をとる。
            works, times = find_target_time(words, works)
            # 2回目をすると、workが空になった時でもtimesの中身が保たれる
            works, times = find_target_time(words, works)
        except ValueError:
            sc.post_message(
                "時間の指定があるようですが時間が正確に判別できませんでした。指定する時間をDMで教えて下さい。",
                channel=dm_channel,
                ts=ts if message_data["event"].get("channel_type") == "im" else None,
            )
            giveup_flag = True

    if giveup_flag:
        update_temp_conversation(user_slackid, action, dates, times, works, text)
        return ""

    # worksが1つだけみつかっていて、timesが1つ(範囲が1つみつかった)ないしは0(範囲指定がなかった)とき
    if (len(works) == 1 and len(times) <= 1) or action is sc.Actions.SHOWSHIFT:
        do_action(
            message_data,
            action,
            works[0].worktime[0].start if len(works) != 0 else dates[0],
            times[0] if len(times) == 1 else None,
            works[0] if len(works) != 0 else None,
            text,
        )
    # workが見つからなかったとき
    elif len(works) == 0:
        update_temp_conversation(user_slackid, action, dates, times, works, text)
        sc.post_message(
            "日付{}と時間{}に対応するシフトがありませんでした。DMでシフトの日付、必要ならば時間も教えてください".format(
                ",".join([date.strftime("%Y/%m/%d") for date in dates]),
                "{}~{}".format(times[0]["start"], times[0]["end"])
                if len(times) > 0
                else "指定なし",
            ),
            channel=dm_channel,
            ts=ts if message_data["event"].get("channel_type") == "im" else None,
        )
    elif len(works) >= 2:
        update_temp_conversation(user_slackid, action, dates, times, works, text)
        sc.post_message(
            "対応するシフトが複数見つかりました。DMで日付や時間を教えて貰えれば絞り込めるかもしれません。\n日付:{}\n時間:{}".format(
                ",".join([date.strftime("%Y/%m/%d") for date in dates]),
                "{}~{}".format(times[0]["start"], times[0]["end"])
                if len(times) > 0
                else "指定なし",
            ),
            channel=dm_channel,
            ts=ts if message_data["event"].get("channel_type") == "im" else None,
        )

    return ""


if __name__ == "__main__":

    words, words_count = analyze_message(sys.argv[1])
    print(words)
    temp = get_temp_conversation("U862Z509F")
    print(type(temp["append_date"]))
    """
    with open(sys.argv[1], "r") as file:
        while True:
            string = file.readline()
            if string == "":
                break
            print("#------------------------------------------#")
            print(string.replace("\n", ""))
            words, words_count = analyze_message(string)
            print(decide_action(words_count))
            # pprint(words)
            for t in find_target_day(words, words_count):
                print(t.strftime("%Y/%m/%d"))
            print("#------------------------------------------#\n")
    """
