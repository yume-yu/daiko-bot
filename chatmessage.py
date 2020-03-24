# -*- coding: utf-8 -*-
import datetime as dt
import json
import os
import re
import sys
from ast import literal_eval
from enum import Enum, auto
from pprint import pprint

import requests

from connectgoogle import TIMEZONE
from settings import (IM_OPEN, SLACK_BOT_TOKEN, TEMP_CONVERSATION_SHEET,
                      analyzer, header, sc)
from workmanage import Work


class UseWordCombination(Enum):
    """

    時刻の範囲作製に利用する単語のパターン

    Attributes:
        twotimes (int): 2つの時刻で作製する
        time_and_range (int): 時刻と範囲指定で作製する
        time_and_noun (int): 時刻と名詞で作製する
        noun_and_range (int):  名詞と範囲指定で作製する
        no_need (int): 範囲を作製する必要がない

    """

    twotimes = auto()
    time_and_range = auto()
    time_and_noun = auto()
    noun_and_range = auto()
    no_need = auto()


class ActionNotFoundError(Exception):
    """

    Actionが見つからなかったときのException

    """

    pass


class ShiftNotFoundError(Exception):
    """

    対象のシフトが見つからなかった時のException

    """

    pass


def get_temp_conversation(slackid: str) -> dict:
    all_data = sc.sheet.get(TEMP_CONVERSATION_SHEET)
    target_index = all_data[0].index(slackid)
    temp_comversation = {
        "append_date": all_data[1][target_index],
        "action": all_data[2][target_index],
        "dates": all_data[3][target_index],
        "time": all_data[4][target_index],
        "works": all_data[5][target_index],
        "text": all_data[6][target_index],
    }
    return temp_comversation


def update_temp_conversation(
    slackid: str,
    action: sc.Actions = None,
    dates: list = [],
    time: dict = None,
    works: list = [],
    text: str = None,
):
    values = [
        dt.datetime.now().astimezone(sc.timezone).isoformat()
        if action is not None
        else str(None),
        str(action),
        ",".join([date.strftime("%m/%d") for date in dates])
        if len(dates) > 0
        else str(None),
        '{{"start":{},"end":{}}}'.format(time["start"], time["end"])
        if time
        else str(None),
        ",".join([worktime.eventid for work in works for worktime in work.worktime])
        if len(works) > 0
        else str(None),
        str(text),
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


def cleansing_nouns(nouns: list):
    """

    抽出された名詞を時刻として使えるものだけに絞り込む

    Args:
        nouns (list): 「名詞」ラベルの付いたデータ

    Returns:
        list : %Hとして有効な数値だけを含んだ「名刺」ラベルのデータのリスト

    """
    if nouns is None:
        return nouns

    for noun in nouns:
        try:
            if sc.BEFORE_OPEN_TIME < int(noun.get("word")) <= sc.AFTER_CLOSE_TIME:
                pass
            else:
                nouns.remove(noun)
        except ValueError:
            # intへのparseのエラーを握りつぶす
            pass
    return nouns


def convert_str2action(action: str) -> sc.Actions:
    if action == "Actions.REQUEST":
        return sc.Actions.REQUEST
    if action == "Actions.CONTRACT":
        return sc.Actions.CONTRACT
    if action == "Actions.SHOWSHIFT":
        return sc.Actions.SHOWSHIFT

    return None


def decide_action(words_count: dict, recorded_action: sc.Actions):
    """

    与えられた対象単語の出現数から行動を決定して返す

    Args:
        words_count (dict): 対象の単語の出現頻度の辞書

    Returns:
        ShiftController.Actions : 推定される行動
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

    # 見つからなければ記録されていたactionを採用
    decided_action = recorded_action

    if decided_action is None:
        raise ActionNotFoundError()

    return decided_action


def check_is_past(base: dt.datetime, date: str):
    """check_is_past

    受け取ったYYYY/mm/dd文字列が基準より過去であるかを精査し、過去であった場合は基準日の翌年の日付の文字列に変換して返す

    Args:
        base(datetime.datetime): 基準の日付。多くの場合呼び出した日付
        date(str): チェック対象の文字列

    Returns:
        datetime.datetime : 基準日より未来である日付

    """
    target = dt.datetime.strptime(date, "%Y/%m/%d").astimezone(sc.timezone)
    if target < base:
        return target.replace(year=base.year + 1)
    else:
        return target


def parse_ymd_str(
    date: str,
    base: dt.datetime = dt.datetime.combine(
        dt.date.today(), dt.time(hour=0, minute=0), sc.timezone
    ),
):
    """parse_ymd_str

    受け取ったYYYY/mm/dd or mm/dd or dd文字列の不足を補い、datetime.datetimeに変換する。
    年数の指定がない場合は指定の日付が過去であるかを精査し、過去であった場合は未来に変換する。

    Args:
        date(str): パース対象の文字列
        base(datetime.datetime): 基準の日付。デフォルト値は呼び出した時

    Returns:
        datetime.datetime : フォーマットを揃えた日付

    Raises:
        ValueError: dateのフォーマットが不適切であった

    Examples:
        parse_ymd_str("2019/10/17")

    Note:
        daiko-dict.csvによって、フィルタした文字列のみが与えられる。パターンは以下の通り
        * mm/dd
        * dd

    """

    if not isinstance(date, str):
        return None

    if re.compile(r"(\d){4}/(\d){2}/(\d){2}").search(date):
        return dt.datetime.strptime(date, "%Y/%m/%d")
    elif re.compile(r"(\d){2}/(\d){2}").search(date):
        return check_is_past(base, "/".join([str(base.year), date]))
    elif re.compile(r"((\d){2})|\d").search(date):
        return check_is_past(base, "/".join([str(base.year), str(base.month), date]))

    raise ValueError("{} is invalid format".format(date))


def parse_unclear_date(
    date: str,
    base: dt.datetime = dt.datetime.combine(
        dt.date.today(), dt.time(hour=0, minute=0), sc.timezone
    ),
):
    """parse_unclear_date

    受け取った曖昧表現の日付文字列をdatetime.datetimeに変換する。

    Args:
        date(str): パース対象の文字列
        base(datetime.datetime): 基準の日付。デフォルト値は呼び出した時

    Returns:
        datetime.datetime : 解析結果の日付

    Raises:
        ValueError: 定義されていない型だった時

    Examples:
        parse_unclear_date("today")

    Note:
        daiko-dict.csvによって、フィルタした文字列のみが与えられる。パターンは以下の通り
        * today
        * tomorrow

    """

    if date == "today":
        return base
    elif date == "tomorrow":
        return base + dt.timedelta(days=1)

    raise ValueError("{} is invalid unclear date.")


def parse_weekday(
    weekday: str,
    attach: str = None,
    base: dt.datetime = dt.datetime.combine(
        dt.date.today(), dt.time(hour=0, minute=0), sc.timezone
    ),
):
    """parse_weekday

    受け取った曜日から日付に変換する

    Args:
        date(str): 曜日情報 0=日曜日,6=土曜日 datetimeの%w基準
        attach(str): 曜日に対する補足情報
        base(datetime.datetime): 基準の日付。デフォルト値は呼び出した時

    Returns:
        datetime.datetime : フォーマットを揃えた日付

    Examples:
        parse_unclear_date("today")

    Note:
        attachにはdaiko-dict.csvによって、フィルタした文字列のみが与えられる。パターンは以下の通り
        * next
    """
    week_diff = 0

    # attachがnextなら1週間後ろにずらす
    if attach == "next":
        week_diff = 1

    return (
        base
        + dt.timedelta(days=int(weekday) - int(base.strftime("%w")) + 7 * week_diff)
    ).astimezone(sc.timezone)


def search_in_date_group(
    dates: list = None,
    days: list = None,
    base: dt.datetime = dt.datetime.combine(
        dt.date.today(), dt.time(hour=0, minute=0), sc.timezone
    ),
):
    """

    見つかった日付表現を探索してdatetime.datetimeへパースする

    Args:
        dates (list): 「日付」ラベルの付いたデータ
        days (list): 「日付-日」ラベルの付いたデータ
        base (datetime.datetime): パース時の基準にする日付

    Returns:
        list: 見つかったパース済みの日付(datetime.datetime)のリスト

    """
    dates_found = []

    if dates:
        for date in dates:
            dates_found.append(parse_ymd_str(date.get("value"), base=base))
        if dates_found:
            return dates_found

    if days:
        for day in days:
            dates_found.append(parse_ymd_str(day.get("value"), base=base))
        if dates_found:
            return dates_found

    return dates_found


def search_in_weekday_group(
    weekdays: list,
    attach: str,
    base: dt.datetime = dt.datetime.combine(
        dt.date.today(), dt.time(hour=0, minute=0), sc.timezone
    ),
):
    """

    見つかった曜日表現を探索してdatetime.datetimeへパースする

    Args:
        weekdays(list): 「日付-曜日」ラベルの付いたデータ
        attach(list): 「日付-補助」ラベルの付いたデータ
        base (datetime.datetime): パース時の基準にする日付

    Returns:
        list: 見つかったパース済みの日付(datetime.datetime)のリスト
    """
    dates_found = []

    if weekdays:
        for weekday in weekdays:
            dates_found.append(
                parse_weekday(weekday.get("value")),
                attach=attach[0].get("value") if attach else None,
                base=base,
            )

    return dates_found


def search_in_unclear_group(
    words: list,
    base: dt.datetime = dt.datetime.combine(
        dt.date.today(), dt.time(hour=0, minute=0), sc.timezone
    ),
):
    """

    見つかった曖昧日付表現を探索してdatetime.datetimeへパースする

    Args:
        words(list): 「日付-曖昧」ラベルの付いたデータ
        base (datetime.datetime): パース時の基準にする日付

    Returns:
        list: 見つかったパース済みの日付(datetime.datetime)のリスト
    """
    dates_found = []

    if words:
        for word in words:
            dates_found.append(parse_unclear_date(word.get("value"), base=base))

    return dates_found


def find_target_day(words: dict, recorded_dates: list):
    """

    解析から得られたデータから対象となる日付を探す

    Args:
        words (dict): analyze_messageによって抽出された文字群
        recorded_dates (list): temp_comversation("dates")に記録されていた日付のリスト

    Returns:
        list: 見つかった日付(datetime.datetime)のリスト
    """

    suspected_target = []
    today = dt.datetime.combine(dt.date.today(), dt.time(hour=0, minute=0), sc.timezone)

    # まず %m/%d or %d を探索
    suspected_target = search_in_date_group(
        dates=words.get("日付"), days=words.get("日付-日"), base=today
    )

    # 対象が見つかったらreturn
    if suspected_target:
        return suspected_target

    # 曜日表現を探索
    suspected_target = search_in_weekday_group(
        weekdays=words.get("日付-曜日"), attach=words.get("日付-補助"), base=today
    )

    # 対象が見つかったらreturn
    if suspected_target:
        return suspected_target

    # 曖昧日付表現を探索
    suspected_target = search_in_unclear_group(words=words.get("日付-曖昧"), base=today)

    # 対象が見つかったらreturn
    if suspected_target:
        return suspected_target

    # 記録された日付があるならreturn
    if recorded_dates:
        return recorded_dates

    # 何も見つからなければ今日を対象とする
    suspected_target.append(today)
    return suspected_target


def check_args_for_time_range(times: list, attach: list, noun: list):
    """

    時間範囲に関連するワードの発見数を精査し、作製のパターンを決定する

    Args:
        times (list): 「時刻」ラベルの付いたデータのリスト
        attach (list): 「時刻-補助」ラベルの付いたデータのリスト
        noun (list): 「名詞」ラベルの付いたデータのリスト

    Returns:
        UseWordCombination : 時間範囲作製に使われるデータのパターン

    Raises:
        ValueError : 要素の数がUseWordCombinationに規定されたどのパターンにも当てはまらない
    """
    if len(times) == 2:
        return UseWordCombination.twolen(times)

    if len(times) == len(attach) == 1:
        return UseWordCombination.time_and_range

    if len(times) == len(noun) == 1:
        return UseWordCombination.time_and_noun

    if len(noun) == len(attach) == 1:
        return UseWordCombination.time_and_noun

    if len(attach) == len(times) == 0:
        return UseWordCombination.no_need

    raise ValueError("Too many word relation time")


def search_in_time_group(times: list, attach: list, noun: list):
    """

    見つかった時刻の表現から時刻の範囲を作製する

    Args:
        times (list): 「時刻」ラベルの付いたデータ
        attach (list): 「時刻-補助」ラベルの付いたデータ
        noun (list): 「名詞」ラベルの付いたデータ

    Returns:
        dict : {"start": %H:%M, "end": %H:%M}
        None : 時間を表す語が一切なかった時

    Note:
        採用される優先度は
        時刻2つ > 時刻+補助 > 時刻+数詞
    """

    # 作製パターンを確認
    pattern = check_args_for_time_range(
        times if times else [], attach if attach else [], noun if noun else []
    )

    # 戻り値の雛形
    time_range = {"start": None, "end": None}

    if pattern is UseWordCombination.twotimes:
        time_range["start"] = times[0]["value"]
        time_range["end"] = times[1]["value"]
        return time_range

    if pattern is UseWordCombination.time_and_range:
        time_range["end"] = times[0]["value"] if attach[0]["value"] == "until" else None
        time_range["start"] = (
            times[0]["value"] if attach[0]["value"] == "from" else None
        )
        return time_range

    if pattern is UseWordCombination.time_and_noun:
        time_range["start"] = (
            times[0].get("value")
            if int(times[0].get("value").split(":")[0]) < int(noun[0].get("word"))
            else ":".join([noun[0].get("word"), "00"])
        )
        time_range["end"] = (
            times[0].get("value")
            if int(times[0].get("value").split(":")[0]) > int(noun[0].get("word"))
            else ":".join([noun[0].get("word"), "00"])
        )
        return time_range

    if pattern is UseWordCombination.noun_and_range:
        time_range["start"] = (
            ":".join([noun[0].get("word"), "00"])
            if attach[0]["value"] == "from"
            else None
        )
        time_range["end"] = (
            ":".join([noun[0].get("word"), "00"])
            if attach[0]["value"] == "until"
            else None
        )
        return time_range

    if pattern is UseWordCombination.no_need:
        return None


def find_target_time(words: dict, record_range: dict):
    """

    与えられた文字列から代行の開始/終了時間を探索する

    Args:
        words (dict): analyze_messageによって抽出された文字群
        record_range (dict): temp_comversation("time")に記録された時間の範囲

    Returns:
        dict : {"start": None, "end": None}のdict
        None : 時間を表す語が一切なかった時

    Raises:
        ValueError :  対応する時刻範囲がなかった時
    """

    try:
        time_range = search_in_time_group(
            times=words.get("時刻"), attach=words.get("時刻-補助"), noun=words.get("名詞")
        )
        return time_range
    except ValueError:
        if record_range:
            return record_range
        else:
            raise ValueError("can't find time range")


def find_target_work(works: list, time_range: dict, action: sc.Actions):
    """

    worksの中からtime_rangeに該当するworkのリストを返す

    Args:
        works (list): check_exist_workで取得したWork型のリスト
        time_range (dict): find_target_timeで取得した時間の範囲
        action (ShiftController.Actions): 呼び出し元の利用目的

    Returns:
        list : time_rangeに該当するシフト(Work型)のリスト

    """
    if action is sc.Actions.SHOWSHIFT or time_range is None:
        return works

    # time_rangeの中身をdt.timeに変換
    time_range = {
        "start": dt.time(
            hour=int(time_range.get("start").split(":")[0]),
            minite=int(time_range.get("start").split(":")[1]),
        )
        if time_range.get("end")
        else None,
        "end": dt.time(
            hour=int(time_range.get("end").split(":")[0]),
            minite=int(time_range.get("end").split(":")[1]),
        )
        if time_range.get("end")
        else None,
    }

    for work in works:
        start = (
            time_range.get("start") if time_range.get("start") else work.start.time()
        )
        end = time_range.get("end") if time_range.get("end") else work.end.time()
        if start < work.start.time() or work.end.time < end:
            works.remove(work)

    if len(works) == 0:
        raise ShiftNotFoundError()
    elif len(works) > 1:
        raise ValueError()

    return works


def check_exist_work(dates: list, slackid: str, action: sc.Actions):
    """
    指定された日付とアクションに対応するシフトを返す

    Args:
        dates (list): シフトを探す日付のリスト
        slackid (str): 検索対象のユーザーのslackid
        action (ShiftController.Actions): 呼び出し元の利用目的

    Returns:
        list: 見つかったシフトのリスト
    """
    work_found = []

    if action is sc.Actions.REQUEST:
        for date in dates:
            work_found.append(
                sc.get_shift(date=date, slackid=slackid, only_active=True)
            )
    elif action is sc.Actions.CONTRACT:
        for date in dates:
            work_found.append(sc.get_shift(date=date, only_requested=True))

    if action is not sc.Actions.SHOWSHIFT and len(work_found) == 0:
        raise ShiftNotFoundError()

    return work_found


def do_action(
    slackid: str,
    action: sc.Actions,
    date: dt.datetime,
    work: Work,
    time_range: dict,
    text: str,
    ts: str,
    receive_channel: str,
):
    """

    情報をもとにactionに対応した処理を行う


    Args:
        slackid (str): ユーザーのslackid
        action (ShiftController.Actions): メッセージから判定した処理
        date (datetime.datetime): メッセージから判定した日付
        work (Work): メッセージから抽出したシフト
        time_range (dict): メッセージから抽出した時間範囲 {"start": %H:%M, "end": %H:%M}
        text (str): メッセージの本文
        ts (str): メッセージのタイムスタンプ
        receive_channel (str): メッセージを受け取ったチャンネルのchannel id

    """
    if action is sc.Actions.SHOWSHIFT:
        image = sc.generate_shiftimg_url(shift=sc.get_shift(date=date, fill_blank=True))
        print(image, file=sys.stderr)
        sc.post_message(
            "{}のシフトです".format(date.strftime("%Y/%m/%d")),
            attachments=[{"image_url": image["url"], "fields": []}],
            channel=receive_channel,
            ts=ts,
        )

    else:
        if not time_range:
            time_range = {"start": work.start, "end": work.end}
        if action is sc.Actions.REQUEST:
            sc.request(
                work.eventid,
                time_range["start"].strftime("%H:%M"),
                time_range["end"].strftime("%H:%M"),
            )
        elif action is sc.Actions.CONTRACT:
            sc.contract(
                work.eventid,
                slackid,
                time_range["start"].strftime("%H:%M"),
                time_range["end"].strftime("%H:%M"),
            )

            notice_message = sc.make_notice_message(
                slackid, action, work, time_range["start"], time_range["end"], text
            )
            sc.post_message(notice_message)

        sc.record_use(slackid, sc.UseWay.CHAT, action)


def get_user_dm_channel(slackid: str):
    """
    指定されたslackidのユーザーとbotのDMチャンネルのchannel idを取得する

    Args:
        slackid (str): 対象のユーザーのslackid

    Returns:
        str : ユーザーとのDM channelのid
    """
    print(
        json.loads(
            requests.post(
                IM_OPEN,
                json=json.loads(
                    json.dumps({"token": SLACK_BOT_TOKEN, "user": slackid})
                ),
                headers=header,
            ).text
        )
    )
    return (
        json.loads(
            requests.post(
                IM_OPEN,
                json=json.loads(
                    json.dumps({"token": SLACK_BOT_TOKEN, "user": slackid})
                ),
                headers=header,
            ).text
        )
        .get("channel")
        .get("id")
    )


def check_in_sequence(timestamp: str):
    """

    タイムスタンプから会話が進行中であるかを判定する

    Args:
        timestamp (str): temp_comversation.get("append_date")に記録された最終更新時間

    Returns:
        bool: 会話が進行中であるか
    """
    # 最終書き込み時刻を確認 比較対象datetime.isoformat() (ex:2021-03-01T00:00:00+09:00)
    if re.compile(r"(\d){4}-(\d){2}-(\d){2}T(\d){2}:(\d){2}:(\d){2}").search(timestamp):
        if dt.datetime.now().astimezone(sc.timezone) - dt.datetime.fromisoformat(
            timestamp
        ) < dt.timedelta(minutes=10):
            return True

    return False


def start_chatmessage_process(message_data: dict):
    """

    チャット形式のメッセージを受け取った時にスレッド実行されるメソッド

    Args:
        message_data(dict): Slackから受け取ったメッセージのデータ

    Returns:
        str: 空("")を返す

    Note:
    """
    # 必要な情報を抜き出す
    bot_userid = message_data.get("authed_users")[0]
    user_slackid = message_data.get("event").get("user")
    text = message_data.get("event").get("text").replace("<@{}>".format(bot_userid), "")
    ts = message_data.get("event").get("ts")
    receive_channel = message_data.get("event").get("channel")
    receive_channel_type = message_data["event"].get("channel_type")
    dm_channel = get_user_dm_channel(slackid=user_slackid)
    del message_data

    # 処理開始
    words = analyze_message(text)
    words["名詞"] = cleansing_nouns(words.get("名詞"))
    action = None
    dates = []
    times = []  # {"start":"HH:MM","end":"HH:MM"}
    works = []
    giveup_flag = False
    is_sequence = False  # 連続した会話の途中であるフラグ

    # 一時記憶の呼び出しと会話中の判定
    temp_comversation = get_temp_conversation(user_slackid)
    is_sequence = check_in_sequence(temp_comversation.get("append_date"))

    # actionを判定
    try:
        action = decide_action(
            words,
            recorded_action=convert_str2action(
                temp_comversation.get("action") if is_sequence else None
            ),
        )
    except ActionNotFoundError:
        sc.post_message(
            "メッセージからアクションが読み取れませんでした。ひょっとして業務外のお話ですか?",
            channel=dm_channel,
            ts=ts if receive_channel_type == "im" else None,
        )
        return ""

    # 日付を探索
    dates = find_target_day(
        words,
        recorded_dates=[
            dt.datetime.fromisoformat(date)
            for date in temp_comversation.get("dates").split(",")
        ]
        if is_sequence
        else None,
    )

    # 対象のシフトの存在を確認
    try:
        works = check_exist_work(dates, user_slackid, action)
    except ShiftNotFoundError:
        sc.post_message(
            "{}には有効な対象がありません。日付を間違えていませんか?".format(
                ",".join([date.strftime("%m/%d") for date in dates])
            ),
            channel=dm_channel,
            ts=ts if receive_channel_type == "im" else None,
        )
        update_temp_conversation(
            slackid=user_slackid, action=action, dates=dates, text=text
        )
        return ""

    try:
        time_range = find_target_time(
            words, literal_eval(temp_comversation.get("time"))
        )
    except ValueError:
        sc.post_message(
            "時間の指定があるようですが時間が正確に判別できませんでした。指定する時間をDMで教えて下さい。",
            channel=dm_channel,
            ts=ts if receive_channel_type == "im" else None,
        )
        update_temp_conversation(
            slackid=user_slackid, action=action, dates=dates, time=time_range, text=text
        )
        return ""

    try:
        works = find_target_work(works, time_range, action)
    except (ShiftNotFoundError, ValueError) as e:
        update_temp_conversation(
            slackid=user_slackid,
            action=action,
            dates=dates,
            times=time_range,
            text=text,
        )
        sc.post_message(
            "日付{}と時間{}に対応するシフトがありませんでした。DMでシフトの日付、必要ならば時間も教えてください".format(
                ",".join([date.strftime("%Y/%m/%d") for date in dates]),
                "{}~{}".format(time_range["start"], time_range["end"]),
            )
            if isinstance(e, ShiftNotFoundError)
            else "対応するシフトが複数見つかりました。DMで日付や時間を教えて貰えれば絞り込めるかもしれません。\n日付:{}\n時間:{}".format(
                ",".join([date.strftime("%Y/%m/%d") for date in dates]),
                "{}~{}".format(times[0]["start"], times[0]["end"])
                if len(times) > 0
                else "指定なし",
            ),
            channel=dm_channel,
            ts=ts if receive_channel_type == "im" else None,
        )
        return ""

    update_temp_conversation(user_slackid)
    do_action(
        slackid=user_slackid,
        action=action,
        date=dates[0],
        time_range=time_range,
        work=works[0] if len(works) != 0 else None,
        text=text,
        ts=ts,
        receive_channel=receive_channel,
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
