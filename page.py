import ast
import datetime
import glob
import json
import os
import urllib.parse

from flask import Flask, jsonify, redirect, render_template, request, url_for
from workmanage import DrawShiftImg, Shift

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
# shift = Shift.parse_json("./shift.json")
shift = Shift.parse_json("./sample.json")


@app.route("/")
def root_page():
    global shift
    make = DrawShiftImg(shift, "/Users/yume_yu/Library/Fonts/Cica-Regular.ttf")
    image = make.makeImage()
    filename = (
        "shiftimage-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S%f") + ".jpg"
    )
    filepath = "./static/img/" + filename
    for file in glob.glob("./static/img/shiftimage-*.jpg", recursive=True):
        os.remove(file)
    image.save("./static/img/" + filename, quality=95)
    # return '<img src="./static/img/' + filename + '">'
    return render_template("index.html", imgpath=filepath)


@app.route("/add", methods=["GET"])
def add_shift_page():
    global shift
    if not (
        request.args.get("weekday")
        or request.args.get("name")
        or request.args.get("worktime")
    ):
        return redirect(url_for("root_page"))
    weekday = urllib.parse.unquote(request.args.get("weekday"))
    name = urllib.parse.unquote(request.args.get("name"))
    worktime = json.loads(urllib.parse.unquote(request.args.get("worktime")))
    shift.add(weekday, name, worktime)
    return redirect(url_for("root_page"))


@app.route("/_get_members", methods=["GET"])
def return_member():
    return jsonify(shift.get_member())


@app.route("/_get_of_member", methods=["GET", "POST"])
def return_shift_of_member():
    # return jsonify(
    if request.method == "GET":
        return str(
            shift.get_shift_of_member(urllib.parse.unquote(request.args.get("name")))
        )
    # )
    elif request.method == "POST":
        if request.json is not None:
            item = shift.get_shift_of_member(urllib.parse.unquote(request.json["name"]))
            print(item)
            return jsonify(item)
        else:
            item = shift.get_shift_of_member(urllib.parse.unquote(request.form["name"]))
            print(type(item))
            return item
    else:
        return "wrong"


@app.route("/_get_week", methods=["GET"])
def return_json():
    return jsonify(ast.literal_eval(str(shift)))  # 文字列→dict→jsonに変換して返す


app.run(debug=True, host="0.0.0.0")
