# 対応済み単語/フォーマット
# 代行依頼時トリガー
#     おねがい お願い
# 代行請負時トリガー
#     うけます 受けます もらいます 貰います
# 日付フォーマット
#     MM/DD M月D日 D日
with open("daiko-dict.csv", "w") as file:
    file.write("代行,キーワード,ダイコウ\n")
    file.write("シフト,キーワード,シフト\n")
    file.write("お願,トリガー-依頼,オネガイ\n")
    file.write("おねがい,トリガー-依頼,オネガイ\n")
    file.write("受けます,トリガー-請負,ウケマス\n")
    file.write("うけます,トリガー-請負,ウケマス\n")
    file.write("もらいます,トリガー-請負,モライマス\n")
    file.write("貰います,トリガー-請負,モライマス\n")
    file.write("みせ,トリガー-確認,ミセ\n")
    file.write("見せ,トリガー-確認,ミセ\n")
    file.write("明日,日付-曖昧,アシタ\n")
    file.write("今日,日付-曖昧,キョウ\n")
    file.write("本日,日付-曖昧,ホンジツ\n")
    file.write("来週,日付-補助,来週\n")
    file.write("から,時刻-補助,から\n")
    file.write("まで,時刻-補助,まで\n")
    for hour in range(0, 24):
        file.write(
            "{hour}時,時刻,{fix_hour:0=2}:00\n".format(
                hour=hour, fix_hour=(hour if hour > 8 else hour + 12)
            )
        )
        for minute in range(0, 60):
            file.write(
                "{hour:0=2}:{minute:0=2},時刻,{fix_hour:0=2}:{minute:0=2}\n".format(
                    hour=hour, minute=minute, fix_hour=(hour if hour > 8 else hour + 12)
                )
            )
            file.write(
                "{hour:0=2}時{minute:0=2}分,時刻,{fix_hour:0=2}:{minute:0=2}\n".format(
                    hour=hour, minute=minute, fix_hour=(hour if hour > 8 else hour + 12)
                )
            )
            if hour < 10:
                file.write(
                    "{hour}:{minute:0=2},時刻,{fix_hour:0=2}:{minute:0=2}\n".format(
                        hour=hour,
                        minute=minute,
                        fix_hour=(hour if hour > 8 else hour + 12),
                    )
                )
                file.write(
                    "{hour}時{minute:0=2}分,時刻,{fix_hour:0=2}:{minute:0=2}\n".format(
                        hour=hour,
                        minute=minute,
                        fix_hour=(hour if hour > 8 else hour + 12),
                    )
                )
            if minute < 10:
                file.write(
                    "{hour:0=2}:{minute},時刻,{fix_hour:0=2}:{minute:0=2}\n".format(
                        hour=hour,
                        minute=minute,
                        fix_hour=(hour if hour > 8 else hour + 12),
                    )
                )
                file.write(
                    "{hour:0=2}時{minute}分,時刻,{fix_hour:0=2}:{minute:0=2}\n".format(
                        hour=hour,
                        minute=minute,
                        fix_hour=(hour if hour > 8 else hour + 12),
                    )
                )
            if hour < 10 and minute < 10:
                file.write(
                    "{hour}:{minute},時刻,{fix_hour:0=2}:{minute:0=2}\n".format(
                        hour=hour,
                        minute=minute,
                        fix_hour=(hour if hour > 8 else hour + 12),
                    )
                )
                file.write(
                    "{hour}時{minute}分,時刻,{fix_hour:0=2}:{minute:0=2}\n".format(
                        hour=hour,
                        minute=minute,
                        fix_hour=(hour if hour > 8 else hour + 12),
                    )
                )
            if minute == 30:
                file.write(
                    "{hour}時半,時刻,{fix_hour:0=2}:{minute:0=2}\n".format(
                        hour=hour,
                        minute=minute,
                        fix_hour=(hour if hour > 8 else hour + 12),
                    )
                )

    for month in range(1, 13):
        for day in range(1, 32):
            file.write(
                "{month:0=2}/{day:0=2},日付,{month:0=2}/{day:0=2}\n".format(
                    month=month, day=day
                )
            )
            file.write(
                "{month:0=2}月{day:0=2}日,日付,{month:0=2}/{day:0=2}\n".format(
                    month=month, day=day
                )
            )
            if month < 10:
                file.write(
                    "{month}/{day:0=2},日付,{month:0=2}/{day:0=2}\n".format(
                        month=month, day=day
                    )
                )
                file.write(
                    "{month}月{day:0=2}日,日付,{month:0=2}/{day:0=2}\n".format(
                        month=month, day=day
                    )
                )
            if day < 10:
                file.write(
                    "{month:0=2}/{day},日付,{month:0=2}/{day:0=2}\n".format(
                        month=month, day=day
                    )
                )
                file.write(
                    "{month:0=2}月{day}日,日付,{month:0=2}/{day:0=2}\n".format(
                        month=month, day=day
                    )
                )
            if day < 10 and month < 10:
                file.write(
                    "{month}/{day},日付,{month:0=2}/{day:0=2}\n".format(
                        month=month, day=day
                    )
                )
                file.write(
                    "{month}月{day}日,日付,{month:0=2}/{day:0=2}\n".format(
                        month=month, day=day
                    )
                )

    for day in range(1, 32):
        file.write("{day}日,日付-日,{day:0=2}\n".format(day=day))
        if day < 10:
            file.write("{day:0=2}日,日付-日,{day:0=2}\n".format(day=day))
    for weekday in ["日", "月", "火", "水", "木", "金", "土"]:
        file.write("{day}曜日,日付-曜日,{day}\n".format(day=weekday))
        file.write("{day}曜,日付-曜日,{day}\n".format(day=weekday))
