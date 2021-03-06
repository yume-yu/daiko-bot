import datetime as dt
import json
import re
import sys
from enum import Enum, auto
from pprint import pprint

import requests

from settings import sc
from workmanage import Shift, Work

D_HELPMSG = "\n".join(
    [
        ">usage: */d command*",
        ">\t*command [args]*",
        ">\t\t*ls*\t\tシフトの一覧を表示",
        ">\t\t\t\t\t/d ls [<type>] [<date>]",
        ">",
        ">\t\t*req*\t代行依頼を出す",
        ">\t\t\t\t\t/d req <target> [-r <range>] <comment>",
        ">",
        ">\t\t*con*\t代行依頼を受ける",
        ">\t\t\t\t\t/d con <target> [-r <range>] [<comment>]",
        ">",
        ">\t\t*img*\tシフトの画像を表示",
        ">\t\t\t\t\t/d img [<date>]",
        ">",
        ">\t\t*help*\tこのヘルプを表示",
    ]
)
LS_HELPMSG = "\n".join(
    [
        ">シフトの一覧を表示する",
        ">",
        ">usage: */d ls [<type>] [<date>]*",
        ">\t*type* : シフトの種類",
        ">\t\t*m , mine*\t\t\t: 自分のシフト",
        ">\t\t*r , requested*\t: 代行依頼が出ているシフト",
        ">\t*date* : 表示するシフトの基準の日付",
        ">\t\t_YYYY-mm-dd_ もしくは _mm-dd_",
        ">",
        ">ex:\t*/d ls* -> 今週の自分のシフト",
        ">\t\t */d ls r 10-17* -> 10月17日の週の代行依頼一覧",
    ]
)
REQ_HELPMSG = "\n".join(
    [
        ">シフトの代行依頼を出す",
        ">",
        ">usage: */d req <target> [-r <range>] <comment>*",
        ">",
        ">\t*target* : シフトのeventidか日付。1日に複数のシフトがある場合はeventidのみ",
        ">\t\t*eventid*\t: _/d ls_ で確認できる予定のid",
        ">\t\t*日付 *\t\t: _YYYY-mm-dd_ もしくは _mm-dd_",
        ">",
        ">\t*comment* : 代行依頼についてのコメント。依頼の理由など",
        ">",
        ">\t*range* : 部分的に代行依頼を出す時間。 _HH:MM-HH:MM_",
        ">",
        ">ex:\t*/d req 2019-10-17 補講のため代行お願いします*",
        ">\t\t */d req 2umeidsspou2h1sj16d54464e7 体調不良のため代行お願いします*",
    ]
)
CON_HELPMSG = "\n".join(
    [
        ">シフトの代行依頼を請け負う",
        ">",
        ">usage: */d con <target> [-r <range>] [<comment>]*",
        ">",
        ">\t*target* : シフトのeventid",
        ">",
        ">\t*range* : 部分的に請け負う場合、代わる時間。 _HH:MM-HH:MM_",
        ">",
        ">\t*comment* : シフトに就いてのコメント。特記すべきことがあれば",
        ">",
        ">ex:\t */d con 2umeidsspou2h1sj16d54464e7*",
        ">\t\t */d req 2umeidsspou2h1sj16d54464e7 -r 13:00~14:00*",
    ]
)
IMG_HELPMSG = "\n".join(
    [
        ">シフトの画像を表示する",
        ">",
        ">usage: */d img [<date>] [-w]*",
        ">\t*date* : 表示するシフトの基準の日付",
        ">\t\t_YYYY-mm-dd_ もしくは _mm-dd_",
        ">\t*-w 生成するシフト画像を一週間分にする*",
        ">",
        ">ex:\t*/d img* -> 今日のシフトの画像",
        ">\t\t */d img 10-17 -w* -> 10月17日の週のシフトの画像",
    ]
)


class TimeOverhangError(Exception):
    pass


class InvalidTimeFormatError(Exception):
    pass


def make_msg(text: str):
    message = {
        "response_type": "ephemeral",
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
    }
    return message


def cui_error(text):
    print(
        "[{}]-cuiinterface {}".format(dt.datetime.now().isoformat(), text),
        file=sys.stderr,
    )


def can_parse_time(time_string: str) -> dt.time:
    """
    与えられたstringがHH:MM形式かつもっともらしい時間表記であればdatetime.timeにして返す

    :param str time_string : チェックする文字列
    """
    try:
        return dt.time.fromisoformat(time_string)
    except ValueError:
        raise ValueError("{} is Invalid format ".format(time_string))


def can_split_times_string(string: str) -> list:
    """
    与えられた文字列がHH:MM~HH:MM形式として適切なら2つを分割しlistにして返す

    :param str string : HH:MM~HH:MM形式の文字列
    :return list: datetime.time のリスト
    """

    # 区切り文字として利用可能なもののタプル
    TARGET_SEPARATE_SYMBOLS = ("~", "〜")
    time_list = []

    # 区切れるかをチェック
    for symbol in TARGET_SEPARATE_SYMBOLS:
        if symbol in string:
            time_list = string.split(symbol)
            break

    # リストが空であるか3つ上の要素に分割できたらエラー
    if not time_list or len(time_list) > 2:
        raise ValueError("{} is invalid format".format(string))

    try:
        for time in time_list:
            time_list[time_list.index(time)] = can_parse_time(time)
    except ValueError:
        raise ValueError("{} is invalid format".format(string))

    time_list.sort()

    return time_list


def check_times(target_work: Work, times: str):
    try:
        # 引数の文字列が妥当かを判断
        target_time = [
            dt.datetime.combine(target_work.start.date(), time)
            for time in can_split_times_string(times)
        ]
        print(target_time)
    except ValueError:
        # 与えられた文字列がHH:MM~HH:MMではない
        raise InvalidTimeFormatError()

    try:
        # 代行依頼の分割位置チェックを使って指定された時刻の範囲が妥当かを判断
        devide = sc.check_need_divide(
            original=target_work,
            request=sc.generate_datefix_work(
                target_work, target_time[0], target_time[1]
            ),
        )
    except ValueError:
        # 時刻の範囲がはみ出している
        raise TimeOverhangError()

    return target_time, devide


def can_parse_date(string: str, today: dt):
    """
    引数の文字列が日付として適切なら、実行した日以降でもっともらしい日付を返す

    :param str string : チェックする文字列
    :param datetime today : 実行時基準の日付
    :return datetime : 基準以降のもっともらしい日付
    """
    date = None
    # yyyy-mm-dd形式であるかを確認
    if re.search(r"2[0-9]{3}-((0[0-9])|1([0-2]))-(([0-2][0-9])|(3[0-1]))$", string):
        date = dt.datetime.strptime(string, "%Y-%m-%d").astimezone(sc.timezone)
        return date
    # mm-dd形式であるかを確認
    elif re.search(r"([0-9]|(0[0-9])|1([0-2]))-(([0-2][0-9])|(3[0-1]))$", string):
        date = dt.datetime.strptime(
            "{}-{}".format(today.year, string), "%Y-%m-%d"
        ).astimezone(sc.timezone)
        # もし、今日から1週間以上前の日付であれば来年のものとして扱う
        if date < today - dt.timedelta(days=7):
            date = dt.datetime.strptime(
                "{}-{}".format(today.year + 1, string), "%Y-%m-%d"
            ).astimezone(sc.timezone)
        return date
    raise ValueError("{} is not valiable".format(string))


def parse_shift2strlist(shift_list: list, need_name: bool):
    """
    Workのリストをmarkdown形式のstrにして返す

    :param list shift_list : worker型のリスト
    :param bool need_name : 返す文字列にシフトの持ち主の名前を入れるかどうか
    """
    return_str = ""
    for work in shift_list:
        name = work.staff_name if need_name else ""
        requested = "[依頼済]"
        date = work.start.strftime("%m-%d")
        weekday = Shift.WORKDAYS_JP[work.start.weekday()]
        date = "".join([date, "(", weekday, ")"])
        start = work.start.strftime("%H:%M")
        end = work.end.strftime("%H:%M")
        eventid = work.eventid
        return_str += " ".join(
            [
                "> *",
                name,
                date,
                start,
                "~",
                end,
                eventid,
                requested if work.requested else "",
                "\n",
            ]
        )
    return return_str


def ready_to_responce(responce_data):
    """
    slackからのレスポンスデータを受け取り/dの一連の対応を実行する。threadで別スレッド実行することを想定している。

    :param object responce_data : slack slash commandが返すレスポンスデータ
    """
    args = "{}".format(responce_data["text"]).split(" ")
    slackid = responce_data["user_id"]
    response_url = responce_data["response_url"]
    res = requests.post(
        responce_data["response_url"],
        json=json.loads(json.dumps(make_msg("".join(["/d ", responce_data["text"]])))),
    )
    return_block = check_args(args, slackid)
    res = requests.post(response_url, json=json.loads(json.dumps(return_block)))


def check_args(args: list, slackId: str):
    """
    引数の1番目を見て処理を振り分ける

    :param list atgs : ユーザーから与えられた引数
    :param dict : 投稿する文章を含んだdict
    """
    print(args)
    if args[0] in ["ls", "req", "con", "img"]:
        if args[0] == "ls":
            return cui_ls(args, slackId)
        elif args[0] == "req":
            return cui_req(args, slackId)
        elif args[0] == "con":
            return cui_con(args, slackId)
        elif args[0] == "img":
            return cui_img(args, slackId)
    else:
        return make_msg(D_HELPMSG)


def cui_ls(args: list, slackid: str):
    """
    /d ls コマンドの中身

    :param list args : 呼び出し時の引数リスト
    :param str slackid : 呼び出した人のslackId
    """

    class ListType(Enum):
        ALL = auto()
        REQUESTED = auto()
        MINE = auto()

    index = 1
    list_type = ListType.MINE
    date = today = dt.datetime.now().astimezone(sc.timezone)
    shift_list = []

    try:
        # ここから第1引数 - リストの種類判定
        if "all".startswith(args[index]):
            index += 1
            list_type = ListType.ALL
        elif "requested".startswith(args[index]):
            index += 1
            list_type = ListType.REQUESTED
        elif "mine".startswith(args[index]):
            index += 1
    except IndexError:
        list_type = ListType.MINE

    # ここから第2引数 - 基準日付判定
    try:
        date = can_parse_date(args[index], today)
    except ValueError:
        return make_msg(LS_HELPMSG)
    except IndexError:
        date = today

    if list_type is ListType.ALL:
        shift_list = sc.get_week_shift(base_date=date)
        shift_list = "".join(
            [
                "> ",
                date.strftime("%Y-%m-%d"),
                "の週のすべてのシフト\n",
                parse_shift2strlist(shift_list, True),
            ]
        )
    elif list_type is ListType.REQUESTED:
        shift_list = sc.get_week_shift(base_date=date, only_requested=True)
        shift_list = "".join(
            [
                "> ",
                date.strftime("%Y-%m-%d"),
                "の週の代行依頼\n",
                parse_shift2strlist(shift_list, True),
            ]
        )
    elif list_type is ListType.MINE:
        shift_list = sc.get_week_shift(
            base_date=date, slackid=slackid, only_active=True
        )
        shift_list = "".join(
            [
                "> ",
                date.strftime("%Y-%m-%d"),
                "の週のあなたのシフト\n",
                "> *  日付\t\t\t始業 ~ 終業\tevent id\n",
                parse_shift2strlist(shift_list, False),
            ]
        )

    return make_msg(str(list_type) + "\n" + shift_list)


def cui_req(args: list, slackid: str):
    """
    /d req コマンドの中身

    :param list atgs : ユーザーから与えられた引数
    :param dict : 投稿する文章を含んだdict
    """
    index = 1
    date = today = dt.datetime.now().astimezone(sc.timezone)
    target = None
    target_time = None
    comment = ""

    # 1つ目の引数を精査する
    try:
        date = can_parse_date(args[index], today)
        target = sc.get_shift(date=date, slackid=slackid, only_active=True)
        if len(target) == 0:
            return make_msg("> Error : この日にはシフトがありません\n" + REQ_HELPMSG)
    except ValueError:
        try:
            target = sc.get_shift(eventid=args[index])
        except ValueError:
            return make_msg("> Error : targetが無効です。\n" + REQ_HELPMSG)
    except IndexError:
        return make_msg(REQ_HELPMSG)

    # 2番めの引数をチェック
    index += 1
    try:
        # 時間指定オプションを確認
        if args[index] == "-r":
            index += 1
            try:
                # 引数の文字列が妥当かを判断
                target_time, devide = check_times(target, args[index])
            except TimeOverhangError:
                # 時刻の範囲がはみ出している
                return make_msg("> Error : 時刻の範囲が不適切です\n" + CON_HELPMSG)
            except InvalidTimeFormatError:
                # 与えられた文字列がHH:MM~HH:MMではない
                return make_msg("> Error : 時刻指定の文字列が不適切です\n" + CON_HELPMSG)
            except IndexError:
                return make_msg("> Error : rangeが不正です\n" + CON_HELPMSG)

            # 時間指定を受け取ったので次の引数を参照する
            index += 1

        # 2番めor4番目の引数をcheck
        if args[index]:
            comment = " ".join(args[index:])
    except IndexError:
        return make_msg("> Error : commentがありません\n" + REQ_HELPMSG)

        # 代行の開始時間と終了時間を整理
    start = target.start if target_time is None else target_time[0]
    end = target.end if target_time is None else target_time[1]

    sc.request(eventid=target.eventid, start=start, end=end)
    sc.post_message(
        sc.make_notice_message(slackid, sc.Actions.REQUEST, target, start, end, comment)
    )
    sc.record_use(slackid, sc.UseWay.COMM, sc.Actions.REQUEST)

    return make_msg(
        "> 代行を依頼しました。\n> date : {} \n> time: {}~{}\n> comment: {}".format(
            target.start.strftime("%Y-%m-%d"), start, end, comment
        )
    )


def cui_con(args: list, slackid: str):
    """
    /d con コマンドの中身

    :param list atgs : ユーザーから与えられた引数
    :param dict : 投稿する文章を含んだdict
    """
    index = 1
    date = today = dt.datetime.now().astimezone(sc.timezone)
    target = None
    target_time = None
    comment = ""

    # 1つ目の引数を精査する
    try:
        date = can_parse_date(args[index], today)
        target = sc.get_shift(date=date, only_requested=True)
        if len(target) == 0:
            return make_msg("> Error : 対象になるシフトがありません\n" + CON_HELPMSG)
    except ValueError:
        try:
            target = sc.get_shift(eventid=args[index])
        except (ValueError, KeyError):
            return make_msg("> Error : targetが無効です。\n" + CON_HELPMSG)
    except IndexError:
        return make_msg(CON_HELPMSG)

    # 2番めの引数をチェック
    index += 1
    try:
        # 時間指定オプションを確認
        if args[index] == "-r":
            index += 1
            try:
                # 引数の文字列が妥当かを判断
                target_time, _ = check_times(target, args[index])
            except TimeOverhangError:
                # 時刻の範囲がはみ出している
                return make_msg("> Error : 時刻の範囲が不適切です\n" + CON_HELPMSG)
            except InvalidTimeFormatError:
                # 与えられた文字列がHH:MM~HH:MMではない
                return make_msg("> Error : 時刻指定の文字列が不適切です\n" + CON_HELPMSG)
            except IndexError:
                return make_msg("> Error : rangeが不正です\n" + CON_HELPMSG)

            # 時間指定を受け取ったので次の引数を参照する
            index += 1
    except IndexError:
        # この位置でIndexErrorならrange指定がないだけなので問題なし
        pass

    try:
        # 2番めor4番目とそれ以降の引数をコメントとしてまとめる
        comment = " ".join(args[index:])
    except IndexError:
        # コメントは必須ではないので何もしない
        pass

        # 代行の開始時間と終了時間を整理
    start = target.start if target_time is None else target_time[0]
    end = target.end if target_time is None else target_time[1]

    sc.contract(slackid=slackid, eventid=target.eventid, start=start, end=end)
    sc.post_message(
        sc.make_notice_message(
            slackid, sc.Actions.CONTRACT, target, start, end, comment
        )
    )
    sc.record_use(slackid, sc.UseWay.COMM, sc.Actions.CONTRACT)

    return make_msg(
        "> 代行を請け負いました。\n> date : {} \n> time: {}~{}\n> comment: {}".format(
            target.start.strftime("%Y-%m-%d"), start, end, comment
        )
    )


def cui_img(args: list, slackid: str):
    """
    /d img コマンドの中身

    :param list atgs : ユーザーから与えられた引数
    :param dict : 投稿する文章を含んだdict
    """

    index = 1
    shift = None
    date = today = dt.datetime.now().astimezone(sc.timezone)

    # 引数の1つ目(eventid or date)を検証
    try:
        date = can_parse_date(args[index], today)
    except ValueError:
        if args[index] in ("-w", "-W"):
            pass
        else:
            return make_msg(IMG_HELPMSG)
    except IndexError:
        pass
    else:
        index += 1

    # 日付をもとに画像を作る
    try:
        if args[index] in ("-w", "-W"):
            shift = sc.get_week_shift(
                base_date=date, grouping_by_week=True, fill_blank=True
            )
        else:
            shift = sc.get_shift(date=date, fill_blank=True)
    except IndexError:
        shift = sc.get_shift(date=date, fill_blank=True)

    uploaded_file = sc.generate_shiftimg_url(shift=shift)
    print("ok,upload success.")

    sc.record_use(slackid, sc.UseWay.COMM, sc.Actions.SHOWSHIFT)

    show_shift = {
        "response_type": "ephemeral",
        "blocks": [
            {
                "type": "image",
                "title": {
                    "type": "plain_text",
                    "text": uploaded_file["filename"],
                    "emoji": True,
                },
                "image_url": uploaded_file["url"],
                "alt_text": "Example Image",
            }
        ],
    }
    return show_shift


if __name__ == "__main__":
    pprint(make_msg(LS_HELPMSG))
