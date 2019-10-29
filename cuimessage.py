import datetime as dt
import json
import re
from enum import Enum, auto
from pprint import pprint

import requests
from pytz import timezone

from connectgoogle import TIMEZONE
from shiftcontroller import ShiftController
from workmanage import Shift

sc = ShiftController()

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
IMG_HELPMSG = "\n".join(
    [
        ">シフトの画像を表示する",
        ">",
        ">usage: */d img [<date>]*",
        ">\t*date* : 表示するシフトの基準の日付",
        ">\t\t_YYYY-mm-dd_ もしくは _mm-dd_",
        ">",
        ">ex:\t*/d img* -> 今週のシフトの画像",
        ">\t\t */d img 10-17* -> 10月17日の週のシフトの画像",
    ]
)


def make_msg(text: str):
    message = {
        "response_type": "ephemeral",
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
    }
    return message


def can_parse_time(time_string: str) -> list:
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

    return time_list.sort()


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
        date = dt.datetime.strptime(string, "%Y-%m-%d").astimezone(timezone(TIMEZONE))
        return date
    # mm-dd形式であるかを確認
    elif re.search(r"([0-9]|(0[0-9])|1([0-2]))-(([0-2][0-9])|(3[0-1]))$", string):
        date = dt.datetime.strptime(
            "{}-{}".format(today.year, string), "%Y-%m-%d"
        ).astimezone(timezone(TIMEZONE))
        # もし、今日から1週間以上前の日付であれば来年のものとして扱う
        if date < today - dt.timedelta(days=7):
            date = dt.datetime.strptime(
                "{}-{}".format(today.year + 1, string), "%Y-%m-%d"
            ).astimezone(timezone(TIMEZONE))
        return date
    raise ValueError("{} is not valiable".format(string))


def parse_shift2strlist(shift_list: list, need_name: bool):
    """
    worker型をmarkdown形式のstrにして返す

    :param list shift_list : worker型のリスト
    :param bool need_name : 返す文字列にシフトの持ち主の名前を入れるかどうか
    """
    return_str = ""
    for shift in shift_list:
        name = shift.name if need_name else ""
        for worktime in shift.worktime:
            date = worktime.start.strftime("%m-%d")
            weekday = Shift.WORKDAYS_JP[worktime.start.weekday()]
            date = "".join([date, "(", weekday, ")"])
            start = worktime.start.strftime("%H:%M")
            end = worktime.end.strftime("%H:%M")
            eventid = worktime.eventid
            return_str += " ".join(["> *", name, date, start, "~", end, eventid, "\n"])
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


def cui_ls(args: list, slackId: str):
    """
    /d ls コマンドの中身

    :param list args : 呼び出し時の引数リスト
    :param str slackId : 呼び出した人のslackId
    """

    class ListType(Enum):
        ALL = auto()
        REQUESTED = auto()
        MINE = auto()

    index = 1
    list_type = ListType.MINE
    date = today = dt.datetime.now().astimezone(timezone(TIMEZONE))
    shift_list = []

    try:
        # ここから第1引数 - リストの種類判定
        if "all".startswith(args[index]):
            index += 1
            # list_type = ListType.ALL
            raise IndexError
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

    # 日付とリストタイプをもとにリストを作る
    sc.init_shift(today.strftime("%Y-%m-%d"))

    if list_type is ListType.ALL:
        shift_list = sc.shift
    elif list_type is ListType.REQUESTED:
        shift_list = sc.get_requested_shift(date.strftime("%Y-%m-%d"))
        shift_list = "".join(
            [
                "> ",
                date.strftime("%Y-%m-%d"),
                "の週の代行依頼\n",
                parse_shift2strlist(shift_list, True),
            ]
        )
    elif list_type is ListType.MINE:
        shift_list = sc.get_parsonal_shift(slackId, date.strftime("%Y-%m-%d"))
        shift_list = "".join(
            [
                "> ",
                date.strftime("%Y-%m-%d"),
                "の週のあなたのシフト\n",
                "> *  日付\t\t\t始業 ~ 終業\tevent id\n",
                parse_shift2strlist(shift_list, False),
            ]
        )

    return make_msg(shift_list)


def cui_req(args: list, slackId: str):
    """
    /d req コマンドの中身

    :param list atgs : ユーザーから与えられた引数
    :param dict : 投稿する文章を含んだdict
    """
    index = 1
    date = today = dt.datetime.now().astimezone(timezone(TIMEZONE))
    target = None

    # 1つ目の引数を精査する
    try:
        date = can_parse_date(args[index], today)
        target = sc.get_shift_by_date(date, slackId)
    except ValueError:
        try:
            target = sc.get_shift_by_id(args[index])
        except ValueError:
            return make_msg("> targetが無効です。\n" + REQ_HELPMSG)
    except IndexError:
        return make_msg(REQ_HELPMSG)

    # 2番めの引数をチェック
    index += 1
    # 時間指定オプションを確認
    if args[index] == "-r":
        index += 1
        times = args[index].split("~").split("〜")
        print(times)

    return make_msg(REQ_HELPMSG)


def cui_con(args: list, slackId: str):
    return None


def cui_img(args: list, slackId: str):
    """
    /d img コマンドの中身

    :param list atgs : ユーザーから与えられた引数
    :param dict : 投稿する文章を含んだdict
    """

    index = 1
    date = today = dt.datetime.now().astimezone(timezone(TIMEZONE))

    # 引数の1つ目(eventid or date)を検証
    try:
        date = can_parse_date(args[index], today)
    except ValueError:
        return make_msg(IMG_HELPMSG)
    except IndexError:
        pass

        # 日付をもとに画像を作る
    sc.init_shift(date.strftime("%Y-%m-%d"))
    uploaded_file = sc.generate_shiftimg_url()

    sc.record_use(slackId, sc.UseWay.COMM, sc.Actions.SHOWSHIFT)

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
