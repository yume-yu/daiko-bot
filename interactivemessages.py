import copy
import datetime as dt
from ast import literal_eval
from pprint import pprint

from settings import *
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
        if literal_eval(value.title()):
            return make_reqest_dialog(eventid)
        else:
            return make_contract_dialog(eventid)
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
    elif action_value == "show_shift":
        return get_shift_image(slack_id)
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

    # テンプレートをコピーして文言準備
    # 依頼か請負かでの文言変更
    made_block = copy.deepcopy(select_nearly)
    # 代行依頼のとき
    if request:
        made_block["blocks"][0] = {
            "type": "section",
            "block_id": "select_shift",
            "text": {"type": "mrkdwn", "text": "代行依頼を出すシフトを選んでください"},
            "accessory": {
                "type": "static_select",
                "action_id": str(request),
                "placeholder": {
                    "type": "plain_text",
                    "text": "この週のあなたのシフト",
                    "emoji": True,
                },
                "options": [],
            },
        }
    # 代行請負のとき
    else:
        made_block["blocks"][0] = {
            "type": "section",
            "block_id": "select_shift",
            "text": {"type": "mrkdwn", "text": "代行依頼を受けるシフトを選んでください"},
            "accessory": {
                "type": "static_select",
                "action_id": str(request),
                "placeholder": {
                    "type": "plain_text",
                    "text": "この週の代行依頼",
                    "emoji": True,
                },
                "options": [],
            },
        }

    # いずれかの状態のシフト一覧を取得
    shift_list = []
    if request:
        shift_list = sc.get_parsonal_shift(slack_id, date)
    else:
        shift_list = sc.get_requested_shift(date)

    # シフト一覧部分のオブジェクトをつくる
    for works in shift_list:
        name = ""
        # 依頼済みリストのときは名前を表示するため名前を取得
        if not request:
            name = "{} ".format(works.name)
        for worktime in works.worktime:
            if worktime.requested == (not request):
                date = worktime.start.strftime("%m/%d")
                weekday = Shift.WORKDAYS_JP[worktime.start.weekday()]
                starttime = worktime.start.strftime("%H:%M")
                endtime = worktime.end.strftime("%H:%M")
                shift_block = {
                    "text": {
                        "type": "plain_text",
                        "text": "{date}({weekday}) {name}{start}~{end}".format(
                            name=name,
                            date=date,
                            weekday=weekday,
                            start=starttime,
                            end=endtime,
                        ),
                        "emoji": True,
                    },
                    "value": worktime.eventid,
                }
                print(made_block["blocks"][0]["accessory"])
                made_block["blocks"][0]["accessory"]["options"].append(shift_block)

    # リストにするシフトがなかったときはない旨を書く
    if not made_block["blocks"][0]["accessory"]["options"]:
        if request:
            made_block["blocks"][0] = {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "この週にはあなたのシフトはないようです"},
            }
        else:
            made_block["blocks"][0] = {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "この週には代行依頼はないようです"},
            }

    # このリストが依頼か代行かをflagでaction_idに記録
    made_block["blocks"][1]["accessory"]["action_id"] = str(request)

    return made_block


def make_reqest_dialog(eventid):
    """
    代行を依頼するためのフォームをつくる

    :param str eventid : 代行依頼を出すシフトのeventid
    """
    return_block = copy.deepcopy(request_dialog)
    target = sc.get_shift_by_id(eventid)
    date = target.worktime[0].start.strftime("%m/%d")
    start = target.worktime[0].start.strftime("%H:%M")
    end = target.worktime[0].end.strftime("%H:%M")
    return_block["dialog"]["state"] = (
        "eventid," + eventid + ",start," + start + ",end," + end + ",date," + date
    )
    return_block["dialog"]["elements"][0]["value"] = start
    return_block["dialog"]["elements"][1]["value"] = end
    return_block["dialog"]["elements"][0]["label"] = "開始時間 - {}~".format(start)
    return_block["dialog"]["elements"][1]["label"] = "終了時間 - ~{}".format(end)
    return return_block


def make_contract_dialog(eventid):
    """
    代行を請け負うためのフォームをつくる

    :param str eventid : 代行依頼を出すシフトのeventid
    """
    return_block = copy.deepcopy(contract_dialog)
    target = sc.get_shift_by_id(eventid)
    date = target.worktime[0].start.strftime("%m/%d")
    start = target.worktime[0].start.strftime("%H:%M")
    end = target.worktime[0].end.strftime("%H:%M")
    return_block["dialog"]["state"] = (
        "eventid," + eventid + ",start," + start + ",end," + end + ",date," + date
    )
    return_block["dialog"]["elements"][0]["value"] = start
    return_block["dialog"]["elements"][1]["value"] = end
    return_block["dialog"]["elements"][0]["label"] = "開始時間 - {}~".format(start)
    return_block["dialog"]["elements"][1]["label"] = "終了時間 - ~{}".format(end)
    print(return_block)
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


def request_shift(target: dict, slackId: str) -> dict:
    if not target:
        return error_message
    pprint(target)
    sc.request(target["eventid"], target["start"], target["end"])
    sc.post_message(
        sc.make_notice_message(
            slackId,
            sc.Actions.REQUEST,
            sc.get_shift_by_id(target["eventid"]),
            target["start"],
            target["end"],
            target["comment"],
        )
    )
    sc.record_use(slackId, sc.UseWay.BUTTONS, sc.Actions.REQUEST)
    return complate_request


def contract_shift(target: dict, slackId: str) -> dict:
    if not target:
        return error_message

    sc.contract(target["eventid"], slackId, target["start"], target["end"])
    sc.post_message(
        sc.make_notice_message(
            slackId,
            sc.Actions.CONTRACT,
            sc.get_shift_by_id(target["eventid"]),
            target["start"],
            target["end"],
            target["comment"],
        )
    )
    sc.record_use(slackId, sc.UseWay.BUTTONS, sc.Actions.CONTRACT)
    return complate_request


def get_shift_image(slackId):
    """
    シフト画像を生成,アップロードして画像を表示するメッセージを返す

    :param str slackId : 呼び出したユーザーのslackId
    """
    return_block = copy.deepcopy(show_shift)
    sc.init_shift()
    uploaded_file = sc.generate_shiftimg_url()
    return_block["blocks"][0]["image_url"] = "{}".format(uploaded_file["url"])
    return_block["blocks"][0]["title"]["text"] = "{}".format(uploaded_file["filename"])
    sc.record_use(slackId, sc.UseWay.BUTTONS, sc.Actions.SHOWSHIFT)
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
                    "text": "この週のあなたのシフト",
                    "emoji": True,
                },
                "options": [],
            },
        },
        {
            "block_id": "select_date",
            "type": "section",
            "text": {"type": "mrkdwn", "text": "他の週のシフトを探しますか?\nシフトのある週の日付を1つえらんでください"},
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
        }
    ],
}
