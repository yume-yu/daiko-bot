# coding: utf-8
import os

# botアカウントのトークンを指定
API_TOKEN = os.environ["SLACK_BOT_TOKEN"]

# このbot宛のメッセージで、どの応答にも当てはまらない場合の応答文字列
DEFAULT_REPLY = "こんにちは!"

# プラグインスクリプトを置いてあるサブディレクトリ名のリスト
PLUGINS = ["mybot.plugins"]
