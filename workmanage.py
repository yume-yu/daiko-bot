import datetime
import json
from enum import Enum

from PIL import Image, ImageDraw, ImageFont
from pytz import timezone


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
            "eventid": self.eventid,
        }
        return str(obj_dict)

    def __init__(self, start, end, eventid=None, requested=None):
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
        self.requested = requested
        self.eventid = eventid

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

    def append_worktime(self, new_worktime: Worktime):
        self.worktime.append(new_worktime)


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
    def parse_dict(shift_dict: dict):
        return Shift(
            shift_dict.get(Shift.WORKDAYS[0]),
            shift_dict.get(Shift.WORKDAYS[1]),
            shift_dict.get(Shift.WORKDAYS[2]),
            shift_dict.get(Shift.WORKDAYS[3]),
            shift_dict.get(Shift.WORKDAYS[4]),
        )

    @staticmethod
    def count_worktime(worktime, columnCount=False):
        """
        Worktimeクラスから勤務時間に必要な目盛りの数と始点の位置を計算する
        """
        delta = worktime.end - worktime.start
        hour = int(delta.seconds) / 3600
        if columnCount:
            diff9th = worktime.start - datetime.timedelta(hours=9)
            # diff9th = worktime.start - (worktime.start - datetime.timedelta(hours=9))
            startColumn = (
                int(diff9th.strftime("%H")) * 2 + int(diff9th.strftime("%M")) / 30
            )
            # 勤務時間に加えて、必要な目盛りの数をtupleで返す
            return (hour * 2, startColumn)
            # return {"startColumn": startColumn, "columns": hour * 2}
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

    @staticmethod
    def has_worker(name: str, workers):
        for (index, worker) in enumerate(workers):
            if worker.name == name:
                return index
        else:
            return None

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
                    shift_list.append(worker)
        return shift_list

    def get_requested_shift(self):
        shift_list = []
        for day in self.shift:
            for worker in day:
                for time in worker.worktime:
                    if time.requested:
                        shift_list.append(Worker(name=worker.name, times=[time]))
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

    def contract_request(self, weekday, cliant_name, contractor_name, worktime):
        # 該当のシフトを削除する
        for item in shift.get_shift_of_member("松田"):
            for day in item:
                for time in item[day]:
                    if (
                        time["start"] == worktime["start"]
                        and time["end"] == worktime["end"]
                    ):
                        print(
                            time["start"],
                            time["end"],
                            worktime["start"],
                            worktime["end"],
                        )
                        break

        return None

    def export(self, path: str):
        exportfile = open(path, "w")
        json.dump(self.shift, exportfile, indent=2, ensure_ascii=False)


class CoordinateGenerator4DrawGrid(object):
    def __init__(
        self, pos: tuple, cell_width, cell_height, horizonal_count, vertical_count
    ):
        """
        ImageDraw.line()で格子を描画するための座標を生成するイテレーター
        :param tuple   pos              : 描画したい格子の左上の座標 (x,y)
        :param number  cell_width       : 格子の1マスの幅
        :param number  cell_height      : 格子の1マスの高さ
        :param number  horizonal_count  : 横のマスの数
        :param number  vertical_count   : 縦のマスの数
        """
        self.cell_width = cell_width
        self.cell_height = cell_height
        self.horizonal_count = horizonal_count
        self.vertical_count = vertical_count
        self.RIGHT = pos[0]
        self.LEFT = pos[0] + cell_width * horizonal_count
        self.TOP = pos[1]
        self.BOTTOM = pos[1] + cell_height * vertical_count
        self.coords_horizonal = self.coordinates_for_draw_horizonal_line()
        self.coords_vertical = self.coordinates_for_draw_vertical_line()

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return self.coords_horizonal.__next__()
        except StopIteration:
            return self.coords_vertical.__next__()

    def coordinates_for_draw_horizonal_line(self):
        r_or_l = self.right_or_left()
        for colmun in range(self.vertical_count + 1):
            yield (r_or_l.__next__(), int(self.TOP + colmun * self.cell_height))
            yield (r_or_l.__next__(), int(self.TOP + colmun * self.cell_height))
        yield (r_or_l.__next__(), self.TOP)
        yield (self.RIGHT, self.TOP)

    def coordinates_for_draw_vertical_line(self):
        t_or_b = self.top_or_bottom()
        for row in range(self.horizonal_count + 1):
            yield (int(self.RIGHT + row * self.cell_width), t_or_b.__next__())
            yield (int(self.RIGHT + row * self.cell_width), t_or_b.__next__())

    def right_or_left(self):
        while True:
            yield self.RIGHT
            yield self.LEFT
            yield self.LEFT
            yield self.RIGHT

    def top_or_bottom(self):
        while True:
            yield self.TOP
            yield self.BOTTOM
            yield self.BOTTOM
            yield self.TOP


class ShiftImageDirection(Enum):
    HORIZONAL = 1
    VERTICAL = 2


class DrawShiftImg:
    # 週のときの画像の高さ
    HEIGHT = 1026
    # 週のときの1人あたりの幅
    FOR_WIDTH_RATIO = 1624 / 38

    ## 1日分シフト用パラメータ ##
    # 画像の幅
    WIDTH = 1045
    # 1人あたりの高さ
    FOR_HEIGHT_RATIO = 1624 / 38
    # グリッドの上下マージンの列数
    TOP_MARGIN_LINES = 2
    BOTTOM_MARGIN_LINES = 1
    # グリッドの左マージンの幅に対する割合
    HORIZON_RIGHT_PCT = 0.13
    # 必要な列数
    NEED_COLUMNS = 20

    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    LIGHT_GRAY = (125, 125, 125)

    gridLineWeight = 1
    boldLineWeight = 3

    def __init__(self, shift, kanjiFontPath, kanjiBoldFontPath=None, fontPath=None):
        if fontPath is None:
            fontPath = kanjiFontPath
        if kanjiBoldFontPath is None:
            kanjiBoldFontPath = kanjiFontPath

        self.shift = shift
        self.shift_direction = None

        # 与えられたシフト情報の型で週のシフトか日のシフトかを判定する
        if isinstance(self.shift, Shift):
            print("This is Week Shift!")
            self.shift_direction = ShiftImageDirection.VERTICAL
            self.initialize_for_week(kanjiFontPath, kanjiBoldFontPath, fontPath)
        elif isinstance(self.shift, list) and isinstance(self.shift[0], Worker):
            print("This is a Day Shift!")
            self.shift_direction = ShiftImageDirection.HORIZONAL
            self.initialize_for_day(kanjiFontPath, fontPath)
        else:
            raise ValueError("Invalid Shift format")

    def initialize_for_week(self, kanjiFontPath, kanjiBoldFontPath, fontPath):
        try:
            self.font = ImageFont.truetype(str(fontPath), 25)
            self.smallFont = ImageFont.truetype(str(fontPath), 15)
            self.kanjiFont = ImageFont.truetype(str(kanjiFontPath), 25)
            self.kanjBoldFont = ImageFont.truetype(str(kanjiBoldFontPath), 25)
        except (IOError, OSError):
            raise ValueError("Invalid Font file path")

        divWidth = self.count_need_row()  # シフトを挿入する列数
        self.needRows = divWidth + 4  # 表の余白分を含めた列数
        self.width = int(DrawShiftImg.FOR_WIDTH_RATIO * self.needRows)
        self.height = DrawShiftImg.HEIGHT
        self.image = Image.new("RGB", (self.width, self.height), DrawShiftImg.WHITE)
        self.drawObj = ImageDraw.Draw(self.image)
        # 罫線を引くためのプロパティ
        self.needColumns = 23  # 名前部分を除いた必要な列数
        self.heightOffset = self.height / 8  # 上部の名前の空間の高さ
        self.namebox_height = self.height / 8  # 上部の名前の空間の高さ
        self.columnHeight = (
            self.height - self.heightOffset
        ) / self.needColumns  # 名前部分を以外の列の高さ
        self.rowWidth = self.width / self.needRows  # 1列の幅

    def initialize_for_day(self, kanjiFontPath, fontPath):
        try:
            self.font = ImageFont.truetype(str(fontPath), 100)
            self.kanjiFont = ImageFont.truetype(str(kanjiFontPath), 25)
            self.mediumFont = ImageFont.truetype(str(kanjiFontPath), 35)
            self.smallFont = ImageFont.truetype(str(kanjiFontPath), 15)
        except (IOError, OSError):
            raise ValueError("Invalid Font file path")

        self.needRows = len(self.shift)  # グリッドの必要行数
        self.width = DrawShiftImg.WIDTH
        self.height = DrawShiftImg.FOR_HEIGHT_RATIO * (
            DrawShiftImg.TOP_MARGIN_LINES
            + DrawShiftImg.BOTTOM_MARGIN_LINES
            + self.needRows
        )
        self.image = Image.new(
            "RGB", (int(self.width), int(self.height)), DrawShiftImg.WHITE
        )
        self.drawObj = ImageDraw.Draw(self.image)
        self.cell_size = self.FOR_HEIGHT_RATIO

    def gen_shiftrect_color(self):
        """
        シフト表の四角の色を順番に返すジェネレーター
        """
        while True:
            yield (216, 126, 107)
            yield (236, 153, 153)
            yield (249, 203, 156)
            yield (255, 230, 154)
            yield (182, 215, 168)
            yield (162, 196, 201)
            yield (141, 179, 247)
            yield (133, 184, 231)
            yield (168, 146, 209)
            yield (213, 166, 189)

    def count_need_row(self, selectedWeekday=None):
        countedRows = 0
        if selectedWeekday is None:
            for weekday in self.shift.shift:
                countedRows += len(weekday)
            return countedRows
        else:
            return len(selectedWeekday)

    def draw_worktime_rect(
        self,
        worktime: Worktime,
        base_pos: tuple,
        line_number: int,
        cell_width: int,
        cell_height: int,
        direction: ShiftImageDirection,
        color,
        font=None,
    ):
        font = self.font if font == None else font

        rectApex = self.calc_rect_apices(
            worktime, base_pos, line_number, cell_width, cell_height, direction
        )
        if worktime.requested:
            self.drawObj.polygon(rectApex, self.LIGHT_GRAY)
        else:
            self.drawObj.polygon(rectApex, fill=color)
        self.draw_worktime_detail(worktime, rectApex, direction, font)

    def draw_worktime_detail(
        self,
        worktime: Worktime,
        rectApex: list,
        direction: ShiftImageDirection,
        font: ImageFont,
    ):
        need_cell, start_cell = Shift.count_worktime(worktime, columnCount=True)
        if start_cell != 0:
            base_pos = rectApex[0]

            self.drawObj.text(
                (
                    base_pos[0]
                    if direction == ShiftImageDirection.VERTICAL
                    else base_pos[0]
                    - font.getsize(worktime.start.strftime("%H:%M"))[0],
                    base_pos[1] - font.getsize(worktime.start.strftime("%H:%M"))[1]
                    if direction == ShiftImageDirection.VERTICAL
                    else base_pos[1],
                ),
                worktime.start.strftime("%H:%M"),
                self.LIGHT_GRAY,
                font=font,
            )
        if start_cell + need_cell < self.NEED_COLUMNS:
            base_pos = rectApex[2]

            self.drawObj.text(
                (
                    base_pos[0] - font.getsize(worktime.end.strftime("%H:%M"))[0]
                    if direction == ShiftImageDirection.VERTICAL
                    else base_pos[0] + 1,
                    base_pos[1] - 3
                    if direction == ShiftImageDirection.VERTICAL
                    else base_pos[1] - font.getsize(worktime.end.strftime("%H:%M"))[1],
                ),
                worktime.end.strftime("%H:%M"),
                self.LIGHT_GRAY,
                font=font,
            )

    def calc_rect_apices(
        self,
        worktime: Worktime,
        base_pos: tuple,
        line_number: int,
        cell_width: int,
        cell_height: int,
        direction: ShiftImageDirection,
    ):
        """
        シフト時間を表す四角形の頂点の座標を返す
        :param Worktime Worktime    : 計算対象のシフト
        :param tuple    base_pos    : 表の左上,基準座標 (x,y)
        :param int      line_number : いくつ目のシフトなのか
        :param int      cell_width  : マスの幅
        :param int      cell_height : マスの高さ
        :param ShiftImageDirection  direction : シフト画像の伸びる向き
        """
        # 就業時間と目盛りの数を計算する
        need_cell, start_cell = Shift.count_worktime(worktime, columnCount=True)

        if direction == ShiftImageDirection.VERTICAL:
            return [
                (
                    base_pos[0] + cell_width * line_number,
                    base_pos[1] + cell_height * start_cell,
                ),
                (
                    base_pos[0] + cell_width * line_number,
                    base_pos[1] + cell_height * (start_cell + need_cell),
                ),
                (
                    base_pos[0] + cell_width * (line_number + 1),
                    base_pos[1] + cell_height * (start_cell + need_cell),
                ),
                (
                    base_pos[0] + cell_width * (line_number + 1),
                    base_pos[1] + cell_height * start_cell,
                ),
            ]
        elif direction == ShiftImageDirection.HORIZONAL:
            return [
                (
                    base_pos[0] + cell_width * start_cell,
                    base_pos[1] + cell_height * line_number,
                ),
                (
                    base_pos[0] + cell_width * (start_cell + need_cell),
                    base_pos[1] + cell_height * line_number,
                ),
                (
                    base_pos[0] + cell_width * (start_cell + need_cell),
                    base_pos[1] + cell_height * (line_number + 1),
                ),
                (
                    base_pos[0] + cell_width * start_cell,
                    base_pos[1] + cell_height * (line_number + 1),
                ),
            ]

        return None

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

    def print_grid_for_week_shift(self, lineWeight=gridLineWeight, color=LIGHT_GRAY):
        if self.shift_direction != ShiftImageDirection.VERTICAL:
            raise ValueError("Can use only for week shift")
        # 縦線の描画
        coor_gen = CoordinateGenerator4DrawGrid(
            (self.rowWidth * 2, self.heightOffset + 2 * self.columnHeight),
            self.rowWidth,
            self.columnHeight,
            self.needRows - 4,
            self.needColumns - 3,
        )
        self.drawObj.line([coordinate for coordinate in coor_gen], color, lineWeight)
        coor_gen = CoordinateGenerator4DrawGrid(
            (self.rowWidth * 2, self.columnHeight),
            self.rowWidth,
            self.heightOffset + self.columnHeight,
            self.needRows - 4,
            1,
        )
        self.drawObj.line([coordinate for coordinate in coor_gen], color, lineWeight)

    def print_grid_for_day_shift(self):
        if self.shift_direction != ShiftImageDirection.HORIZONAL:
            raise ValueError("Can use only for day shift")
        coord_gen = CoordinateGenerator4DrawGrid(
            (
                self.width * DrawShiftImg.HORIZON_RIGHT_PCT,
                DrawShiftImg.FOR_HEIGHT_RATIO * DrawShiftImg.TOP_MARGIN_LINES,
            ),
            self.cell_size,
            self.cell_size,
            DrawShiftImg.NEED_COLUMNS,
            self.needRows,
        )

        self.drawObj.line(
            [coord for coord in coord_gen],
            DrawShiftImg.LIGHT_GRAY,
            DrawShiftImg.gridLineWeight,
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
            self.drawObj.text(
                (
                    self.rowWidth * (tmpCountRow)
                    - font.getsize(
                        self.shift.shift[loopCount][0]
                        .worktime[0]
                        .start.strftime("%m/%d")
                    )[0]
                    - (font.getsize(" ")[0]) / 2,
                    self.columnHeight * (self.needColumns + 3)
                    - font.getsize(
                        self.shift.shift[loopCount][0]
                        .worktime[0]
                        .start.strftime("%m/%d")
                    )[1],
                ),
                self.shift.shift[loopCount][0].worktime[0].start.strftime("%m/%d"),
                color,
                font,
            )

    def print_names(self, font=None, boldFont=None):
        if font is None:
            font = self.kanjiFont

        if self.shift_direction == ShiftImageDirection.VERTICAL:
            if boldFont is None:
                boldFont = self.kanjBoldFont
            nameBottomOfiiset = 20
            for (row, name) in enumerate(
                [worker.name for day in self.shift.shift for worker in day]
            ):
                self.write_text_ttb(
                    {
                        "x": self.rowWidth * (row + 2.5),
                        "y": self.columnHeight + self.heightOffset + nameBottomOfiiset,
                    },
                    name,
                )
        elif self.shift_direction == ShiftImageDirection.HORIZONAL:
            for count in range(len(self.shift)):
                self.drawObj.text(
                    (
                        self.width * 0.12 - font.getsize(self.shift[count].name)[0],
                        DrawShiftImg.FOR_HEIGHT_RATIO
                        * (DrawShiftImg.TOP_MARGIN_LINES + count)
                        + DrawShiftImg.FOR_HEIGHT_RATIO * 0.5
                        - font.getsize(self.shift[count].name)[1] / 2,
                    ),
                    self.shift[count].name,
                    DrawShiftImg.BLACK,
                    font=font,
                )

    def print_worktimerect(
        self, shift, font=None, textColor=BLACK, timepos="None", counter_offset=0
    ):
        """
        1日分のシフトの四角形を描画する
        """
        # if font is None:
        #     font = self.smallFont

        counter = counter_offset
        color_iter = self.gen_shiftrect_color()
        for worker in shift:
            color = color_iter.__next__()
            for worktime in worker.worktime:
                self.draw_worktime_rect(
                    worktime,
                    (self.rowWidth * 2, self.heightOffset + 2 * self.columnHeight)
                    if self.shift_direction == ShiftImageDirection.VERTICAL
                    else (
                        self.width * DrawShiftImg.HORIZON_RIGHT_PCT,
                        DrawShiftImg.FOR_HEIGHT_RATIO * DrawShiftImg.TOP_MARGIN_LINES,
                    ),
                    counter,
                    self.rowWidth
                    if self.shift_direction == ShiftImageDirection.VERTICAL
                    else self.cell_size,
                    self.columnHeight
                    if self.shift_direction == ShiftImageDirection.VERTICAL
                    else self.cell_size,
                    self.shift_direction,
                    color,
                    font=font,
                )
            else:
                counter += 1
        return counter
        """
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
            """

    def print_time(self, font=None):
        if font is None:
            font = self.font

        if self.shift_direction == ShiftImageDirection.VERTICAL:
            timeToPrint = datetime.datetime(2000, 1, 1, 9, 0)
            timesOffset = 10
            for column in range(self.needColumns - 2):
                print_y = (
                    self.heightOffset
                    + self.columnHeight * (column + 2)
                    - font.getsize(timeToPrint.strftime("%H:%M"))[1] / 2
                )

                print_x = {
                    "right": self.rowWidth * 2
                    - font.getsize(timeToPrint.strftime("%H:%M"))[0]
                    - timesOffset,
                    "left": self.rowWidth * (self.needRows - 2) + timesOffset,
                }

                self.drawObj.text(
                    (print_x["right"], print_y),
                    str(timeToPrint.strftime("%H:%M")),
                    (0, 0, 0),
                    font,
                )
                self.drawObj.text(
                    (print_x["left"], print_y),
                    str(timeToPrint.strftime("%H:%M")),
                    (0, 0, 0),
                    font,
                )
                timeToPrint += datetime.timedelta(minutes=30)
        elif self.shift_direction == ShiftImageDirection.HORIZONAL:
            for time in range(11):
                now_str = "{:2}:00".format(time + 9)

                img = Image.new("RGBA", font.getsize(now_str), (255, 255, 255, 0))
                text_img = ImageDraw.Draw(img)
                text_img.text((0, 0), now_str, DrawShiftImg.BLACK, font=font)
                img = img.rotate(60, expand=True)
                img = img.resize((int(img.size[0] * 0.25), int(img.size[1] * 0.25)))
                tx, ty = img.size
                self.image.paste(
                    img,
                    (
                        int(
                            self.width * DrawShiftImg.HORIZON_RIGHT_PCT
                            + 2 * DrawShiftImg.FOR_HEIGHT_RATIO * time
                            - tx * 0.3
                        ),
                        int(2 * DrawShiftImg.FOR_HEIGHT_RATIO - 1.1 * ty),
                    ),
                    mask=img,
                )
            del text_img
            del img

    def print_date(self):
        if self.shift_direction != ShiftImageDirection.HORIZONAL:
            raise TypeError("This method only use in HORIZONAL")

        str_date = self.shift[0].worktime[0].start.strftime("%m/%d")
        font = self.mediumFont
        self.drawObj.text(
            (
                0.06 * self.width - font.getsize(str_date)[0] / 2,
                self.FOR_HEIGHT_RATIO - (font.getsize(str_date)[1] / 2),
            ),
            str_date,
            self.BLACK,
            font,
        )

    def print_generatedate(self, font=None, color=LIGHT_GRAY):
        if font is None:
            font = self.font
        now = datetime.datetime.now().astimezone(timezone("Asia/Tokyo"))
        now_str = now.strftime("generated at %Y/%m/%d %H:%M")

        img = Image.new("RGB", font.getsize(now_str), DrawShiftImg.WHITE)
        text_img = ImageDraw.Draw(img)
        text_img.text((0, 0), now_str, color, font=font)
        img = img.rotate(90, expand=True)
        img = img.resize((int(img.size[0] * 0.5), int(img.size[1] * 0.5)))
        tx, ty = img.size
        self.image.paste(img, (self.width - tx, 0))
        del text_img
        del img

    def make_shiftimage(self, empday=None, timepos="None"):
        self.print_names()
        self.print_time()
        if self.shift_direction == ShiftImageDirection.VERTICAL:
            counter = 0
            for shift_a_day in self.shift.shift:
                counter = self.print_worktimerect(
                    shift_a_day,
                    timepos=timepos,
                    counter_offset=counter,
                    font=self.smallFont,
                )
            self.print_grid_for_week_shift()
            self.print_weekseparateline()
            self.print_generatedate()
        elif self.shift_direction == ShiftImageDirection.HORIZONAL:
            self.print_worktimerect(self.shift, font=self.smallFont)
            self.print_grid_for_day_shift()
            self.print_date()
            # self.print_generatedate()

        return self.image


if __name__ == "__main__":
    shift = Shift.parse_json("./now.json")
    # shift = Shift.parse_json("./now.json")
    # shift.update("mon", "松田", ["9:00", "12:00"])
    # shift.add("mon", "新宮", [["12:00", "16:00"], ["9:00", "11:00"]])
    # shift.delete("mon", "新宮", 1)
    # shift.delete("mon", "新宮", 1)
    # for item in shift.shift:
    #    for day in item:
    #        print(day)
    #        # for worktime in day.worktime:
    # print(shift.get_shift_of_member("熊田"))
    # print(shift)
    # shift = Shift("./shift.json")
    make = DrawShiftImg(
        shift,
        "/Users/yume_yu/Library/Fonts/Cica-Regular.ttf",
        "/Users/yume_yu/Library/Fonts/Cica-Bold.ttf",
        "/Library/Fonts/Arial.ttf",
    )
    # print(type(shift.get_shift_of_member("松田")[0]))
    # print(shift.get_shift_of_member("松田")[0])
    # for item in shift.get_shift_of_member("松田"):
    #     for day in item:
    #         for time in item[day]:
    #             print(time["start"], time["end"])
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
    image.save("./sample.jpg", quality=95)
