import os
import asyncio
import discord
from discord.ext import commands
from gtts import gTTS
from pydub import AudioSegment
import langid
import tempfile
import re
from typing import List
from discord.utils import get
import yaml

tmp_directory = os.path.join(os.getcwd(), "tmp")

class BroadcastCog(commands.Cog):
    def __init__(self, all_bots):
        self.all_bots: List[discord.Client] = all_bots
        self.queue = []
        self.stop_event = asyncio.Event()
        self.task = None

        import shutil
        if os.path.exists(tmp_directory):
            shutil.rmtree(tmp_directory)
        os.makedirs(tmp_directory)
    
    def cog_load(self):
        self.task = self.all_bots[0].loop.create_task(self.loop_through_queue())
    
    def cog_unload(self):
        self.task.cancel()

    @commands.command(aliases=['bc'])
    @commands.has_permissions(administrator=True)
    async def broadcast(self, ctx: commands.Context, *input):
        text = '，'.join(input)
        self.queue.append((ctx, text))
        await ctx.reply(f"已放入佇列：{text}")

    @commands.command(aliases=['rst'])
    @commands.has_permissions(administrator=True)
    async def reset(self, ctx: commands.Context):
        """
        disconnect兼重置廣播任務，好讓用戶不用重開bot
        """

        # 清空廣播Queue
        self.queue.clear()

        # 取消loop_through_queue
        if self.task:
            self.task.cancel()

        # 讓bots登出語音頻道
        for bot in self.all_bots:
            for voice_client in bot.voice_clients:
                if voice_client.guild == ctx.guild:
                    await voice_client.disconnect(force=True)

        # 重新創建任務
        self.task = self.all_bots[0].loop.create_task(self.loop_through_queue())
        await ctx.reply(f'已重置廣播機器人')
    
    async def loop_through_queue(self):
        while True:
            try:
                if self.queue:
                    ctx, text = self.queue.pop(0)
                    mp3_path = text2mp3(text)
                    
                    with open('./config.yml', 'r', encoding='utf-8') as file:
                        config = yaml.safe_load(file)
                    channels = regex_channels(r"{0}".format(config["channels_regexp"]), ctx.guild)

                    await ctx.reply("正在廣播該訊息......")

                    num_bots = len(self.all_bots)
                    for i in range(0, len(channels), num_bots):
                        # 如果stop_event被設置，結束當前疊代
                        if self.stop_event.is_set():
                            break

                        channel_subset = channels[i:i + num_bots]

                        tasks = [self.play_audio(bot, channel, mp3_path)
                                for bot, channel in zip(self.all_bots, channel_subset)]
                        
                        await asyncio.gather(*tasks)

                    # 重置停止事件，以便下一個任務可以正常播放
                    self.stop_event.clear()
                await asyncio.sleep(0)
            except KeyboardInterrupt:
                self.stop_event.set()
                self.task.cancel()
            except asyncio.CancelledError:
                pass

    
    async def play_audio(self, bot_client: discord.Client, channel: discord.VoiceChannel, mp3_path):
        # 檢查是否已經連接到語音頻道
        channel = await bot_client.fetch_channel(channel.id)
        voice: discord.VoiceClient = get(bot_client.voice_clients, guild=channel.guild)

        if voice:
            await voice.disconnect(force=True)
        voice_client = await channel.connect()

        source = discord.FFmpegPCMAudio(mp3_path)
        voice_client.play(source)

        # 等待音频播放完成或收到停止事件
        while voice_client.is_playing():
            if self.stop_event.is_set():
                voice_client.stop()
                break
            await asyncio.sleep(1)

        # 離開語音頻道
        await voice_client.disconnect(force=True)


def text2mp3(text: str):
    lang = langid.classify(text)[0]
    with tempfile.NamedTemporaryFile(dir=tmp_directory) as fp:
        # 生成文本的語音
        tts = gTTS(text=text, lang=lang)
        text_audio_path = f'{fp.name}.mp3'
        tts.save(text_audio_path)
        
        # 加載intro音頻
        intro_audio = AudioSegment.from_mp3("./assets/intro.mp3")
        # 加載生成的文本語音
        text_audio = AudioSegment.from_mp3(text_audio_path)
        
        # 合併音頻
        combined_audio = intro_audio + text_audio
        
        # 儲存合併後的音頻
        final_audio_path = f'{fp.name}_with_intro.mp3'
        combined_audio.export(final_audio_path, format="mp3")
        
        return final_audio_path

def regex_channels(regex, guild: discord.Guild):
    pattern = re.compile(regex)
    voice_channels = guild.voice_channels
    return [channel for channel in voice_channels if pattern.search(channel.name)]

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BroadcastCog(bot))
