import datetime
import json

from PIL import Image, ImageDraw, ImageFont


class Worktime:
    def _str__(self):
        return_str = f"start:{0} end:{1} requested:{2}".format(
            self.start, self.end, self.requested
        )
        return return_str

    def __repr__(self):
        obj_dict = {
            "start": self.start.strftime("%H:%M"),
            "end": self.end.strftime("%H:%M"),
            "requested": self.requested,
        }
        return str(obj_dict)

    def __init__(self, start, end):
        """
        :param str start : シフトの開始時刻。HH:MMで書く。
        :param str end : シフトの終了時刻。HH:MMで書く。
        """
        if type(start) is str:
            self.start = datetime.datetime.strptime(start, "%H:%M")
        elif type(start) is datetime.datetime:
            self.start = start
        if type(end) is str:
            self.end = datetime.datetime.strptime(end, "%H:%M")
        elif type(end) is datetime.datetime:
            self.end = end
        self.requested = None

    def update_start(self, start):
        """
        :param str start : 新しいシフトの開始時刻。HH:MMで書く。
        """
        self.start = datetime.datetime.strptime(start, "%H:%M")

    def update_end(self, end):
        """
        :param str end : 新しいシフトの終了時刻。HH:MMで書く。
        """
        self.end = datetime.datetime.strptime(end, "%H:%M")

    def update(self, start, end):
        """
        :param str start : 新しいシフトの開始時刻。HH:MMで書く。
        :param str end : 新しいシフトの終了時刻。HH:MMで書く。
        """
        self.update_start(start)
        self.update_end(end)

    def add_request(self, start, end):
        """
        :param str start : 新しいシフトの開始時刻。HH:MMで書く。
        :param str end : 新しいシフトの終了時刻。HH:MMで書く。
        """
        self.requested = Worktime(start, end)

    def to_dict(self):
        return_dict = {
            "start": self.start.strftime("%H:%M"),
            "end": self.end.strftime("%H:%M"),
        }
        return return_dict


class Worker:
    def _str__(self):
        return_str = f"name:{0} worktime:{1}".format(self.name, self.worktime)
        return return_str

    def __repr__(self):
        obj_dict = {"name": self.name, "worktime": self.worktime}
        return str(obj_dict)

    def __init__(self, name, times):
        """
        :param str name : 働く人の名前。
        :param times: その人が働く時間。Worktimeオブジェクトのリスト
        """
        self.name = name
        self.worktime = times


class Shift:
    WORKDAYS = ("mon", "tue", "wed", "thu", "fri")
    WORKDAYS_JP = ("月", "火", "水", "木", "金")

    def _str__(self):
        return_str = ""
        for (weekdayindex, day) in enumerate(self.shift):
            return_str += "{0} : {1},".format(Shift.WORKDAYS[weekdayindex], day)
        return return_str

    def __repr__(self):
        obj_dict = {
            Shift.WORKDAYS[weekdayindex]: day
            for (weekdayindex, day) in enumerate(self.shift)
        }
        return str(obj_dict)

    @staticmethod
    def hook(dct):
        if dct.get("start") is not None:
            return Worktime(dct["start"], dct["end"])
        elif dct.get("name") is not None:
            return Worker(dct["name"], dct["worktime"])
        elif dct.get("mon") is not None:
            return Shift(
                dct.get(Shift.WORKDAYS[0]),
                dct.get(Shift.WORKDAYS[1]),
                dct.get(Shift.WORKDAYS[2]),
                dct.get(Shift.WORKDAYS[3]),
                dct.get(Shift.WORKDAYS[4]),
            )
        else:
            return dct

    @staticmethod
    def parse_json(json_path):
        """
        Parameters
        ----------
        json_path : string
            読み込むシフトのjsonファイルのpath
        """
        shiftFile = open(json_path, "r")
        shift_dict = json.load(shiftFile)
        return json.loads(json.dumps(shift_dict), object_hook=Shift.hook)

    @staticmethod
    def count_worktime(worktime, columnCount=False):
        delta = worktime.end - worktime.start
        hour = int(delta.seconds) / 3600
        if columnCount:
            diff9th = worktime.start - datetime.timedelta(hours=8)
            # diff9th = worktime.start - (worktime.start - datetime.timedelta(hours=9))
            startColumn = (
                int(diff9th.strftime("%H")) * 2 + int(diff9th.strftime("%M")) / 30
            )
            return {"startColumn": startColumn, "columns": hour * 2}
        else:
            return hour * 2

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

    def __init__(self, mon, tue, wed, thu, fri):
        self.shift = [mon, tue, wed, thu, fri]
        self.sort_by_starttime()

    def get_member(self):
        menbers = []
        for day in self.shift:
            for worker in day:
                if worker.name not in menbers:
                    menbers.append(worker.name)
        return menbers

    def get_shift_of_member(self, name):
        shift_list = []
        for day in self.shift:
            for worker in day:
                if worker.name == name:
                    print(worker)
                    shift_list.append(
                        {
                            Shift.WORKDAYS_JP[self.shift.index(day)]: [
                                time.to_dict() for time in worker.worktime
                            ]
                        }
                    )
        return shift_list

    def get_requested_shift(self):
        shift_list = []
        for day in self.shift:
            for worker in day:
                for time in worker.worktime:
                    if time.requested is not None:
                        shift_list.append(
                            {Shift.WORKDAYS_JP[self.shift.index(day)]: time.to_dict()}
                        )

        return shift_list

    def sort_by_starttime(self):
        for (weekdayindex, workers) in enumerate(self.shift):
            for worker in workers:
                worker.worktime = sorted(worker.worktime, key=lambda x: x.start)
            self.shift[weekdayindex] = sorted(
                workers,
                key=lambda worker: (worker.worktime[0].start, worker.worktime[0].end),
            )

    def add(self, weekday, name, worktime):
        """
        :param str weekday : 追加するシフトの曜日。
        :param str name : 働く人の名前。
        :param worktimes: 追加するシフトの時間。["HH:MM","HH:MM"]
        """
        weekdayindex = Shift.WORKDAYS.index(Shift.exchange_weekdayname(weekday))
        for worker in self.shift[weekdayindex]:
            if worker.name == name:
                worker.worktime.append(Worktime(worktime[0], worktime[1]))
                break
        else:
            newWorker = Worker(
                name, (Worktime(times[0], times[1]) for times in worktime)
            )
            self.shift[weekdayindex].append(newWorker)
        self.sort_by_starttime()

    def delete(self, weekday, name, index=1):
        weekdayindex = Shift.WORKDAYS.index(Shift.exchange_weekdayname(weekday))
        for worker in self.shift[weekdayindex]:
            if worker.name == name:
                del worker.worktime[index - 1]
                if not worker.worktime:
                    self.shift[weekdayindex].remove(worker)
        self.sort_by_starttime()

    def update(self, weekday, name, time, index=1):
        """
        :param str weekday : 追加するシフトの曜日。
        :param str name : 働く人の名前。
        :param time: 修正後のシフトの時間。["HH:MM","HH:MM"]
        :param index: 修正するシフトがその日の何番目か
        """
        weekdayindex = Shift.WORKDAYS.index(Shift.exchange_weekdayname(weekday))
        for worker in self.shift[weekdayindex]:
            if worker.name == name:
                worker.worktime[index - 1].update(time[0], time[1])
        self.sort_by_starttime()

    def add_request(self, weekday, name, index=1, requestedtime=None):
        weekdayindex = Shift.WORKDAYS.index(Shift.exchange_weekdayname(weekday))
        for worker in self.shift[weekdayindex]:
            if worker.name == name:
                if requestedtime is None:
                    worker.worktime[index - 1].requested = Worktime(
                        worker.worktime[index - 1].start, worker.worktime[index - 1].end
                    )
                    # worker.worktime[index - 1]["requested"] = {
                    #     "start": (
                    #         if requestedtime is None
                    #         else requestedtime["start"]
                    #     ),
                    #     "end": (
                    #         worker["worktime"][index - 1]["end"]
                    #         if requestedtime is None
                    #         else requestedtime["end"]
                    #     ),
                    # }
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
        (141, 179, 247),
        (133, 184, 231),
        (168, 146, 209),
        (213, 166, 189),
    )
    HEIGHT = 1026

    gridLineWeight = 1
    boldLineWeight = 3

    def __init__(self, shift, kanjiFontPath, kanjiBoldFontPath=None, fontPath=None):
        if fontPath is None:
            fontPath = kanjiFontPath
        if kanjiBoldFontPath is None:
            kanjiBoldFontPath = kanjiFontPath

        self.shift = shift
        divWidth = self.count_need_row()  # シフトを挿入する列数
        self.needRows = divWidth + 4  # 表の余白分を含めた列数
        self.font = ImageFont.truetype(str(fontPath), 25)
        self.smallFont = ImageFont.truetype(str(fontPath), 15)
        self.kanjiFont = ImageFont.truetype(str(kanjiFontPath), 25)
        self.kanjBoldFont = ImageFont.truetype(str(kanjiBoldFontPath), 25)
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
                countedRows += len(weekday)
            return countedRows
        else:
            return len(selectedWeekday)

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

    def print_weekseparateline(
        self,
        font=None,
        boldFont=None,
        lineWeight=boldLineWeight,
        color=BLACK,
        weekday=None,
    ):
        if font is None:
            font = self.kanjiFont
        if boldFont is None:
            boldFont = self.kanjBoldFont

        tmpCountRow = 2  # 両サイド2列分開いてるからoffset
        weekdayList = ("月", "火", "水", "木", "金")
        if weekday is None:
            weekday = "mon"
        weekday = Shift.exchange_weekdayname(weekday)
        self.drawObj.line(
            [(self.rowWidth * 2, 0), (self.rowWidth * 2, self.height)],
            (0, 0, 0),
            lineWeight,
        )
        for (day, loopCount) in zip(self.shift.shift, range(len(self.shift.shift))):
            weekdayLabelPoint = (
                self.rowWidth * (tmpCountRow + self.count_need_row(day) / 2)
                - font.getsize(weekdayList[loopCount])[0] / 2,
                (self.columnHeight - font.getsize(weekdayList[loopCount])[1]) / 2,
            )
            if weekday == day:
                self.drawObj.text(
                    weekdayLabelPoint, weekdayList[loopCount], color, boldFont
                )
            else:
                self.drawObj.text(
                    weekdayLabelPoint, weekdayList[loopCount], color, font
                )
            tmpCountRow += self.count_need_row(day)
            self.drawObj.line(
                [
                    (self.rowWidth * (tmpCountRow), 0),
                    (self.rowWidth * (tmpCountRow), self.height),
                ],
                color,
                lineWeight,
            )

    def print_names(self, font=None, boldFont=None, weekday=None):
        if font is None:
            font = self.kanjiFont
        if boldFont is None:
            boldFont = self.kanjBoldFont
        if weekday is None:
            weekday = datetime.datetime.now().strftime("%a")
        """
        weekday = Shift.exchange_weekdayname(weekday)
        weekdaylist = []
        print(Shift.WORKDAYS[0])
        weekdaylist.extend(
            [Shift.WORKDAYS[0]
                for i in self.shift[Shift.WORKDAYS[0]]["worker"]]
        ).extend(
            [Shift.WORKDAYS[1]
                for i in self.shift[Shift.WORKDAYS[1]]["worker"]]
        ).extend(
            [Shift.WORKDAYS[2]
                for i in self.shift[Shift.WORKDAYS[2]]["worker"]]
        ).extend(
            [Shift.WORKDAYS[3]
                for i in self.shift[Shift.WORKDAYS[3]]["worker"]]
        ).extend(
            [Shift.WORKDAYS[4]
                for i in self.shift[Shift.WORKDAYS[4]]["worker"]]
        )
        print(weekdaylist)
        """
        nameBottomOfiiset = 20
        for (row, name) in enumerate(
            [worker.name for day in self.shift.shift for worker in day]
        ):
            """
              if day == weekday:
                  self.write_text_ttb(
                      {
                          "x": self.rowWidth * (row + 2.5),
                          "y": self.columnHeight + self.heightOffset + nameBottomOfiiset,
                      },
                      name,
                      font=boldFont,
                  )
              else:
              """
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
            for worker in weekday:
                for worktime in worker.worktime:
                    worktimePerDay += Shift.count_worktime(worktime)
                    rectApex = self.calc_rect_apices(worktime, rowCounter)
                    self.drawObj.polygon(
                        rectApex, fill=colorTable[weekday.index(worker)]
                    )
                    if worktime.requested is not None:
                        requestTime = Shift.count_worktime(worktime.requested)
                        worktimePerDay -= requestTime
                        apex = self.calc_rect_apices(worktime.requested, rowCounter)
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

    def makeImage(self, empday=None, timepos="None"):
        self.print_worktimerect(timepos)
        self.print_names()
        self.print_grid()
        self.print_weekseparateline()
        self.print_time()
        return self.image


if __name__ == "__main__":
    shift = Shift.parse_json("./shift.json")
    # shift.update("mon", "松田", ["9:00", "12:00"])
    # shift.add("mon", "新宮", [["12:00", "16:00"], ["9:00", "11:00"]])
    # shift.delete("mon", "新宮", 1)
    # shift.delete("mon", "新宮", 1)
    for item in shift.shift:
        for day in item:
            print(day)
            # for worktime in day.worktime:
    print(shift.get_shift_of_member("熊田"))
    # print(shift)
    # shift = Shift("./shift.json")
    make = DrawShiftImg(
        shift,
        "/Users/yume_yu/Library/Fonts/Cica-Regular.ttf",
        "/Users/yume_yu/Library/Fonts/Cica-Bold.ttf",
        "/Library/Fonts/Arial.ttf",
    )
    # make.shift.add_request("月", "松田", requestedtime={"start": "13:00", "end": "16:00"})
    # make.shift.delete_request("月", "松田")
    # make.shift.add("月", "松田", {"start": "09:00", "end": "10:00"})
    # make.update()
    image = make.makeImage()
    image.show()
    # make.shift.export("./export.json")
    # make.update()
    # image = make.makeImage()
    # image.show()
    # image.save("./sample.jpg", quality=95)
