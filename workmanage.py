import datetime
import json

from PIL import Image, ImageDraw, ImageFont


class Shift:
    WORKDAYS = ("mon", "tue", "wed", "thu", "fri")

    @staticmethod
    def parse_json(json_path):
        shiftFile = open(json_path, "r")
        shift_dict = json.load(shiftFile)
        return shift_dict

    @staticmethod
    def count_worktime(worktime, columnCount=False):
        startTime = {
            "hour": int(worktime["start"].split(":")[0]),
            "minute": int(worktime["start"].split(":")[1]),
        }
        endTime = {
            "hour": int(worktime["end"].split(":")[0]),
            "minute": int(worktime["end"].split(":")[1]),
        }
        worktimeLangth = (endTime["hour"] - startTime["hour"]) + (
            ((endTime["minute"] - startTime["minute"]) / 60)
        )
        if columnCount:
            startColumn = (startTime["hour"] - 8) * 2 + (startTime["minute"] / 30)
            return {"startColumn": startColumn, "columns": worktimeLangth * 2}
        else:
            return worktimeLangth

    @staticmethod
    def exchange_weekdayname(weekday):
        if weekday in (Shift.WORKDAYS[0], "月", "げつ", "Monday", "Mon"):
            return Shift.WORKDAYS[0]
        elif weekday in (Shift.WORKDAYS[1], "火", "か", "Tuesday", "Tue"):
            return Shift.WORKDAYS[1]
        elif weekday in (Shift.WORKDAYS[2], "水", "すい", "Wednesday", "Wed"):
            return Shift.WORKDAYS[2]
        elif weekday in (Shift.WORKDAYS[3], "木", "もく", "Thursday", "Thu"):
            return Shift.WORKDAYS[3]
        elif weekday in (Shift.WORKDAYS[4], "金", "きん", "Friday", "Fri"):
            return Shift.WORKDAYS[4]
        raise ValueError("invaild weekday text")

    def __init__(self, path):
        self.shift = Shift.parse_json(path)
        self.sort_by_starttime()

    def sort_by_starttime(self):
        for weekday in self.shift:
            for worker in self.shift[weekday]["worker"]:
                # worker["worktime"] =
                worker["worktime"] = sorted(
                    worker["worktime"], key=lambda x: x["start"]
                )
            self.shift[weekday]["worker"] = sorted(
                self.shift[weekday]["worker"],
                key=lambda x: (x["worktime"][0]["start"], x["worktime"][0]["end"]),
            )

    def add(self, weekday, name, worktime):
        weekday = Shift.exchange_weekdayname(weekday)
        for worker in self.shift[weekday]["worker"]:
            if worker["name"] == name:
                worker["worktime"].append(worktime)
                break
        else:
            newWorker = {"name": name, "worktime": [worktime]}
            self.shift[weekday]["worker"].append(newWorker)

        self.sort_by_starttime()

    def delete(self, weekday, name, index=1):
        weekday = Shift.exchange_weekdayname(weekday)
        for worker in self.shift[weekday]["worker"]:
            if worker["name"] == name:
                del worker["worktime"][index - 1]
                if not worker["worktime"]:
                    self.shift[weekday]["worker"].remove(worker)
        self.sort_by_starttime()

    def update(self, weekday, name, worktime, index=1):
        weekday = Shift.exchange_weekdayname(weekday)
        for worker in self.shift[weekday]["worker"]:
            if worker["name"] == name:
                worker["worktime"][index - 1]["start"] = worktime["start"]
                worker["worktime"][index - 1]["end"] = worktime["end"]
        self.sort_by_starttime()

    def add_request(self, weekday, name, index=1, requestedtime=None):
        weekday = Shift.exchange_weekdayname(weekday)
        for worker in self.shift[weekday]["worker"]:
            if worker["name"] == name:
                worker["worktime"][index - 1]["requested"] = {
                    "start": (
                        worker["worktime"][index - 1]["start"]
                        if requestedtime is None
                        else requestedtime["start"]
                    ),
                    "end": (
                        worker["worktime"][index - 1]["end"]
                        if requestedtime is None
                        else requestedtime["end"]
                    ),
                }
                break

    def delete_request(self, weekday, name, index=1):
        weekday = Shift.exchange_weekdayname(weekday)
        for worker in self.shift[weekday]["worker"]:
            if worker["name"] == name:
                print(worker)
                if "requested" in worker["worktime"][index - 1]:
                    print("delete!")
                    del worker["worktime"][index - 1]["requested"]
                    break

    def export(self, path: str):
        exportfile = open(path, "w")
        json.dump(self.shift, exportfile, indent=2, ensure_ascii=False)


class DrawShiftImg:

    FOR_WIDTH_RATIO = 1624 / 38
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    LIGHT_GRAY = (125, 125, 125)
    SHIFTTIME_RECT_COLORS = (
        (216, 126, 107),
        (236, 153, 153),
        (249, 203, 156),
        (255, 230, 154),
        (182, 215, 168),
        (162, 196, 201),
        (162, 196, 201),
        (162, 196, 201),
        (213, 166, 189),
    )
    HEIGHT = 1026

    gridLineWeight = 1
    boldLineWeight = 3

    def __init__(self, shift, kanjiFontPath, fontPath=None):
        if fontPath is None:
            fontPath = kanjiFontPath

        self.shift = shift
        divWidth = self.count_need_row()  # シフトを挿入する列数
        self.needRows = divWidth + 4  # 表の余白分を含めた列数
        self.font = ImageFont.truetype(str(fontPath), 25)
        self.smallFont = ImageFont.truetype(str(fontPath), 15)
        self.kanjiFont = ImageFont.truetype(str(kanjiFontPath), 25)
        self.width = int(DrawShiftImg.FOR_WIDTH_RATIO * self.needRows)
        self.height = DrawShiftImg.HEIGHT
        self.image = Image.new("RGB", (self.width, self.height), DrawShiftImg.WHITE)
        self.drawObj = ImageDraw.Draw(self.image)
        # 罫線を引くためのプロパティ
        self.needColumns = 23  # 名前部分を除いた必要な列数
        self.heightOffset = self.height / 8  # 上部の名前の空間の高さ
        self.columnHeight = (
            self.height - self.heightOffset
        ) / self.needColumns  # 名前部分を以外の列の高さ
        self.rowWidth = self.width / self.needRows  # 1列の幅

    def update(self, newshift=None):
        if newshift is not None:
            self.shift = newshift
        divWidth = self.count_need_row()  # シフトを挿入する列数
        self.needRows = divWidth + 4  # 表の余白分を含めた列数
        self.width = int(DrawShiftImg.FOR_WIDTH_RATIO * self.needRows)
        self.height = DrawShiftImg.HEIGHT
        self.image = Image.new("RGB", (self.width, self.height), DrawShiftImg.WHITE)
        self.drawObj = ImageDraw.Draw(self.image)
        # 罫線を引くためのプロパティ
        self.needColumns = 23  # 名前部分を除いた必要な列数
        self.heightOffset = self.height / 8  # 上部の名前の空間の高さ
        self.columnHeight = (
            self.height - self.heightOffset
        ) / self.needColumns  # 名前部分を以外の列の高さ
        self.rowWidth = self.width / self.needRows  # 1列の幅

    def count_need_row(self, selectedWeekday=None):
        countedRows = 0
        if selectedWeekday is None:
            for weekday in self.shift.shift:
                countedRows += len(self.shift.shift[weekday]["worker"])
            return countedRows
        else:
            return len(self.shift.shift[selectedWeekday]["worker"])

    def calc_rect_apices(self, worktime, row):
        points = []
        worktimeColumn = Shift.count_worktime(worktime, columnCount=True)
        points.append(
            (
                self.rowWidth * (2 + row),
                self.heightOffset + self.columnHeight * worktimeColumn["startColumn"],
            )
        )
        points.append(
            (
                self.rowWidth * (2 + row + 1),
                self.heightOffset + self.columnHeight * worktimeColumn["startColumn"],
            )
        )
        points.append(
            (
                self.rowWidth * (2 + row + 1),
                self.heightOffset
                + self.columnHeight
                * (worktimeColumn["startColumn"] + worktimeColumn["columns"]),
            )
        )
        points.append(
            (
                self.rowWidth * (2 + row),
                self.heightOffset
                + self.columnHeight
                * (worktimeColumn["startColumn"] + worktimeColumn["columns"]),
            )
        )
        return points

    def write_text_ttb(self, coor, text, font=None):
        if font is None:
            font = self.kanjiFont
        reversedList = list(reversed(text))
        printPosition = {"x": coor["x"], "y": coor["y"]}
        for character in range(len(reversedList)):
            printPosition["x"] = (
                coor["x"] - font.getsize(str(reversedList[character]))[0] / 2
            )
            printPosition["y"] = (
                printPosition["y"] - font.getsize(str(reversedList[character]))[1]
            )
            self.drawObj.text(
                [(printPosition["x"]), (printPosition["y"])],
                str(reversedList[character]),
                (0, 0, 0),
                font=font,
            )

    def print_grid(self, lineWeight=gridLineWeight, color=LIGHT_GRAY):
        # 縦線の描画
        for row in range(2, self.needRows - 1):
            self.drawObj.line(
                [
                    (self.rowWidth * row, self.columnHeight),
                    (self.rowWidth * row, self.height - self.columnHeight),
                ],
                color,
                lineWeight,
            )
        # 罫線の描画
        self.drawObj.line(
            [
                (self.rowWidth * 2, self.columnHeight),
                (self.rowWidth * (self.needRows - 2), self.columnHeight),
            ],
            color,
            lineWeight,
        )
        for column in range(2, self.needColumns):
            self.drawObj.line(
                [
                    (self.rowWidth * 2, self.heightOffset + self.columnHeight * column),
                    (
                        self.rowWidth * (self.needRows - 2),
                        self.heightOffset + self.columnHeight * column,
                    ),
                ],
                color,
                lineWeight,
            )

    def print_weekseparateline(self, font=None, lineWeight=boldLineWeight, color=BLACK):
        if font is None:
            font = self.kanjiFont

        tmpCountRow = 2  # 両サイド2列分開いてるからoffset
        weekdayList = ("月", "火", "水", "木", "金")
        self.drawObj.line(
            [(self.rowWidth * 2, 0), (self.rowWidth * 2, self.height)],
            (0, 0, 0),
            lineWeight,
        )
        for (weekday, loopCount) in zip(self.shift.shift, range(len(self.shift.shift))):
            weekdayLabelPoint = (
                self.rowWidth * (tmpCountRow + self.count_need_row(weekday) / 2)
                - font.getsize(weekdayList[loopCount])[0] / 2,
                (self.columnHeight - font.getsize(weekdayList[loopCount])[1]) / 2,
            )
            self.drawObj.text(weekdayLabelPoint, weekdayList[loopCount], color, font)
            tmpCountRow += self.count_need_row(weekday)
            self.drawObj.line(
                [
                    (self.rowWidth * (tmpCountRow), 0),
                    (self.rowWidth * (tmpCountRow), self.height),
                ],
                color,
                lineWeight,
            )

    def print_names(self, font=None):
        if font is None:
            font = self.kanjiFont

        nameBottomOfiiset = 20
        for (row, name) in enumerate(
            [
                worker["name"]
                for weekday in self.shift.shift
                for worker in self.shift.shift[weekday]["worker"]
            ]
        ):
            self.write_text_ttb(
                {
                    "x": self.rowWidth * (row + 2.5),
                    "y": self.columnHeight + self.heightOffset + nameBottomOfiiset,
                },
                name,
            )

    def print_worktimerect(
        self,
        font=None,
        colorTable=SHIFTTIME_RECT_COLORS,
        textColor=BLACK,
        timepos="None",
    ):
        if font is None:
            font = self.smallFont
        rowCounter = 0
        worktimePerDay = 0
        worktimeTextOffset = 3
        for weekday in self.shift.shift:
            for worker in self.shift.shift[weekday]["worker"]:
                for worktime in worker["worktime"]:
                    worktimePerDay += Shift.count_worktime(worktime)
                    rectApex = self.calc_rect_apices(worktime, rowCounter)
                    self.drawObj.polygon(
                        rectApex,
                        fill=colorTable[
                            self.shift.shift[weekday]["worker"].index(worker)
                        ],
                    )
                    if "requested" in worktime:
                        requestTime = Shift.count_worktime(worktime["requested"])
                        worktimePerDay -= requestTime
                        apex = self.calc_rect_apices(worktime["requested"], rowCounter)
                        self.drawObj.polygon(apex, self.LIGHT_GRAY)

                else:
                    if timepos == "rect":
                        # 最後の勤務の矩形の下に総勤務時間
                        self.drawObj.text(
                            (
                                rectApex[2][0]
                                - font.getsize(str(worktimePerDay))[0]
                                - worktimeTextOffset,
                                rectApex[2][1],
                            ),
                            str(worktimePerDay),
                            textColor,
                            font,
                        )
                    elif timepos == "name":
                        # 名前の右下に総勤務時間
                        self.drawObj.text(
                            (
                                rectApex[2][0]
                                - font.getsize(str(worktimePerDay))[0]
                                - worktimeTextOffset,
                                2 * self.columnHeight
                                + self.heightOffset
                                - font.getsize(str(worktimePerDay))[1]
                                - worktimeTextOffset,
                            ),
                            str(worktimePerDay),
                            textColor,
                            font,
                        )
                    elif timepos == "bottom":
                        # 一番下の行に総勤務時間
                        self.drawObj.text(
                            (
                                rectApex[2][0]
                                - font.getsize(str(worktimePerDay))[0]
                                - worktimeTextOffset,
                                self.heightOffset
                                + self.columnHeight * 22,  # self.needColumns
                            ),
                            str(worktimePerDay),
                            textColor,
                            font,
                        )
                    rowCounter += 1
                    worktimePerDay = 0

    def print_time(self, font=None):
        if font is None:
            font = self.font

        timeToPrint = datetime.datetime(2000, 1, 1, 9, 0)
        timesOffset = 10
        for column in range(self.needColumns - 2):
            printPosition = {
                "right": (
                    (
                        self.rowWidth * 2
                        - font.getsize(timeToPrint.strftime("%H:%M"))[0]
                        - timesOffset
                    ),
                    (
                        self.heightOffset
                        + self.columnHeight * (column + 2)
                        - font.getsize(timeToPrint.strftime("%H:%M"))[1] / 2
                    ),
                ),
                "left": (
                    (self.rowWidth * (self.needRows - 2) + timesOffset),
                    (
                        self.heightOffset
                        + self.columnHeight * (column + 2)
                        - font.getsize(timeToPrint.strftime("%H:%M"))[1] / 2
                    ),
                ),
            }

            self.drawObj.text(
                printPosition["right"],
                str(timeToPrint.strftime("%H:%M")),
                (0, 0, 0),
                font,
            )
            self.drawObj.text(
                printPosition["left"],
                str(timeToPrint.strftime("%H:%M")),
                (0, 0, 0),
                font,
            )
            timeToPrint += datetime.timedelta(minutes=30)

    def makeImage(self):
        self.print_worktimerect()
        self.print_names()
        self.print_grid()
        self.print_weekseparateline()
        self.print_time()
        return self.image


if __name__ == "__main__":
    shift = Shift("./shift.json")
    make = DrawShiftImg(
        shift,
        "/Users/yume_yu/Library/Fonts/Cica-Regular.ttf",
        "/Library/Fonts/Arial.ttf",
    )
    make.shift.add_request("月", "松田", requestedtime={"start": "13:00", "end": "16:00"})
    make.shift.delete_request("月", "松田")
    make.update()
    image = make.makeImage()
    image.show()
    make.shift.export("./export.json")
    shift = Shift("./export.json")
    make = DrawShiftImg(
        shift,
        "/Users/yume_yu/Library/Fonts/Cica-Regular.ttf",
        "/Library/Fonts/Arial.ttf",
    )
    image = make.makeImage()
    image.show()

# image.save("./sample.jpg", quality=95)
