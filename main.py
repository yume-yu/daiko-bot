import datetime as dt
import json
import logging
import os
import sys
import threading
import time
from ast import literal_eval
from logging import StreamHandler
from pprint import pformat, pprint

import requests
# from chatmessage import start_chatmessage_process
from cuimessage import make_msg, ready_to_responce
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_httpauth import HTTPDigestAuth
from interactivemessages import csv_to_dict, get_block
from settings import *
from settings import ADD_TOKEN, header, sc
from shiftregistrationapi import parse_formdata

app = Flask(__name__)
app.config["SECRET_KEY"] = "qwertyuiop"
app.debug = True
# file_handler = StreamHandler()
app.logger.addHandler(StreamHandler())
auth = HTTPDigestAuth()

users = {"yume_yu": "password"}


@auth.get_password
def get_pw(username):
    if username in users:
        return users.get(username)
    return None


@app.route("/")
def show_entries():
    return "ok, wakeup!"
    # return str("hello, world")


@app.route("/get-users")
def get_users_dict():
    return jsonify(sc.sheet.get_slackId2name_dict())


@app.route("/reg-form")
@auth.login_required
def show_registry_page():
    name_dict = sc.sheet.get_slackId2name_dict()
    pprint(name_dict, stream=sys.stderr)
    return render_template(
        "regist.html", members=zip(name_dict.keys(), name_dict.values()), title="www"
    )


def validate_token(token: str):
    if token in [SLACK_VALID_TOKEN, ADD_TOKEN]:
        return True
    else:
        return False


# シフト一括追加API POSTでjsonを受け取る
@app.route("/add-once", methods=["POST"])
def add_shifts_at_once():
    parse_formdata(json.loads(request.data))

    return jsonify({"status": "ok"})


@app.route("/slack", methods=["POST"])
def api_for_slack():

    if request.data.decode():
        # request.dataがあるのはfrom Event API
        return event_api(json.loads(request.data.decode()))
    elif request.form.get("payload"):
        # request.form["payload"]があるのは interactive message
        return interactive_message(json.loads(request.form.get("payload")))
    elif request.form.get("command"):
        # request.form["command"]があるのは slash command
        return command(request.form)

    # 該当がなければ空を返す
    return ""


def command(data: dict):
    """

    slashコマンド呼び出しへの対応をする


    Args:
        data (dict): slackからのリクエストの内容

    Returns:
        str : slackからのリクエストに応じた応答文字列

    Note:
        * "/d"で呼び出されたときは空文字を返す。実際のレスポンスは別スレッドにて行う。
        * "/daiko"で呼び出されたときはメニューUIのjsonを返す。
    """

    # tokenの確認
    if not validate_token(data["token"]):
        return ""

    if data.get("command") == "/d":
        thread = threading.Thread(target=ready_to_responce, args=(data,))
        thread.start()

        return ""
    elif data.get("command") == "/daiko":
        return_dict = get_block("select_action", slack_id=data["user_id"])
        return jsonify(return_dict)

    return ""


def validate_requesttimes(responce_data: dict, state: dict) -> list:

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


def interactive_message(data: dict):
    """

    interactive message呼び出しへの対応をする


    Args:
        data (dict): slackからのリクエストの内容

    Returns:
        str : jsonify({"status":"ok"})

    """
    # def check_post():

    app.logger.warning(pformat(data))

    # tokenの確認
    if not validate_token(data["token"]):
        return ""

    return_block = None

    """
    palyload["type"]について
    * dialog_cancellation -> dialogから送信されたデータ
    * dialog_cancellation -> dialogがキャンセルされたことを知らせるデータ
    * block_actions -> block要素を含むメッセージが送出したデータ
    """
    if data["type"] == "dialog_submission":
        responce_data = data["submission"]
        state = csv_to_dict(data["state"])

        error_list = []
        if data["callback_id"] in ("Request", "Contract"):
            error_list = validate_requesttimes(responce_data, state)
        elif data["callback_id"] == "Addname":
            use_db.add(data["user"]["id"], responce_data["name"])
            return_block = get_block("select_action", value=responce_data["name"])
            res = requests.post(
                data["response_url"], json=json.loads(json.dumps(return_block))
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

        if data["callback_id"] == "Request":
            return_block = get_block(
                "request_dialog_ok", target=responce_data, value=new_value
            )
        elif data["callback_id"] == "Contract":
            return_block = get_block(
                "contract_dialog_ok", target=responce_data, value=new_value
            )

        res = requests.post(
            data["response_url"], json=json.loads(json.dumps(return_block))
        )
        print(res.text)
        return ""

    elif data["type"] == "dialog_cancellation":
        return_block = get_block("cancel")
        res = requests.post(
            data["response_url"], json=json.loads(json.dumps(return_block))
        )
        print(res.text)
        return jsonify({"status": "ok"})
    elif data["type"] == "block_actions":

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

        responce_action = data["actions"][0]

        if responce_action["block_id"] == "select_date":
            return_block = get_block(
                (
                    "to_request"
                    if literal_eval(responce_action["action_id"].title())
                    else "to_contract"
                ),
                date=responce_action["selected_date"],
                slack_id=data["user"]["id"],
            )
        elif responce_action["block_id"] == "select_shift":

            return_block = get_block(
                responce_action["block_id"],
                eventid=responce_action["selected_option"]["value"],
                value=responce_action["action_id"],
            )
            return_block["trigger_id"] = data["trigger_id"]

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
                slack_id=data["user"]["id"],
            )
            return_block = return_block
        elif responce_action["block_id"] in ("show_shift", "switch_type"):
            return_block = get_block(
                responce_action["block_id"],
                slack_id=data["user"]["id"],
                value=responce_action,
            )
        else:
            if "value" in responce_action.keys():
                selected_action = responce_action["value"]
                return_block = get_block(
                    selected_action,
                    slack_id=data["user"]["id"],
                    value=data.get("actions")[0],
                )

    if not return_block:
        return_block = get_block("error")

    res = requests.post(data["response_url"], json=json.loads(json.dumps(return_block)))
    return jsonify({"status": "ok"})


def event_api(data: dict):
    """

    Event APIからのデータを処理する呼び出しへの対応をする


    Args:
        data (dict): slackからのリクエストの内容

    Returns:
        str : 空文字

    """

    # 認証用の処理
    if data.get("challenge"):
        return data["challenge"]

    # tokenの確認
    if not validate_token(data["token"]):
        return ""

    # thread = Ready_to_responce(request.form)
    # thread = threading.Thread(target=start_chatmessage_process, args=(data,))
    # thread.start()

    return ""


@app.route("/shiftimg-test", methods=["GET", "POST"])
def img_test():
    print(request.form["user_id"])
    return_dict = get_block("select_action", slack_id=request.form["user_id"])
    return jsonify(return_dict)


if __name__ != "__main__":
    gunicorn_logger = logging.getLogger("gunicorn.log")
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

if __name__ == "__main__":

    def start_app():
        app.run(debug=True)

    start_app()
