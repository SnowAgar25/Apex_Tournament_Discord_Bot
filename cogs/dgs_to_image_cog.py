import os
import re
from typing import Dict, List
import discord
from discord.ext import commands
from dotenv import load_dotenv
import requests
import yaml
from table2ascii import table2ascii, PresetStyle

from cogs.image_generator import ImageGenerator
from cogs.team_selection import get_teams, send_message_of_team_select

with open('./config.yml', 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)
    ranking_score_map = config["ranking_score_map"]
    kill_ranking_bonus_score_map = config["kill_ranking_bonus_score_map"]
    output_data = config["output_data"]
    order_by = config["order_by"]
    dgs_teamname_regexp = config["dgs_teamname_regexp"]

async def split_and_send(ctx, input_string, max_length=1900):
    # 將字串分割成指定長度的片段
    chunks = [input_string[i:i+max_length] for i in range(0, len(input_string), max_length)]

    # 逐一對每個片段執行 send 函數
    for chunk in chunks:
        await ctx.send(f"```\n{chunk}\n```")

def custom_sort(data_list):
                """
                我有一個list[list]
                第一層list代表每種數據類型，第二層list的數據代表每一隊的該數據
                舉個例子第二層每個list裡的index=0，代表第一隊的所有類型數據

                現在我有一個名為order by的list
                它可以有多個int，例如：[0, 2]
                這代表我想先以第一種數據類型對所有隊伍的順序進行排序，由大到小，如果有相同值的，就再以第二種數據類型排序
                記住，排序的時候一定要讓每種資料類型的同隊伍index一起移動，每個list裡面同個index都是映射為一個隊伍
                請用python幫我完成這個method

                下面是例子
                data_list = [
                    [10, 20, 30, 40, 50],
                    [15, 25, 35, 45, 55],
                    [5, 15, 25, 35, 45]
                ]

                order_by_list = [0, 2]

                output: [
                    [50, 50, 40, 20 10],
                    [55, 35, 45, 25, 15],
                    [45, 25, 35, 12, 5]

                ]
                """
                def sort_key(team):
                    return tuple(team[i] for i in order_by)
                sorted_data = sorted(zip(*data_list), key=sort_key, reverse=True)
                output = [list(row) for row in zip(*sorted_data)]
                return output

class DGSToImage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        load_dotenv()
        self.dgs_auth = os.getenv("DGS_AUTH")
        self.headers = {
            'Authorization': self.dgs_auth
        }
    pass

    @commands.command(aliases=['c'])
    @commands.has_permissions(administrator=True)
    async def convert(self, ctx: commands.Context, url: str):
        if 'apexlegendsstatus.com' not in url:
            await ctx.reply("請傳送要分析的場次網址，網域：apexlegendsstatus.com")
            return
        
        match = re.search(r'/(\d+)/', url)

        if not match:
            await ctx.reply("網址有誤，請確認")

        pattern = re.compile(r"{0}".format(dgs_teamname_regexp))

        try:
            # 發送請求並取得 JSON 數據
            response = requests.get(f"https://apexlegendsstatus.com/tournament/ingram/?qt=getScores&tournamentId={match.group(1)}", headers=self.headers)
            response.raise_for_status()
            json_data = response.json()

            # 這段本意是要防止「開預備房+隊名打錯編號」的情形
            # 但由於API會將資料分別傳送，並於網頁版合併，所以算是沒什麼用
            # 最好的方法是，盡量別開預備房，如果開了就要確保隊名一致
            # 以下是SSS隊伍的兩段資料
                # [4, 1, -1, -1, -1, -1]
                # [-1, -1, 7, 13, 10, 4] 
                # —————————————————————— or
                # [4, 1, 7, 13, 10, 4] 
            team_names_seen = set()
            team_from_url = []
            for i in range(len(json_data['teamData'])):
                team_name = json_data['teamData'][i]['teamName']
                if dgs_teamname_regexp:
                    team_name = pattern.search(team_name).group(1).strip()
                if team_name not in team_names_seen:
                    team_from_url.append(team_name)
                    team_names_seen.add(team_name)


            await ctx.reply(f"已獲取網址資料，請選擇與之匹配的本地隊伍```\n{team_from_url}\n```")

            team_path = await send_message_of_team_select(ctx)
            team_dict: Dict[str, str] = await get_teams(team_path)

            if not team_dict:
                return

            key, value = team_dict.keys(), team_dict.values()

            if set(team_from_url) == set(value):
                pass
            elif set(team_from_url) == set(key):
                pass
            else:
                await ctx.reply("網址資料與隊伍資料不匹配，請重新選擇隊伍")
                return
            
            data_from_url = [
                {
                    "teamname": json_data['teamData'][i]['teamName'],
                    "kills": json_data["teamData"][i]['kills'],
                    "ranking": json_data["teamData"][i]['ranking']
                } for i in range(len(json_data['teamData']))
            ]

            value_to_key_map = {v: k for k, v in team_dict.items()}
            # 根據list的順序獲取相對應的鍵
            full_teamnames = [value_to_key_map[value] for value in team_from_url if value in value_to_key_map]
            total_kills = [team.get("kills") for team in data_from_url]
            total_ranking_score = calc_custom_ranking_score([team.get("ranking") for team in data_from_url])
            await ctx.reply(f"ranking: ```{[team.get('ranking') for team in data_from_url]}```\ncalc_custom_ranking_score: ```{total_ranking_score}```")
            kill_bonus = calc_custom_kill_ranking_score(total_kills)

            # await ctx.reply(f"```\ntotal_kills: {type(total_kills)}\n{total_kills}\n```\n```\ntotal_ranking_score: {type(total_ranking_score)}\n{total_ranking_score}\n```\n```\nkill_bonus: {type(kill_bonus)}\n{kill_bonus}\n```")

            total_score = [sum(x) for x in zip(total_kills, total_ranking_score, kill_bonus)]

            # [簡稱, 隊名, 總擊殺, 總排名分, Kill_Bonus, 總分數]
            data_for_image = [
                team_from_url, # 隊伍簡稱
                full_teamnames, # 隊伍名稱
                total_kills, 
                total_ranking_score, 
                kill_bonus, 
                total_score
            ]

            # 驗證訊息
            header = ['隊伍', "總擊殺", '總排名分', 'Bonus', '總分數']
            rows = [team_from_url, total_kills, total_ranking_score, kill_bonus, total_score]
            rows = custom_sort(rows)
            rows = list(zip(*rows))
            message = f"**總結**\n```{table2ascii(header=header, body=rows, style=PresetStyle.borderless)}```"
            await ctx.reply(message)


            # 獲取符合圖片的資料 from get_data_for_image_format
            data_for_image = [data_for_image[i] for i in output_data]
            data_for_image = custom_sort(data_for_image)

            image_generator = ImageGenerator()
            img_bytes = await image_generator.add_text_to_image(data_for_image)
            file = discord.File(img_bytes, filename="image.png")

            await ctx.send(file=file)


        except requests.exceptions.RequestException as e:
            # 處理請求錯誤
            if '401' in str(e):
                await ctx.reply("請在根目錄新增.env檔案，並且填入DGS的Token，然後重啓Bot\nhttps://apexlegendsstatus.com/tournament/profile\n格式：DGS_AUTH=\"xxx\"")
            else:
                await ctx.send(f"發生錯誤: {e.__traceback__}")
        finally:
            response.close()

        pass

def calc_custom_ranking_score(list: List):
    """
    GPT提問邏輯：
        請幫我寫python method
        輸入是list[list[int]]
        第一層list代表每一個隊伍，第二層list代表該隊伍的每場比賽排名
        我有一個ranking_score_map: dict，結構是：「排名:分數」
        請你用以上提供的資料，幫我計算每一個隊伍的ranking_score總共是多少
        並輸出一個所有隊伍分數的list[int]
    """
    team_scores = []
    
    for team_ranking in list:
        team_score = 0
        
        for ranking in team_ranking:
            if ranking in ranking_score_map:
                team_score += ranking_score_map[ranking]
        
        team_scores.append(team_score)
    
    return team_scores

def calc_custom_kill_ranking_score(list: List):
    """
    GPT提問邏輯：
        請幫我寫python method
        輸入是list[int]，代表每一個隊伍的總擊殺
        我有kill_ranking_bonus_score_map: dict，結構是：「擊殺排名:分數」
        現在請你對比所有隊伍的擊殺，按照排名，以kill_ranking_bonus_score_map給分，如果排名沒有在map上，就給0分
        最後輸出一個和原來順序一樣的分數list

        請你給出一個list len 為20
        map len為5的例子
    """
    """
    由於這次不需要bonus，所以先不寫
    """
    return [0 for i in range(len(list))]

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DGSToImage(bot))
