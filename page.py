import datetime
import glob
import json
import os
import urllib.parse

from flask import Flask, render_template, request

from workmanage import DrawShiftImg, Shift

app = Flask(__name__)
shift = Shift("./shift.json")


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
        return "Error"
    weekday = urllib.parse.unquote(request.args.get("weekday"))
    name = urllib.parse.unquote(request.args.get("name"))
    worktime = json.loads(urllib.parse.unquote(request.args.get("worktime")))
    print(weekday, name, worktime)
    shift.add(weekday, name, worktime)
    return "status :Ok"


app.run(debug=True)
