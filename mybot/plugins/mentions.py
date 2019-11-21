# coding: utf-8
import datetime as dt
import json
import os
import sys

import requests
from pytz import timezone
from slackbot.bot import default_reply  # 該当する応答がない場合に反応するデコーダ
from slackbot.bot import listen_to  # チャネル内発言で反応するデコーダ
from slackbot.bot import respond_to  # @botname: で反応するデコーダ

from chatmessage import *

# @respond_to('string')     bot宛のメッセージ
#                           stringは正規表現が可能 「r'string'」
# @listen_to('string')      チャンネル内のbot宛以外の投稿
#                           @botname: では反応しないことに注意
#                           他の人へのメンションでは反応する
#                           正規表現可能
# @default_reply()          DEFAULT_REPLY と同じ働き
#                           正規表現を指定すると、他のデコーダにヒットせず、
#                           正規表現にマッチするときに反応
#                           ・・・なのだが、正規表現を指定するとエラーになる？

# message.reply('string')   @発言者名: string でメッセージを送信
# message.send('string')    string を送信
# message.react('icon_emoji')  発言者のメッセージにリアクション(スタンプ)する
#                               文字列中に':'はいらない

SLACK_BOT_TOKEN = os.environ["SLACK_OAUTH_TOKEN"]


@respond_to("こんちは")
def mention_func(message):
    print(message.body)
    print(message)
    message.reply("www", in_thread=True)


@respond_to("メンション")
def mention_func(message):
    print("catch DM")
    message.reply("私にメンションと言ってどうするのだ")  # メンション


SLACK_DM_HISTORY_API = "https://slack.com/api/im.history?token={token}&channel={channel}&count=1&inclusive=1&latest={ts}&pretty=1"


def reget_message(message):
    # DMでのみ起こる先頭文字列カット対策でAPIから文字列取得
    res = requests.get(
        SLACK_DM_HISTORY_API.format(
            token=SLACK_BOT_TOKEN,
            channel=message.body["channel"],
            ts=message.body["event_ts"],
        )
    )
    res_dict = json.loads(res.text)
    if res_dict["ok"]:
        return res_dict["messages"][0]["text"]
    else:
        return message.body["text"]


@default_reply
def mention_func(message):
    # DMでのみ起こる先頭文字列カット対策でAPIから文字列取得
    text = reget_message(message)
    words, words_count = analyze_message(text)
    print(message.body)
    # message.reply(str(words))
    action = None
    dates = []
    times = []  # {"start":"HH:MM","end":"HH:MM"}
    works = []
    giveup_flag = False
    is_sequence = False

    sys.stderr.write(message.body["user"])
    temp_comversation = get_temp_conversation(message.body["user"])
    if temp_comversation["append_date"] != "None":
        if dt.datetime.now().astimezone(timezone(TIMEZONE)) - dt.datetime.fromisoformat(
            temp_comversation["append_date"]
        ) < dt.timedelta(minutes=10):
            is_sequence = True

    try:
        action = decide_action(words_count)
    except ActionNotFoundError:
        if is_sequence:
            action = convert_str2action(temp_comversation["action"])
        if not action:
            message.direct_reply("メッセージからアクションが読み取れませんでした。ひょっとして業務外のお話ですか?")
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
            work = check_exist_work(date, message.body["user"], action)
            if work:
                works.extend(work)
        except ValueError:
            pass

    # 対象になりうるシフトがあるかどうか
    if len(works) == 0 and action is not sc.Actions.SHOWSHIFT:
        message.direct_reply(
            "{}には有効な対象がありません。日付を間違えていませんか?".format(
                ",".join([date.strftime("%m/%d") for date in dates])
            )
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
            message.direct_reply("時間の指定があるようですが時間が正確に判別できませんでした。指定する時間をDMで教えて下さい。")
            giveup_flag = True

    if giveup_flag:
        update_temp_conversation(
            message.body["user"], action, dates, times, works, text
        )
        return

    # worksが1つだけみつかっていて、timesが1つ(範囲が1つみつかった)ないしは0(範囲指定がなかった)とき
    if (len(works) == 1 and len(times) <= 1) or action is sc.Actions.SHOWSHIFT:
        do_action(
            message,
            action,
            works[0].worktime[0].start if len(works) != 0 else dates[0],
            times[0] if len(times) == 1 else None,
            works[0] if len(works) != 0 else None,
            text,
        )
    # workが見つからなかったとき
    elif len(works) == 0:
        update_temp_conversation(
            message.body["user"], action, dates, times, works, text
        )
        message.direct_reply(
            "日付{}と時間{}に対応するシフトがありませんでした。DMでシフトの日付、必要ならば時間も教えてください".format(
                ",".join([date.strftime("%Y/%m/%d") for date in dates]),
                "{}~{}".format(times[0]["start"], times[0]["end"])
                if len(times) > 0
                else "指定なし",
            )
        )
    elif len(works) >= 2:
        update_temp_conversation(
            message.body["user"], action, dates, times, works, text
        )
        message.direct_reply(
            "対応するシフトが複数見つかりました。DMで日付や時間を教えて貰えれば絞り込めるかもしれません。\n日付:{}\n時間:{}".format(
                ",".join([date.strftime("%Y/%m/%d") for date in dates]),
                "{}~{}".format(times[0]["start"], times[0]["end"])
                if len(times) > 0
                else "指定なし",
            )
        )


@listen_to("リッスン")
def listen_func(message):
    message.send("誰かがリッスンと投稿したようだ")  # ただの投稿
    message.reply("君だね？")  # メンション
