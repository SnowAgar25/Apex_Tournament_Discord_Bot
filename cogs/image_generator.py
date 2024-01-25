import io
import yaml
import cv2
import collections
import numpy as np
from PIL import Image, ImageDraw, ImageFont


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