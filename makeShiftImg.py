import datetime
import json

from PIL import Image, ImageDraw, ImageFont


class makeShiftImg:

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

    @staticmethod
    def parseShiftJson(json_path):
        shiftFile = open(json_path, "r")
        shift_dict = json.load(shiftFile)
        return shift_dict

    @staticmethod
    def sortShiftByStartTime(shift):
        for weekday in shift:
            shift[weekday]["worker"] = sorted(
                shift[weekday]["worker"], key=lambda x: x["worktime"][0]["start"]
            )
        return shift

    def __init__(self, jsonFilePath, kanjiFontPath, fontPath=None):

        if fontPath is None:
            fontPath = kanjiFontPath

        self.shift = makeShiftImg.parseShiftJson(jsonFilePath)
        self.shift = makeShiftImg.sortShiftByStartTime(self.shift)
        divWidth = self.countNeedShiftRow()  # シフトを挿入する列数
        self.needRows = divWidth + 4  # 表の余白分を含めた列数
        self.font = ImageFont.truetype(str(fontPath), 25)
        self.smallFont = ImageFont.truetype(str(fontPath), 15)
        self.kanjiFont = ImageFont.truetype(str(kanjiFontPath), 25)
        self.width = int(makeShiftImg.FOR_WIDTH_RATIO * self.needRows)
        self.height = makeShiftImg.HEIGHT
        self.image = Image.new("RGB", (self.width, self.height), makeShiftImg.WHITE)
        self.drawObj = ImageDraw.Draw(self.image)
        # 罫線を引くためのプロパティ
        self.needColumns = 23  # 名前部分を除いた必要な列数
        self.heightOffset = self.height / 8  # 上部の名前の空間の高さ
        self.columnHeight = (
            self.height - self.heightOffset
        ) / self.needColumns  # 名前部分を以外の列の高さ
        self.rowWidth = self.width / self.needRows  # 1列の幅

    def countNeedShiftRow(self, selectedWeekday=None):
        countedRows = 0
        if selectedWeekday is None:
            for weekday in self.shift:
                countedRows += len(self.shift[weekday]["worker"])
            return countedRows
        else:
            return len(self.shift[selectedWeekday]["worker"])

    def countWorktime(self, worktime, columnCount=False):
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

    def calculateApexPointsFromWorktime(self, worktime, row):
        points = []
        worktimeColumn = self.countWorktime(worktime, columnCount=True)
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

    def writeTextVerticalBottom(self, coor, text, font=None):
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

    def printGrid(self, lineWeight=gridLineWeight, color=LIGHT_GRAY):
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

    def printWeekSeparateLine(self, font=None, lineWeight=boldLineWeight, color=BLACK):
        if font is None:
            font = self.kanjiFont

        tmpCountRow = 2  # 両サイド2列分開いてるからoffset
        weekdayList = ("月", "火", "水", "木", "金")
        self.drawObj.line(
            [(self.rowWidth * 2, 0), (self.rowWidth * 2, self.height)],
            (0, 0, 0),
            lineWeight,
        )
        for (weekday, loopCount) in zip(self.shift, range(len(self.shift))):
            weekdayLabelPoint = (
                self.rowWidth * (tmpCountRow + self.countNeedShiftRow(weekday) / 2)
                - font.getsize(weekdayList[loopCount])[0] / 2,
                (self.columnHeight - font.getsize(weekdayList[loopCount])[1]) / 2,
            )
            self.drawObj.text(weekdayLabelPoint, weekdayList[loopCount], color, font)
            tmpCountRow += self.countNeedShiftRow(weekday)
            self.drawObj.line(
                [
                    (self.rowWidth * (tmpCountRow), 0),
                    (self.rowWidth * (tmpCountRow), self.height),
                ],
                color,
                lineWeight,
            )

    def printWorkerNames(self, font=None):
        if font is None:
            font = self.kanjiFont

        nameBottomOfiiset = 20
        for (row, name) in enumerate(
            [
                worker["name"]
                for weekday in self.shift
                for worker in self.shift[weekday]["worker"]
            ]
        ):
            self.writeTextVerticalBottom(
                {
                    "x": self.rowWidth * (row + 2.5),
                    "y": self.columnHeight + self.heightOffset + nameBottomOfiiset,
                },
                name,
            )

    def printWorkTimerect(
        self, font=None, colorTable=SHIFTTIME_RECT_COLORS, textColor=BLACK
    ):
        if font is None:
            font = self.smallFont
        rowCounter = 0
        worktimePerDay = 0
        worktimeTextOffset = 3
        for weekday in self.shift:
            for worker in self.shift[weekday]["worker"]:
                for worktime in worker["worktime"]:
                    worktimePerDay += self.countWorktime(worktime)
                    rectApex = self.calculateApexPointsFromWorktime(
                        worktime, rowCounter
                    )
                    self.drawObj.polygon(
                        rectApex,
                        fill=colorTable[self.shift[weekday]["worker"].index(worker)],
                    )
                    if "代行依頼" in worktime:
                        requestTime = self.countWorktime(worktime["代行依頼"])
                        worktimePerDay -= requestTime
                        apex = self.calculateApexPointsFromWorktime(
                            worktime["代行依頼"], rowCounter
                        )
                        self.drawObj.polygon(apex, self.LIGHT_GRAY)

                else:
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
                    """
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
                    """
                    rowCounter += 1
                    worktimePerDay = 0

    def printTimeLabel(self, font=None):
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
        self.printWorkTimerect()
        self.printWorkerNames()
        self.printGrid()
        self.printWeekSeparateLine()
        self.printTimeLabel()
        return self.image


if __name__ == "__main__":
    make = makeShiftImg(
        "./shift.json",
        "/Users/yume_yu/Library/Fonts/Cica-Regular.ttf",
        "/Library/Fonts/Arial.ttf",
    )
    image = make.makeImage()
    image.show()
# image.save("./sample.jpg", quality=95)
