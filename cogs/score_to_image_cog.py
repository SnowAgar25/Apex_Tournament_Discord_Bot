import collections
import os
import re
import json
import yaml
import glob

from typing import Dict, List, Tuple, Set
import cv2
import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

import io
import logging

import numpy as np

from table2ascii import table2ascii, PresetStyle
from typing import Dict, Tuple, List

with open('./config.yml', 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)
    round_name_map = config["round_name_map"]
    ranking_score_map = config["ranking_score_map"]
    kill_ranking_bonus_score_map = config["kill_ranking_bonus_score_map"]
    output_data = config["output_data"]
    output_color = config["output_color"]
    order_by = config["order_by"]

class ScoreToImage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.image_generator = ImageGenerator()
        
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler(filename='./log/score_to_image.log', encoding='utf-8', mode='w')
        handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s'))
        self.logger.addHandler(handler)

    @commands.command()
    async def i(self, ctx: commands.Context, *, text: str):
        """
        基本流程
        1. 文字轉換資料
        2. 對資料進行各種處理
        3-1. 轉換成製圖的資料
        3-2. 把資料處理的過程作成訊息，傳至Discord以便用戶驗算
        4. 把分數圖片上傳
        """

        # 獲取組別
        team = await send_message_of_team_select(ctx)

        if not team:
            return

        # 獲取該組別的隊伍資料，並創建一個GameScores的實例
        try:
            team_dict: Dict[str, str] = await get_teams(team)
            game = GameScores.from_raw_text(team_dict, text)
        except Exception as e:
            await ctx.reply(e)
            return

        # 生成資料的訊息
        bonus_message = "(含Bonus)" if game.is_bonus else "(不含Bonus)"
        practise_bonus_message = "(含額外分)" if game.practise_teams_for_bonus else "(不含額外分)"
        info_message = f"資料的場次如下: {', '.join(game.data_dict.keys())} {bonus_message}{practise_bonus_message}"

        data_for_image = game.get_data_for_image_format()

        img_bytes = await self.image_generator.add_text_to_image(data_for_image)
        file = discord.File(img_bytes, filename="image.png")

        await game.send_data_message_for_recheck(ctx)
        await ctx.send(info_message)
        await ctx.send(file=file)

class GameScores:
    def __init__(self, team_dict, data_dict, practise_teams_for_bonus):
        """
        該Class用於處理一切有關比賽分數的數據

        可透過特定格式的text輸入，創建實例
        並轉換資料爲「依照類型處理」「所有場次總和」「用於圖片合成的資料」

        若是輸入數據的段落包含所有場次，即「一、二、三、終、練習」，則會自動計算Bonus分數
        TODO: 此處邏輯尚未實現

        self.team_dict: Dict[short_name, team_name]
        self.data_dict: Dict[場次, List[隊伍Tuple[index, ranking, kills]]]
        self.practise_team_for_bonus: 參加練習賽的隊伍，加Bonus一分
        """
        self.team_dict: Dict[str, str] = team_dict
        self.data_dict: Dict[str, List[Tuple[int, int, int]]] = data_dict
        self.practise_teams_for_bonus: Dict[int, int] = practise_teams_for_bonus

        self._check_if_data_wrong()

        self.is_bonus = set(data_dict.keys()) == set(round_name_map)

    @staticmethod
    def _split_text_to_round_Dict(raw_text):
        """
        把raw_text拆分成包含不同場次的Dict
        """

        # 創建一個正則表達式，用於匹配場次名稱
        # 倘若將練習放入round_name_map，則會讓is_bonus判斷錯誤，是以將["練習"]放此。（透過unittest發現）
        round_name_map_for_split = round_name_map + ["練習"]
        round_name_pattern = "|".join(map(re.escape, round_name_map_for_split))
        round_name_regex = re.compile(f"({round_name_pattern})")

        # 使用正則表達式分割原始文本
        parts = round_name_regex.split(raw_text)
        round_text_dict = collections.OrderedDict()

        # 處理分割的部分，將場次名稱和對應的文本添加到字典中
        current_round_name = None
        for part in parts:
            if part in round_name_map_for_split:
                current_round_name = part
                if current_round_name in round_text_dict:
                    raise ValueError(f"場次{current_round_name}: 重複輸入")
                round_text_dict[current_round_name] = ""
            elif current_round_name is not None:
                round_text_dict[current_round_name] += part

        # 重新排序並返回結果字典
        output = collections.OrderedDict((name, round_text_dict[name]) for name in round_name_map_for_split if name in round_text_dict)
        return output

    
    @staticmethod
    def _convert_text_to_data_of_round_Dict(round_text_dict) -> Tuple[Dict[str, Tuple[int, int, int]], Dict[int, int]]:
        """
        把round_Dict裏的text轉換成data
        
        input: str
        output: Tuple[Dict[str, List[Tuple[int, int, int]]], Set[int]]
        """
        new_round_text_dict = {}
        practise_teams = {}

        for round_name, round_text in round_text_dict.items():
            if not round_name:
                # 資料不完備
                break

            if round_name == '額外分':
                [practise_teams.update({int(match[0]): int(match[1])}) for line in round_text.split("\n") if len(match := re.findall(r"\d+", line)) == 2]
                practise_teams = dict(sorted(practise_teams.items()))
            else:
                data = [
                    (int(match[0]), int(match[1]), int(match[-1]))
                    for line in round_text.split("\n")
                    if len(match := re.findall(r"\d+", line)) == 3
                ]

                # 按照隊伍index排序
                sorted_data = sorted(data, key=lambda x: x[0])
                new_round_text_dict.update({round_name: sorted_data})

        return new_round_text_dict, practise_teams

    def _check_if_data_wrong(self):
        """
        確認輸入的資料數量，是否等同於team_x.json裏的隊伍數量
        """
        team_len = len(self.team_dict)
        for key, round in self.data_dict.items():
            if key == "練習":
                continue

            if team_len != len(round):
                raise Exception(f"場次{key}: 資料數量({len(round)})與隊伍數量({team_len})不符")
            
    @classmethod
    def from_raw_text(cls, team_dict, raw_text: str):
        """
        input: 包含多組數據的text: index, 名次, 擊殺
        output: 依照場次排序的數據: index, 名次, 擊殺

        Dict[str, List[Tuple[int, int, int]]]
        """

        # 拆分場次→文字轉數據
        round_text_dict = GameScores._split_text_to_round_Dict(raw_text)
        data_dict, practise_teams = GameScores._convert_text_to_data_of_round_Dict(round_text_dict)

        # 返回一個實例
        instance = cls(team_dict, data_dict, practise_teams)
        return instance


    def get_data_by_type(self):
        """
        使資料以「名次」「名次分數」「擊殺數」的類型作排序。

        input: Dict[str, List[Tuple[int, int, int]]]
        output: Dict[str, Dict[str, List[int]]]

        每場Dict[每隊Tuple[index, 名次, 擊殺]]
        ↓
        Dict[每場Dict[名次_List, 名次分數_List, 擊殺數_List]]
        """

        data_dict_by_type = {}
        for round_num, team_list in self.data_dict.items():
            round_dict = {
                "rankings": [],
                "ranking_points": [],
                "kills": [],
            }

            for team_index, ranking, kills in team_list:
                ranking_score = ranking_score_map.get(ranking, 0)

                round_dict["rankings"].append(ranking)
                round_dict["ranking_points"].append(ranking_score)
                round_dict["kills"].append(kills)

            data_dict_by_type[round_num] = round_dict

        return data_dict_by_type

    def get_sum_of_data(self):
        """
        獲取資料的總和（所有比賽的加總）
        input: self.team_dict: Dict[short_name, team_name], self.data_dict_by_type: Dict[每場Dict[名次_List, 名次分數_List, 擊殺數_List, 擊殺排名_List, Total_Score_List]]
        output: List[Tuple[str, str, int, int, int, int]]

        每隊[簡稱, 隊名, 總擊殺, 總排名分, Bonus, 總分數]，依然按照team_index排列
        """
        data_dict_by_type: Dict[str, Dict[str, List[int]]] = self.get_data_by_type()
        team_sum_data: List[Tuple[str, str, int, int]] = []

        # 把每場擊殺和排名分加總在一起
        for index, (team_name, short_name) in enumerate(self.team_dict.items()):
            total_kills = 0
            total_ranking_score = 0

            for round_num, round_dict in data_dict_by_type.items():
                total_kills += round_dict["kills"][index]
                total_ranking_score += round_dict["ranking_points"][index]

            team_sum_data.append(
                (short_name, team_name, total_kills, total_ranking_score)
            )

        # 計算總擊殺排名，根據每一隊的kills比較，並且把排名按照隊伍順序排列，例如第一隊爲第三名，第二隊爲第四名，則[3, 4, ...]
        total_kill_ranking: List[int]
        sorted_teams = sorted(team_sum_data, key=lambda x: x[2], reverse=True)
        team_names = [team[0] for team in sorted_teams]
        total_kill_ranking = [team_names.index(team[0]) + 1 for team in team_sum_data]

        practise_teams_list = list(self.practise_teams_for_bonus.keys())

        # 遍歷隊伍，增添Bonus和總分
        for index, (
            short_name,
            team_name,
            total_kills,
            total_ranking_score,
        ) in enumerate(team_sum_data):
            
            bonus = (
                kill_ranking_bonus_score_map.get(total_kill_ranking[index], 0)
                if self.is_bonus
                else 0
            )

            if (index + 1) in practise_teams_list:
                bonus += self.practise_teams_for_bonus[index + 1]

            total_score = total_kills + total_ranking_score + bonus
            team_sum_data[index] = (
                short_name,
                team_name,
                total_kills,
                total_ranking_score,
                bonus,
                total_score,
            )

        return team_sum_data

    def get_data_for_image_format(self):
        """
        獲取符合圖片的資料
        output: List[Tuple]

        [List[簡稱], List[隊名], List[總擊殺數], List[總分數]]，並且按照總分數排列順序
        """
        data = self.get_sum_of_data()
        # 從每個data裏面，只獲取指定的數據
        data = [tuple(t[i] for i in output_data) for t in data]
        # 按照 指定的數據 排序
        data = sorted(data, key=lambda x: tuple(x[i] for i in order_by), reverse=True)

        return list(zip(*data))
    
    async def send_data_message_for_recheck(self, ctx: commands.Context):
        """
        傳送驗算的訊息，懶得補充了
        """
        view = discord.ui.View()

        def process_data(data_by_type):
            team_list = list(self.team_dict.values())

            header = ['隊伍', '排名', '排名分', '擊殺數']
            rows = []
            message_dict = {}

            for round, round_data in data_by_type.items():
                rankings = round_data['rankings']
                ranking_points = round_data['ranking_points']
                kills = round_data['kills']
                for i in range(len(rankings)):
                    row = [team_list[i], rankings[i], ranking_points[i], kills[i]]
                    rows.append(row)

                message_dict.update({round: f"**{round}**\n```{table2ascii(header=header, body=rows, style=PresetStyle.borderless)}```"})
                rows.clear()
            return message_dict
        
        def practise_team_bonus_data():
            header = ['隊伍', '次數']
            rows = []
            message_dict = {}

            team_list = list(self.team_dict.values())
            

            for index, value in self.practise_teams_for_bonus.items():
                row = [team_list[index-1], value]
                rows.append(row)

            message_dict.update({"練習賽Bonus": f"**練習賽Bonus**\n```{table2ascii(header=header, body=rows, style=PresetStyle.borderless)}```"})
            return message_dict
        
        def process_total_data(summed_data):
            header = ['隊伍', '總擊殺', '總排名分', 'Bonus', '總分數']
            rows = []
            message_dict = {}

            for data in summed_data:
                row = [data[0], data[2], data[3], data[4], data[5]]
                rows.append(row)

            message_dict.update({"總結": f"**總結**\n```{table2ascii(header=header, body=rows, style=PresetStyle.borderless)}```"})
            return message_dict

        async def button_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            button_index = int(interaction.data["custom_id"].split("_")[1]) - 1
            edit_text = text_dict.get(text_dict_keys[button_index])
            await interaction.message.edit(content=edit_text, view=view)

        text_dict = process_data(self.get_data_by_type())
        text_dict.update(process_total_data(self.get_sum_of_data()))

        if len(self.practise_teams_for_bonus) > 0:
            text_dict.update(practise_team_bonus_data())

        text_dict_keys = list(text_dict.keys())

        for index, text in enumerate(text_dict.values()):
            button = discord.ui.Button(label=f"{text_dict_keys[index]}", custom_id=f"button_{index+1}")
            button.callback = button_callback
            view.add_item(button)

        await ctx.send(text_dict[text_dict_keys[0]], view=view)


class ImageGenerator:
    """專門負責生成圖片的類"""

    def __init__(self):
        with open('./config.yml', 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)

        self.font_path = config["font"]
        self.image_for_score = config["image_for_score"]
        self.image_with_color_block = config["image_with_color_block"]

        # 顏色順序對應(第幾場, 簡稱, 隊名, 擊殺數, 總分)
        self.colors = config["output_color"]

    async def add_text_to_image(self, data_list: collections.OrderedDict):
        detect_img = cv2.imread(self.image_with_color_block)
        img = Image.open(self.image_for_score)

        black = (0, 0, 0)
        white = (255, 255, 255)

        text_h_offset = -2

        # img_pli = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)

        for color, datas in zip(self.colors, data_list):
            # 反正就是關於inRange使用hsv，所以RGB偵測不到，只能轉換過來
            R, G, B = color
            mask = cv2.inRange(detect_img, np.array([B, G, R]), np.array([B, G, R]))
            contours, hierarchy = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            rects = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > 100:  # 去除太小的輪廓
                    x, y, w, h = cv2.boundingRect(cnt)
                    rects.append((x, y, x + w, y + h))

            i = 1  # 紀錄每個顏色矩形的順序

            for cnt, data in zip(
                sorted(
                    contours, key=lambda x: (cv2.boundingRect(x)[0], cv2.boundingRect(x)[1])
                ),
                datas,
            ):
                x, y, w, h = cv2.boundingRect(cnt)
                text = str(data)

                scale = 0.75
                fontScale = int(min(w, h)) * scale

                font = ImageFont.truetype(self.font_path, int(fontScale))
                text_x, text_y, text_w, text_h = draw.textbbox((0, 0), text, font)

                text_x = x + w / 2 - text_w / 2
                text_y = y + h / 2 - text_h / 2 + text_h_offset  # 計算文字應該在矩形中的y座標

                draw.text((int(text_x), int(text_y)), text, font=font, fill=white)

                i += 1

        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")

        img_bytes.seek(0)
        return img_bytes

class SelectTeamButton(discord.ui.Button):
    def __init__(self, label, team_view, *args, **kwargs):
        super().__init__(label=label, *args, **kwargs)
        self.team_view : discord.ui.View = team_view  # Changed the name here

    async def callback(self, interaction: discord.Interaction):
        # 禁止再次使用按鈕
        for item in self.team_view.children:
            item.disabled = True

        # 更新callback的內容，好讓disabled起效
        await interaction.message.edit(view=self.team_view)

        # 儲存選擇的隊伍
        self.team_view.selected_team = self.label

        if self.label == '取消':
            await interaction.response.send_message(content=f"已取消執行")
        else:
            await interaction.response.send_message(content=f"已選擇{self.label}，請稍待片刻")

        self.team_view.stop()


class TeamSelectorView(discord.ui.View):
    def __init__(self, team_path, timeout):
        super().__init__(timeout=timeout)
        self.selected_team = None  # This will store the selected team
        for key in team_path.keys():
            # Pass the view instance to the SelectTeamButton
            self.add_item(SelectTeamButton(label=key, team_view=self, style=discord.ButtonStyle.primary))

async def send_message_of_team_select(ctx: commands.Context):
    json_paths_dict = {}
    for json_path in glob.glob(os.path.join('./data', '*.json')):
        filename, _ = os.path.splitext(os.path.basename(json_path))
        json_paths_dict[filename] = json_path

    json_paths_dict.update({'取消': None})

    view = TeamSelectorView(team_path=json_paths_dict, timeout=30)

    # Sending the message with the buttons
    await ctx.send(content="請選擇資料隊伍", view=view)

    # Waiting for the interaction to be completed (or timeout)
    await view.wait()

    value = json_paths_dict.get(view.selected_team)
    if value is not None:
        return value
    else:
        await ctx.send("沒有選擇隊伍，已取消")
        return None


async def get_teams(path) -> Dict[str, str]:
    """
    output: Dict[簡稱: 隊名]
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ScoreToImage(bot))
