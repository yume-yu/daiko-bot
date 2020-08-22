# daiko-botってなに
GoogleCalendarに登録したアルバイトのシフトを確認/代行依頼することができるSlackApp。シフト登録用のWebフォームも準備中。

# 動かすのに必要なもの
1. python 3.7.3 (2020/08/22現在 開発環境)
1. SlackのWorkSpace
1. Googleアカウント
1. 有効なシフト,代行依頼中のシフト,開館情報の3つのGoogleCalendar
1. メンバー一覧のGoogleSheet
1. Googleアクセストークン&リフレッシュトークン
1. foreman https://www.theforeman.org/manuals/1.24/quickstart_guide.html

# daiko-bot単体を動かすための準備
1. git cloneと準備の準備
1. .envファイルの準備
1. foremanを使って実行


## 1. git clone と 準備の準備
まずはgit cloneする。このとき、プロジェクトのディレクトリが実行ディレクトリとなるので作る場所には注意。clone後、`Python -V` などで動作バージョンを確認してから必要パッケージのインストールを行う。
```shell
$ git clone ...
$ python -V
Python 3.7.3
$ pip install -r requirements.txt
```
## 2. .envファイルの準備
git cloneしたディレクトリに`.env`ファイルを作成する。必要な内容は以下の通り。
|キー名|値|
|:---|:---|
|REFRESH_TOKEN | Google OAuthトークンのリフレッシュトークン|
|CALENDARID_SHIFT |有効なシフトを記録するカレンダーのカレンダーID|
|CALENDARID_DAIKO |代行依頼済みシフトを記録するカレンダーのカレンダーID|
|CALENDARID_OPEN |開館情報を記録するカレンダーのカレンダーID|
|DATABASE_SHEET |ユーザー情報/利用状況を記録するためのスプレッドシートのファイルID|
|CLIENT_SECRET_JSON |Google OAuthクライアントIDの認証情報のjsonファイルの中身全部|
|NOTICE_CHANNEL |代行依頼などの通知を送るSlackチャンネルのチャンネルID|
|SLACK_OAUTH_TOKEN|xoxp- から始まるSlackのOAuth Access Token|
|SLACK_BOT_TOKEN|xoxb- から始まるSlackのUser OAuth Access Token|
|SLACK_VALID_TOKEN|SlackのVerification Token|
|ADD_TOKEN|テスト時に2つ目のワークスペースから使うためのSlackのVerification Token。必要ないときは適当な文字列を入れておく|

## 3. foremanをつかって実行
プロジェクトルートで `$ foreman start`とすることで実行。http://your-host-name/slack へSlackからリクエストするようにすればSlackAppとして動く。

# 連携サービスの認証などの必要情報

1. Google側の準備
    1. 利用する3つのカレンダーを作成する。
    1. メンバー一覧のSheetを作成する
    1. Google OAuthクライアントIDを作成する / client_secret.jsonをもらう
    1. リフレッシュトークンを取得
1. Slack側の準備
    1. SlackAppを作成する
    1. Appに権限を与える
    1. 必要な認証情報の確認
    1. アプリの呼び出し設定


## 2-1. 利用する3つのカレンダーを作成する。
Web版GoogleCalendarからそれぞれを作成しておく。作成した3つのカレンダーのurlをそれぞれメモしておく。

## 2-2. メンバー一覧のSheetを作成する
daiko-botが個人を特定してGoogkeCalendar上と紐付けるためにはこのシートが必要。作成して、botが使うアカウントから読み書きできればよい。

> 現行では`Share/ツール/daiko-bot/Database`が該当。
* "name-id" シート<br>
    フォーマットは下記の通り。
    |slack-id|name in table|
    |:---|:---|
    |ABCDEFGH1|鈴木|
    |ABGDGFGH4|田中|

    このとき、`name in table` の行の名前がGoogleCalendar/daiko-bot上で扱われる名前になるので注意。表示名はslackとは同期されない。

* "temp-conversation" シート<br>
    会話UIの一時情報を保持するシート。作成さえしておけばok。停止中のため割愛。

* "use-logs" シート<br>
    ユーザーの利用記録を取るシート。作成さえしておけばok。

## 2-3..Google OAuthクライアントIDを作成する / client_sectert.jsonをもらう
このアプリケーションはGoogleのAPIを利用するため、トークンを取得する必要がある。
> 参考; https://qiita.com/chenglin/items/f2382898a8cf85bec8dd

1. Google Cloud Platformにアクセスする
2. 「プロジェクトの選択」からdaiko-botで使うためのプロジェクトを作成する
3. 左上のハンバーガーメニューから、"APIとサービス > 認証情報" を開く
4. 画面上部「認証情報を作成」から"OAuthクライアントID"を選択
5. 以下のように情報を設定
  * アプリケーションの種類: ウェブ アプリケーション
  * 名前: daiko-bot(ここはなんでもいい)
  * 承認済みJavaScript作成元: 無視
  * 承認済みのリダイレクト URI: `http://localhost:8080/` ←末尾の/を忘れずに
6. 作成後、一覧から`client_secret_hogehogehoge.json`をダウンロードして、`client_secret.json`にリネームする

## 2-4. リフレッシュトークンを取得
Googleへのアクセストークンをdaiko-botで更新できるようリフレッシュトークンを取得する。

1. 先程の`client_secret.json`を`setup/`ディレクトリに配置する
1. `get_token_info.py`を実行する
1. 表示されるurlにアクセスし、管理用アカウントとして承認する
1. 承認後のブラウザがアクセスしているurlを確認し、パラメータの`code=XXXXXXXXXX`の部分をshellに打ち込みEnterを押す
1. トークン情報が表示されるので、"refresh_token"の部分をメモしておく

## 3-1. SlackAppを作成する
[SlackAPIのページ](https://api.slack.com/apps)へアクセスし、"Create New App"から好きな名前と対象のWorkspaceを指定してアプリケーションを作成する

## 3-2. Appに権限を与える
左側のメニュー"OAuth & Permissions"を開く。"Scopes"の節までスクロールし、"Add an OAuth Scope"をクリックして以下の権限を与える。
* bot
* chennels:history
* chennels:read
* chat:write:bot
* commands
* im:history
* im:write
* incoming-webhook

## 3-3. 必要な認証情報の確認
左側のメニュー"Basic Information"から、以下の項目を確認してメモする。
* Verification Token

左側のメニュー"OAuth & Permissions"から、以下の項目を確認してメモする。
* OAuth Access Token
* Bot User OAuth Access Token

## 2-4. アプリの呼び出し設定
* CUI風 & GUIよびだしの設定<br>
    左側の"Slash Commands"を開き、"Create New Command"から追加する。
    |項目名|CUI|GUI|
    |:---|:---|:---|
    |Command|/d|/daiko|
    |Request URL|https://daiko-bot.herokuapp.com/slack|https://daiko-bot.herokuapp.com/slack|

    その他の項目は自由記述。Commandの項目を変えると呼び出しに失敗するようになるので注意(url統合の後遺症)。

* 会話UIの設定<br>
    左側の"Event Subscriptions"を開き、以下のように設定する。
    |項目名|値|
    |---|---|
    |Request URL|https://daiko-bot.herokuapp.com/slack|

    ただし、先にdaiko-botが稼働状態でないと動作確認に失敗して登録ができないので注意。

# QA

## メンバー一覧のシートについて

### 人が増えたら?
人が増えた場合は下の行に追記していけばよい。ただし、データが大きくなりすぎるとdaiko-botの処理速度に影響があるので、必要に応じて使わないユーザーを削除したほうがよい。

### ユーザーを削除してもいい?
slackidの修正や名前の変更はok。シートの情報の書き換えはdaiko-botに反映される。

### 他の情報を書き込んでもよい?
pythonでのデータの参照に列/行の情報を使っているので、左や上に空行や別のデータを挿入すると誤作動の原因になる。右側には何を追記しても問題ない。行を増やすとユーザーと認識してしまうので注意。
