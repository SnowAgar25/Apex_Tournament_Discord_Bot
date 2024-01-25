import collections
import os
import re
import json
import yaml
import glob

from typing import Dict
import discord
from discord.ext import commands


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
