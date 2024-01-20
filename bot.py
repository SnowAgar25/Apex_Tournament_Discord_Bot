import json
import os
import random
from typing import List, NamedTuple
import discord
from discord.ext import commands
import asyncio
import yaml

from cogs.broadcast_cog import BroadcastCog
from cogs.score_to_image_cog import ScoreToImage

class BotEntry(NamedTuple):
    name: str
    url: str
    client: discord.Client
    token: str

intents = discord.Intents.all()

with open('tokens.json', 'r', encoding='utf-8') as file:
        tokens = json.load(file)

main_entry = BotEntry(
        name = tokens[0]['name'],
        url = tokens[0]['url'] or '',
        client = commands.Bot(command_prefix='>', intents=intents),
        token = tokens[0]['token']
    )

secondary_botentries = [
    BotEntry(
        name = token_info['name'],
        url = tokens[0]['url'] or '',
        client = discord.Client(intents=intents),
        token = token_info['token']
    )
    for _, token_info in enumerate(tokens[1:])
]

all_bots = [main_entry.client] + [entry.client for entry in secondary_botentries]

@main_entry.client.event
async def on_ready():
    with open('./config.yml', 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
        
    if config['broadcast']:
        await main_entry.client.add_cog(BroadcastCog(all_bots))
        print("🎈開啓廣播")
    if config['score_image']:
        await main_entry.client.add_cog(ScoreToImage(main_entry.client))
        print("🎈開啓計分&圖片")

    print("✅ 啓動成功（若要關閉請使用Ctrl+C）")

@main_entry.client.event
async def on_resumed():
    print("🛐 已重新連線")

@main_entry.client.event
async def on_disconnect():
    print("🈹 已中斷連線")

@main_entry.client.command()
async def ping(ctx: commands.Context):
    bot = random.choice(all_bots)
    channel = await bot.fetch_channel(ctx.channel.id)
    await channel.send(f'Pong by {bot._application.name} in {round(bot.latency, 1)} seconds!')

@main_entry.client.command()
async def standby(ctx: commands.Context):
    server_id = ctx.guild.id
    not_in_this_guild: List[BotEntry] = []

    all_entry: List[BotEntry] = [main_entry] + secondary_botentries
    for entry in all_entry:
        if not server_id in [guild.id for guild in entry.client.guilds]:
            not_in_this_guild.append(entry)

    if not_in_this_guild:
        selected_bot = [entry for entry in all_entry if entry not in not_in_this_guild][0]
        message = ''.join([f"{o_bot.name}並不在此群組，請點擊網址邀請：{o_bot.url}\n" for o_bot in not_in_this_guild])
        await selected_bot.client.get_channel(ctx.channel.id).send(message)
    else:
        await ctx.reply("所有機器人就位")

async def start_all_bots():
    await asyncio.gather(
        *(bot.client.start(token['token']) for bot, token in zip(secondary_botentries, tokens[1:])),
        main_entry.client.start(tokens[0]['token'])
    )

async def close_all_bots():
    await asyncio.gather(
        main_entry.client.close(),
        *(bot.client.close() for bot in secondary_botentries)
    )

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        print("🔄 正在準備……")
        loop.create_task(start_all_bots())
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(close_all_bots())


if __name__ == "__main__":
    log_path = './log'
    if not os.path.exists(log_path):
        os.makedirs(log_path)

    import logging
    logger = logging.getLogger('discord')
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(filename='./log/discord.log', encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s'))
    logger.addHandler(handler)

    logging.getLogger().addHandler(logging.StreamHandler())

    main()