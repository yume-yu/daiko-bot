import copy
import datetime as dt
import sys
from ast import literal_eval
from pprint import pprint

from settings import *
from settings import sc
from workmanage import Shift


def csv_to_dict(state: str) -> dict:
    """
    stateに保持していたeventid,start,endをdictに展開する
    state_data -> {"eventid":"id","start":"%H:%M","end":"%H:%M",date:"%m/%d"}

    :param str state : カンマ区切り文字列
    :return dict : 返還したdict
    """
    state_list = state.split(",")
    state_data = dict(
        {
            state_list[index]: state_list[index + 1]
            for index in range(0, len(state_list), 2)
        }
    )
    return state_data


def get_block(
    action_value: str,
    date: str = None,
    target: dict = None,
    eventid: str = None,
    value: str = None,
    slack_id: str = None,
):
    # /postに投げられる最初の応答メッセージへの応答文をつくる処理へ
    if action_value == "select_action":
        return_block = copy.deepcopy(select_action)
        if not slack_id:
            raise ValueError("in select_action, slack_id must be needed")
        return_block["blocks"][0]["text"]["text"] = "こんにちは{}さん\nようこそシフト代行システムへ".format(
            sc.slackid2name(slack_id)
        )
        return return_block
    # 代行依頼のための自分のシフト一覧を作る処理へ
    elif action_value == "to_request":
        return make_shift_list(slack_id, request=True, date=date)
    # 代行請負のための依頼済みのシフト一覧を作る処理へ
    elif action_value == "to_contract":
        return make_shift_list(slack_id, request=False, date=date)
    elif action_value == "cancel":
        return canceled
    elif action_value == "select_shift":
        return make_application_dialog(
            eventid=eventid, is_request=literal_eval(value.title())
        )
    elif action_value == "request_dialog_ok":
        return make_comfirm_request(target, value)
    elif action_value == "contract_dialog_ok":
        return make_comfirm_contract(target, value)
    elif action_value == "confirm_request":
        if not value:
            return canceled
        else:
            return request_shift(value, slack_id)
    elif action_value == "confirm_contract":
        if not value:
            return canceled
        else:
            return contract_shift(value, slack_id)
    elif action_value in ("show_shift", "switch_type"):
        return get_shift_image(slack_id, value)
    else:
        return error_message


def make_shift_list(slack_id, request: bool, date: str = None) -> dict:
    """
    シフトのリスト一覧を埋め込んだメッセージを返す

    :param      str  slack_id    : 対象の人のslackId
    :param      bool request     : 依頼か請負かを示す。True = 依頼
    :param      str  date        : 基準の日付。"%Y-%m-%d"書式。
    :return     dict
    """

    # slackのdate selectorの回答は"%Y-%m-%d"の文字列なので、dt.datetimeにconvert
    date = (
        dt.datetime.strptime(date, "%Y-%m-%d")
        if date is not None
        else dt.datetime.now()
    )
    # テンプレートをコピーして文言準備
    # 依頼か請負かでの文言変更
    made_block = copy.deepcopy(select_nearly)
    made_block["blocks"][0] = {
        "type": "section",
        "block_id": "select_shift",
        "text": {
            "type": "mrkdwn",
            "text": ("代行依頼を出すシフトを選んでください" if request else "代行依頼を受けるシフトを選んでください"),
        }
        if request
        else {"type": "mrkdwn", "text": "代行依頼を受けるシフトを選んでください"},
        "accessory": {
            "type": "static_select",
            "action_id": str(request),
            "placeholder": {
                "type": "plain_text",
                "text": "この日のあなたのシフト" if request else "この日の代行依頼",
                "emoji": True,
            },
            "options": [],
        },
    }

    # いずれかの状態のシフト一覧を取得
    shift_list = []
    if request:
        shift_list = sc.get_shift(date=date, slackid=slack_id, only_active=True)
    else:
        shift_list = sc.get_shift(date=date, only_requested=True)

    # シフト一覧部分のオブジェクトをつくる
    for work in shift_list:
        # 依頼済みリストのときは名前を表示するため名前を取得
        name = work.staff_name
        date = work.start.strftime("%m/%d")
        weekday = Shift.WORKDAYS_JP[work.start.weekday()]
        starttime = work.start.strftime("%H:%M")
        endtime = work.end.strftime("%H:%M")
        shift_block = {
            "text": {
                "type": "plain_text",
                "text": "{date}({weekday}) {name}{start}~{end}".format(
                    name="" if request else name,
                    date=date,
                    weekday=weekday,
                    start=starttime,
                    end=endtime,
                ),
                "emoji": True,
            },
            "value": work.eventid,
        }
        print(made_block["blocks"][0]["accessory"])
        made_block["blocks"][0]["accessory"]["options"].append(shift_block)

    # リストにするシフトがなかったときはない旨を書く
    if not made_block["blocks"][0]["accessory"]["options"]:
        made_block["blocks"][0] = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ("この日にはあなたのシフトはないようです" if request else "この日には代行依頼はないようです"),
            },
        }

    # このリストが依頼か代行かをflagでaction_idに記録
    made_block["blocks"][1]["accessory"]["action_id"] = str(request)

    return made_block


def make_application_dialog(eventid: str, is_request: bool):
    """
    代行を依頼/請負申請のフォームをつくる

    :param str eventid : 代行依頼を出すシフトのeventid
    """
    return_block = copy.deepcopy(request_dialog if is_request else contract_dialog)
    target = sc.get_shift(eventid=eventid)
    date = target.start.strftime("%m/%d")
    start = target.start.strftime("%H:%M")
    end = target.end.strftime("%H:%M")
    return_block["dialog"]["state"] = (
        "eventid," + eventid + ",start," + start + ",end," + end + ",date," + date
    )
    return_block["dialog"]["elements"][0]["value"] = start
    return_block["dialog"]["elements"][1]["value"] = end
    return_block["dialog"]["elements"][0]["label"] = "開始時間 - {}~".format(start)
    return_block["dialog"]["elements"][1]["label"] = "終了時間 - ~{}".format(end)
    return return_block


def make_comfirm_contract(target: dict, value: str):
    if not (target and value):
        return None

    if not target["comment"]:
        target["comment"] = ""
    else:
        target["comment"] = "\n> {}".format(target["comment"])

    return_block = copy.deepcopy(confirm_request)
    return_block["blocks"][0]["text"][
        "text"
    ] = "> {} {}~{}{}\n上の内容で代行を請け負います。\nよろしいですか?".format(
        target["date"], target["start_time"], target["end_time"], target["comment"]
    )
    return_block["blocks"][1]["elements"][0]["value"] = value
    return_block["blocks"][1]["block_id"] = "confirm_contract"
    return return_block


def make_comfirm_request(target: dict, value: str):
    if not (target and value):
        return None
    return_block = copy.deepcopy(confirm_request)
    return_block["blocks"][0]["text"][
        "text"
    ] = "> {} {}~{}\n> {}\n上の内容で代行依頼を出します。\nよろしいですか?".format(
        target["date"], target["start_time"], target["end_time"], target["comment"]
    )
    return_block["blocks"][1]["elements"][0]["value"] = value
    return_block["blocks"][1]["block_id"] = "confirm_request"
    return return_block


def request_shift(target: dict, slackid: str) -> dict:
    if not target:
        return error_message
    pprint(target)
    target_work = sc.get_shift(eventid=target["eventid"])
    start_dt = target_work.start.replace(
        hour=int(target["start"].split(":")[0]),
        minute=int(target["start"].split(":")[1]),
    )
    end_dt = target_work.end.replace(
        hour=int(target["end"].split(":")[0]), minute=int(target["end"].split(":")[1])
    )
    sc.request(target["eventid"], start_dt, end_dt)
    del start_dt, end_dt
    sc.post_message(
        sc.make_notice_message(
            slackid,
            sc.Actions.REQUEST,
            sc.get_shift(eventid=target["eventid"]),
            target["start"],
            target["end"],
            target["comment"],
        )
    )
    sc.record_use(slackid, sc.UseWay.BUTTONS, sc.Actions.REQUEST)
    return complate_request


def contract_shift(target: dict, slackid: str) -> dict:
    if not target:
        return error_message

    original_work = sc.get_shift(eventid=target["eventid"])
    start_dt = original_work.start.replace(
        hour=int(target["start"].split(":")[0]),
        minute=int(target["start"].split(":")[1]),
    )
    end_dt = original_work.end.replace(
        hour=int(target["end"].split(":")[0]), minute=int(target["end"].split(":")[1])
    )
    sc.contract(target["eventid"], slackid, start_dt, end_dt)
    sc.post_message(
        sc.make_notice_message(
            slackid,
            sc.Actions.CONTRACT,
            original_work,
            target["start"],
            target["end"],
            target["comment"],
        )
    )
    sc.record_use(slackid, sc.UseWay.BUTTONS, sc.Actions.CONTRACT)
    return complate_request


def get_shift_image(slackid, value):
    """
    シフト画像を生成,アップロードして画像を表示するメッセージを返す

    :param str slackid : 呼び出したユーザーのslackid
    """
    is_day = False
    date = dt.datetime.now()
    value_dict = {"date": None, "is_day": None}

    print(value)
    if "," in value.get("action_id"):
        value_dict = csv_to_dict(value.get("action_id"))

    if value.get("block_id") == "show_shift" and value.get("type") == "datepicker":
        date = dt.datetime.strptime(value.get("selected_date"), "%Y-%m-%d")
        is_day = literal_eval(value_dict.get("is_day"))
    elif value.get("block_id") == "switch_type":
        date = dt.datetime.strptime(value_dict.get("date"), "%Y-%m-%d")
        is_day = literal_eval(value.get("value"))
        print("ok, type is button")

    return_block = copy.deepcopy(show_shift)
    if is_day:
        shift = sc.get_shift(date=date, fill_blank=True)
    else:
        shift = sc.get_week_shift(
            base_date=date, grouping_by_week=True, fill_blank=True
        )
    uploaded_file = sc.generate_shiftimg_url(shift=shift)
    print("ok,upload success.")
    return_block["blocks"][0]["image_url"] = "{}".format(uploaded_file["url"])
    return_block["blocks"][0]["title"]["text"] = "{}".format(uploaded_file["filename"])
    return_block["blocks"][2]["accessory"]["initial_date"] = date.strftime("%Y-%m-%d")
    return_block["blocks"][2]["accessory"]["action_id"] = ",".join(
        ["is_day", str(is_day), "date", date.strftime("%Y-%m-%d")]
    )
    return_block["blocks"][3]["elements"][0]["action_id"] = ",".join(
        ["is_day", str(is_day), "date", date.strftime("%Y-%m-%d")]
    )
    return_block["blocks"][3]["elements"][0]["value"] = str(not is_day)
    sc.record_use(slackid, sc.UseWay.BUTTONS, sc.Actions.SHOWSHIFT)
    pprint(return_block)
    return return_block


name_input_dialog = {
    "delete_original": True,
    "dialog": {
        "title": "名前の登録",
        "callback_id": "Addname",
        "notify_on_cancel": True,
        "notify_on_channel": False,
        "state": "type,addname",
        "elements": [
            {
                "label": "名前(名字)",
                "type": "text",
                "value": "",
                "name": "name",
                "max_length": "5",
                "hint": "名字だけ入力してください",
            }
        ],
    },
}

contract_dialog = {
    "delete_original": True,
    "dialog": {
        "title": "代行請負フォーム",
        "callback_id": "Contract",
        "notify_on_cancel": True,
        "notify_on_channel": False,
        "state": "",
        "elements": [
            {
                "label": "開始時間",
                "type": "text",
                "value": "",
                "name": "start_time",
                "max_length": "5",
                "hint": "請け負うシフトの開始時間 cf. 09:00",
            },
            {
                "label": "終了時間",
                "type": "text",
                "value": "",
                "name": "end_time",
                "max_length": "5",
                "hint": "請け負うシフトの終了時間 cf. 12:00",
            },
            {
                "label": "コメント",
                "name": "comment",
                "type": "textarea",
                "optional": True,
                "hint": "なにかコメントがある場合は記入する",
            },
        ],
    },
}


request_dialog = {
    "delete_original": True,
    "dialog": {
        "title": "代行依頼フォーム",
        "callback_id": "Request",
        "notify_on_cancel": True,
        "notify_on_channel": False,
        "state": "",
        "elements": [
            {
                "label": "開始時間",
                "type": "text",
                "value": "",
                "name": "start_time",
                "max_length": "5",
                "hint": "依頼するシフトの開始時間 cf. 09:00",
            },
            {
                "label": "終了時間",
                "type": "text",
                "value": "",
                "name": "end_time",
                "max_length": "5",
                "hint": "依頼するシフトの終了時間 cf. 12:00",
            },
            {
                "label": "代行コメント",
                "name": "comment",
                "type": "textarea",
                "hint": "代行依頼の理由などコメントを記入する",
            },
        ],
    },
}

complate_request = {
    "blocks": [
        {"type": "section", "text": {"type": "mrkdwn", "text": "代行依頼を出しました:+1:"}}
    ]
}

confirm_request = {
    "blocks": [
        {"type": "section", "text": {"type": "mrkdwn", "text": ""}},
        {
            "type": "actions",
            "block_id": "",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "はい", "emoji": True},
                    "value": "",
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "いいえ", "emoji": True},
                    "style": "danger",
                    "value": "cancel",
                },
            ],
        },
    ]
}

error_message = {
    "replace_original": True,
    "blocks": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "問題があったようです:thinking_face:\n申し訳ないですが最初からお願いします",
            },
        }
    ],
}

cancel_button = {
    "type": "actions",
    "block_id": "start_check",
    "elements": [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "キャンセル", "emoji": True},
            "style": "danger",
            "value": "cancel",
        }
    ],
}

select_action = {
    "blocks": [
        {"type": "section", "text": {"type": "mrkdwn", "text": "ようこそシフト管理システムへ"}},
        {
            "type": "actions",
            "block_id": "start_check",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "シフトを見る", "emoji": True},
                    "value": "show_shift",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "代行を出す", "emoji": True},
                    "value": "to_request",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "代行を受ける", "emoji": True},
                    "value": "to_contract",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "キャンセル", "emoji": True},
                    "style": "danger",
                    "value": "cancel",
                },
            ],
        },
    ]
}

canceled = {
    "blocks": [
        {"type": "section", "text": {"type": "mrkdwn", "text": "キャンセルしました:wave:"}}
    ]
}


select_nearly = {
    "response_type": "ephemeral",
    "blocks": [
        {
            "type": "section",
            "block_id": "select_shift",
            "text": {"type": "mrkdwn", "text": "代行依頼を出すシフトを選んでください"},
            "accessory": {
                "type": "static_select",
                "action_id": "",
                "placeholder": {
                    "type": "plain_text",
                    "text": "この日のあなたのシフト",
                    "emoji": True,
                },
                "options": [],
            },
        },
        {
            "block_id": "select_date",
            "type": "section",
            "text": {"type": "mrkdwn", "text": "他の日のシフトを探しますか?\n日付をえらんでください"},
            "accessory": {
                "type": "datepicker",
                "action_id": "",
                "initial_date": dt.datetime.now().strftime("%Y-%m-%d"),
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select a date",
                    "emoji": True,
                },
            },
        },
        cancel_button,
    ],
}

show_shift = {
    "response_type": "ephemeral",
    "blocks": [
        {
            "type": "image",
            "title": {"type": "plain_text", "text": "Example Image", "emoji": True},
            "image_url": "",
            "alt_text": "Example Image",
        },
        {"type": "divider"},
        {
            "block_id": "show_shift",
            "type": "section",
            "text": {"type": "mrkdwn", "text": "シフトを表示する日を選んでください"},
            "accessory": {
                "type": "datepicker",
                "action_id": "",
                "initial_date": "",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select a date",
                    "emoji": True,
                },
            },
        },
        {
            "block_id": "switch_type",
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": "a",
                    "text": {
                        "type": "plain_text",
                        "text": "Switch day/week",
                        "emoji": True,
                    },
                    "value": "click_me_123",
                }
            ],
        },
    ],
}
