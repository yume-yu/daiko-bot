import datetime as dt
import json
import os
import threading
import time
from ast import literal_eval

import requests
from flask import Flask, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_VALID_TOKEN = os.environ["SLACK_VALID_TOKEN"]
ADD_TOKEN = os.environ["ADD_TOKEN"]
header = {
    "Content-type": "application/json",
    "Authorization": "Bearer " + SLACK_BOT_TOKEN,
}


@app.route("/")
def show_entries():
    return render_template("index.html", imgpath="./static/img/sample.jpg")
    # return str("hello, world")


@app.route("/cmd", methods=["GET", "POST"])
def command():
    from cuimessage import make_msg, ready_to_responce

    # print(request.form)

    # tokenの確認
    if not validate_token(request.form["token"]):
        return ""

    # thread = Ready_to_responce(request.form)
    thread = threading.Thread(target=ready_to_responce, args=(request.form,))
    thread.start()

    return ""


def validate_token(token: str):
    if token in [SLACK_VALID_TOKEN, ADD_TOKEN]:
        return True
    else:
        return False


def validate_request(responce_data: dict, state: dict) -> list:

    base_start = dt.datetime.strptime(str(state["start"]), "%H:%M")
    base_end = dt.datetime.strptime(str(state["end"]), "%H:%M")

    error_list = []
    request_start = None
    request_end = None

    # 開始時間のvalidate
    try:
        request_start = dt.datetime.strptime(responce_data["start_time"], "%H:%M")
        if request_start < base_start:
            error_list.append({"name": "start_time", "error": "開始時間が本来のそれより前です"})
    except ValueError:
        error_list.append({"name": "start_time", "error": "時間の形式が間違っています"})

    # 終了時間のvalidate
    try:
        request_end = dt.datetime.strptime(responce_data["end_time"], "%H:%M")
        if base_end < request_end:
            error_list.append({"name": "end_time", "error": "終了時間が本来のそれより後です"})
    except ValueError:
        error_list.append({"name": "end_time", "error": "時間の形式が間違っています"})

    try:
        if (request_start.strftime("%H:%M") != base_start.strftime("%H:%M")) and (
            request_end.strftime("%H:%M") != base_end.strftime("%H:%M")
        ):
            error_list.append({"name": "start_time", "error": "時間の範囲が不適切です"})
            error_list.append({"name": "end_time", "error": "時間の範囲が不適切です"})
        elif (request_start > base_end) or (request_end < base_start):
            error_list.append({"name": "start_time", "error": "時間の範囲が不適切です"})
            error_list.append({"name": "end_time", "error": "時間の範囲が不適切です"})
    except AttributeError:
        # datetimeにパースできなかったとき
        pass

    return error_list


def validate_contract(responce_data: dict, state: dict) -> list:

    base_start = dt.datetime.strptime(str(state["start"]), "%H:%M")
    base_end = dt.datetime.strptime(str(state["end"]), "%H:%M")

    error_list = []
    contract_start = None
    contract_end = None

    # 開始時間のvalidate
    try:
        contract_start = dt.datetime.strptime(responce_data["start_time"], "%H:%M")
        if contract_start < base_start:
            error_list.append({"name": "start_time", "error": "開始時間が本来のそれより前です"})
    except ValueError:
        error_list.append({"name": "start_time", "error": "時間の形式が間違っています"})

    # 終了時間のvalidate
    try:
        contract_end = dt.datetime.strptime(responce_data["end_time"], "%H:%M")
        if base_end < contract_end:
            error_list.append({"name": "end_time", "error": "終了時間が本来のそれより後です"})
    except ValueError:
        error_list.append({"name": "end_time", "error": "時間の形式が間違っています"})

    try:
        if (contract_start > base_end) or (contract_end < base_start):
            error_list.append({"name": "start_time", "error": "時間の範囲が不適切です"})
            error_list.append({"name": "end_time", "error": "時間の範囲が不適切です"})
    except AttributeError:
        # datetimeにパースできなかったとき
        pass
    return error_list


@app.route("/interactive", methods=["GET", "POST"])
def check_post():
    from interactivemessages import csv_to_dict, get_block

    get_json = json.loads(request.form["payload"])
    print(json.loads(request.form["payload"]))

    # tokenの確認
    if not validate_token(get_json["token"]):
        return ""

    return_block = None

    """
    palyload["type"]について
    * dialog_cancellation   ->  dialogから送信されたデータ
    * dialog_cancellation   ->  dialogがキャンセルされたことを知らせるデータ
    * block_actions         ->  block要素を含むメッセージが送出したデータ
    """
    if get_json["type"] == "dialog_submission":
        responce_data = get_json["submission"]
        state = csv_to_dict(get_json["state"])

        error_list = []
        if get_json["callback_id"] == "Request":
            error_list = validate_request(responce_data, state)
        elif get_json["callback_id"] == "Contract":
            error_list = validate_contract(responce_data, state)
        elif get_json["callback_id"] == "Addname":
            use_db.add(get_json["user"]["id"], responce_data["name"])
            return_block = get_block("select_action", value=responce_data["name"])
            res = requests.post(
                get_json["response_url"], json=json.loads(json.dumps(return_block))
            )
            print(res.text)
            return ""

        if error_list:
            vaildate_error = {"errors": error_list}
            print(vaildate_error)
            return jsonify({"errors": error_list})

        new_value = "eventid,{},start,{},end,{},date,{},comment,{}".format(
            state["eventid"],
            responce_data["start_time"],
            responce_data["end_time"],
            state["date"],
            responce_data["comment"],
        )
        responce_data["date"] = state["date"]

        if get_json["callback_id"] == "Request":
            return_block = get_block(
                "request_dialog_ok", target=responce_data, value=new_value
            )
        elif get_json["callback_id"] == "Contract":
            return_block = get_block(
                "contract_dialog_ok", target=responce_data, value=new_value
            )

        res = requests.post(
            get_json["response_url"], json=json.loads(json.dumps(return_block))
        )
        print(res.text)
        return ""

    elif get_json["type"] == "dialog_cancellation":
        return_block = get_block("cancel")
        res = requests.post(
            get_json["response_url"], json=json.loads(json.dumps(return_block))
        )
        print(res.text)
        return jsonify({"status": "ok"})
    elif get_json["type"] == "block_actions":

        # block_actionsへの返答には一旦考え中メッセージを返す
        loading_message = {
            "response_type": "ephemeral",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "now thinking... :thinking_face: ",
                    },
                }
            ],
        }
        res = requests.post(
            json.loads(request.form["payload"])["response_url"],
            json=json.loads(json.dumps(loading_message)),
        )

        responce_action = get_json["actions"][0]

        if responce_action["block_id"] == "select_date":
            return_block = get_block(
                (
                    "to_request"
                    if literal_eval(responce_action["action_id"].title())
                    else "to_contract"
                ),
                date=responce_action["selected_date"],
                slack_id=get_json["user"]["id"],
            )
        elif responce_action["block_id"] == "select_shift":

            return_block = get_block(
                responce_action["block_id"],
                eventid=responce_action["selected_option"]["value"],
                value=responce_action["action_id"],
            )
            return_block["trigger_id"] = get_json["trigger_id"]

            res = requests.post(
                "https://slack.com/api/dialog.open",
                json=json.loads(json.dumps(return_block)),
                headers=header,
            )
            print(res.text)
        elif responce_action["block_id"] in ["confirm_request", "confirm_contract"]:
            return_block = get_block(
                responce_action["block_id"],
                value=csv_to_dict(responce_action["value"])
                if responce_action["value"] != "cancel"
                else None,
                slack_id=get_json["user"]["id"],
            )
            return_block = return_block
        elif responce_action["block_id"] == "show_shift":
            return_block = get_block(
                responce_action["block_id"], slack_id=get_json["user"]["id"]
            )
        else:
            if "value" in responce_action.keys():
                selected_action = responce_action["value"]
                return_block = get_block(
                    selected_action, slack_id=get_json["user"]["id"]
                )

    if not return_block:
        return_block = get_block("error")

    res = requests.post(
        get_json["response_url"], json=json.loads(json.dumps(return_block))
    )
    print(res.text)
    return jsonify({"status": "ok"})


@app.route("/daiko", methods=["GET", "POST"])
def getPost():
    from interactivemessages import csv_to_dict, get_block

    slack_token = request.form["token"]
    # tokenの確認
    if not validate_token(slack_token):
        # 無効なトークンだった場合はなにもさせない
        return ""
    print(request.form["user_id"])
    return_dict = get_block("select_action", slack_id=request.form["user_id"])
    return jsonify(return_dict)


@app.route("/event", methods=["GET", "POST"])
def for_eventapi():
    from chatmessage import start_chatmessage_process

    message_data = json.loads(request.data.decode())

    # 認証用の処理
    if message_data.get("challenge"):
        return message_data["challenge"]

    # tokenの確認
    if not validate_token(message_data["token"]):
        return ""

    # thread = Ready_to_responce(request.form)
    thread = threading.Thread(target=start_chatmessage_process, args=(message_data,))
    thread.start()

    return ""


@app.route("/shiftimg-test", methods=["GET", "POST"])
def img_test():
    print(request.form["user_id"])
    return_dict = get_block("select_action", slack_id=request.form["user_id"])
    return jsonify(return_dict)


if __name__ == "__main__":
    from memory_profiler import profile

    @profile
    def start_app():
        app.run(debug=True)

    @profile
    def check():
        print("check")

    start_app()
