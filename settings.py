import os

from janome.analyzer import Analyzer
from janome.charfilter import *
from janome.tokenfilter import *
from janome.tokenizer import Tokenizer

import make_dict
import shiftcontroller
from connectgoogle import TIMEZONE

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_VALID_TOKEN = os.environ["SLACK_VALID_TOKEN"]
ADD_TOKEN = os.environ["ADD_TOKEN"]
header = {
    "Content-type": "application/json",
    "Authorization": "Bearer " + SLACK_BOT_TOKEN,
}

while True:
    try:
        TOKENIZER = Tokenizer("daiko-dict.csv", udic_type="simpledic", udic_enc="utf8")
    except:
        pass
    else:
        break

CHAR_FILTERS = [
    RegexReplaceCharFilter(u"：", u":"),
    RegexReplaceCharFilter(u"[\(\)]", u""),
    RegexReplaceCharFilter(u"十[^一二三四五六七八九]", u"10"),
    RegexReplaceCharFilter(u"十", u"1"),
    RegexReplaceCharFilter(u"九", u"9"),
    RegexReplaceCharFilter(u"八", u"8"),
    RegexReplaceCharFilter(u"七", u"7"),
    RegexReplaceCharFilter(u"六", u"6"),
    RegexReplaceCharFilter(u"五", u"5"),
    RegexReplaceCharFilter(u"四", u"4"),
    RegexReplaceCharFilter(u"三", u"3"),
    RegexReplaceCharFilter(u"二", u"2"),
    RegexReplaceCharFilter(u"一", u"1"),
]
TOKEN_FILTERS = [POSKeepFilter(["日付", "日付-日", "時刻", "トリガー", "キーワード", "名詞,数"])]

TEMP_CONVERSATION_SHEET = "temp-conversation"
IM_OPEN = "https://slack.com/api/im.open"
analyzer = Analyzer(
    char_filters=CHAR_FILTERS, tokenizer=TOKENIZER, token_filters=TOKEN_FILTERS
)

sc = shiftcontroller.ShiftController()
TIMEZONE = TIMEZONE
