# 簡介
此專案爲Apex自訂比賽主辦方的輔助Bot。

功能如下：
1. 廣播，在選定的頻道裡進行語音廣播，通知參賽者。
2. 計分+製圖，輸入比賽的玩家數據，讓程式自動計算，並且快速製圖。

# 說明
此專案爲個人使用，不會再進行任何變動。

本專案是根據澈日Clearsun的需求寫的，基本上應該不符合其他人的使用。

（但廣播功能還蠻簡單的，應該符合一般人使用）

如有需求，請自行在本地魔改。

代碼很爛，因爲我不會寫程式.jpg

註解很亂，部分跟代碼邏輯脫節，懶得更新

詳細設定在config.yml裡。

沒有使用Apex官方API是因爲當初寫的時候API不太穩定。

現在不知道如何，也懶得寫，有想法的自己魔改一下吧。

注意，廣播目前沒有支援多伺服器使用，只能自行使用，否則會出現Bug

# 安裝流程 
1. 到專案的資料夾裏，在主目錄自行新增tokens.json，並按照下述格式輸入資料。
    - 創建機器人Token：https://discord.com/developers/applications
    - 取得Token跟邀請url教學：https://ithelp.ithome.com.tw/articles/10262736

2. 安裝必要軟體，再安裝套件。

3. 視乎個人需求對start.cmd創建捷徑，點擊即可啓動Bot。

4. 邀請所有機器人到伺服器（可打\>standby邀請，若是token裏面有寫網址）

5. 若需要使用廣播功能，需自行更改Regex獲取要廣播的頻道（頻道名需有規律性，因爲使用Regex），請到config更改。

6. 如果要使用DGS轉圖片，請在根目錄新增.env檔案，並且填入DGS的Token，然後重啓Bot，格式：DGS_AUTH=\"xxx\"
   - https://apexlegendsstatus.com/tournament/profile 

# 必要軟體
- FFmpeg，並把/bin添加進PATH環境變數
    - 下載網址：https://ffmpeg.org/download.html
    - 安裝教學：https://withhh0525.weebly.com/tutorials/ffmpeg

- Python 3.10.7，安裝時記得勾選添加PATH環境變數
    - 下載網址：https://www.python.org/downloads/release/python-3107/
    - 安裝教學：https://www.codingspace.school/blog/2021-04-07

# 安裝套件
虛擬環境和安裝pypi套件。
```shell
pip install pipenv
pipenv install
```

# tokens.json
```
[  
    {
        "name":"Number1",
        "token": "...",
        "url": "https://discord.com/api/oauth2/authorize?client_id=..."
    },
    {
        "name":"Number2",
        "token": "...",
        "url": "https://discord.com/api/oauth2/authorize?client_id=..."
    },
    {
        "name":"Number3",
        "token": "...",
        "url": "https://discord.com/api/oauth2/authorize?client_id=..."
    },
]
```

# Start
啓動機器人
```shell
./start.cmd
```

# 使用方法
可以對start.cmd右鍵新增捷徑，並放到桌面上使用。

結束記得使用Ctrl+C結束，不要直接把視窗關閉，否則就得到工作管理員去把Python結束。

# 廣播指令
1. \>broadcast (>bc): 後面加上文字，把文字添加進廣播佇列。
2. \>reset (>rst)：直接重置整個廣播任務，用於機器人意外卡住，或是想取消廣播之際。

# 計分指令
- \>i
- 詳情請見分數製圖說明，和config裏面的提示

# DGS資料轉圖片
- \>convert(>c) https://apexlegendsstatus.com/tournament/results/xxxx/Overview
> 這東西只要比賽房間的隊伍名稱一有問題，就會爆炸，不用爲妙。

# 圖片示範
|<img src="https://i.imgur.com/jkHWo0g.png">|<img src="https://i.imgur.com/f3VhOto.png">|
|---|---|
|<img src="https://i.imgur.com/E7MEKQx.png">||

# 額外說明
- 於assets資料夾的intro.mp3是廣播的開頭，可以自行替換檔案，只需命名一致即可。
