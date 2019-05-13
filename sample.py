from workmanage import DrawShiftImg, Shift

shift = Shift("./sample.json")
make = DrawShiftImg(shift, "/Users/yume_yu/Library/Fonts/Cica-Regular.ttf")
image = make.makeImage()
image.show()
